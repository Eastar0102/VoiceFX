"""마이크 → 이펙트 → 가상 케이블(+모니터) 오디오 엔진."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

import numpy as np
import pedalboard as pb
import sounddevice as sd

from .dsp import NoiseSuppressor, run_chain
from .presets import Preset

SAMPLE_RATE = 48000
BLOCK = 480  # 10ms
FADE_SAMPLES = 2400  # 프리셋 전환 크로스페이드 50ms


@dataclass(frozen=True)
class Device:
    index: int
    name: str
    hostapi: str

    @property
    def label(self) -> str:
        return f"{self.name}  [{self.hostapi}]"


def list_devices() -> tuple[list[Device], list[Device]]:
    hostapis = sd.query_hostapis()
    inputs, outputs = [], []
    for i, d in enumerate(sd.query_devices()):
        api = hostapis[d["hostapi"]]["name"]
        # WDM-KS는 장치를 독점해서 다른 앱(디스코드)과 충돌하므로 제외
        if api == "Windows WDM-KS":
            continue
        dev = Device(i, d["name"], api)
        if d["max_input_channels"] > 0:
            inputs.append(dev)
        if d["max_output_channels"] > 0:
            outputs.append(dev)
    return inputs, outputs


class RingBuffer:
    """입력 스트림 → 출력 스트림 사이의 모노 지터 버퍼.

    입력·출력 콜백 타이밍이 서로 어긋나므로 target만큼 미리 채운 뒤 내보내고, 비면 조각난 소리를
    내보내는 대신 다시 채울 때까지 기다린다. 장치 간 클럭 차이로 쌓이는 지연은 target으로 잘라낸다.
    """

    def __init__(self, target: int, max_latency: int):
        self._buf = np.zeros(max_latency * 4, dtype=np.float32)
        self._target = target
        self._max_latency = max_latency
        self._primed = False
        self._r = 0
        self._count = 0
        self._lock = threading.Lock()

    def write(self, x: np.ndarray) -> None:
        cap = len(self._buf)
        with self._lock:
            n = len(x)
            w = (self._r + self._count) % cap
            first = min(n, cap - w)
            self._buf[w:w + first] = x[:first]
            self._buf[:n - first] = x[first:]
            self._count = min(self._count + n, cap)
            if self._count > self._max_latency:
                drop = self._count - self._target
                self._r = (self._r + drop) % cap
                self._count -= drop

    def read(self, n: int) -> np.ndarray:
        cap = len(self._buf)
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            if not self._primed:
                if self._count < self._target:
                    return out
                self._primed = True
            if self._count < n:
                self._primed = False  # 다 써버렸으면 다음엔 다시 채운 뒤 재생
            m = min(n, self._count)
            first = min(m, cap - self._r)
            out[:first] = self._buf[self._r:self._r + first]
            out[first:m] = self._buf[:m - first]
            self._r = (self._r + m) % cap
            self._count -= m
        return out


class AudioEngine:
    def __init__(self):
        self.input_gain = 1.0
        self.output_volume = 1.0
        self.monitor_volume = 0.8
        self.monitor_enabled = False  # 모니터 스트림은 열어두고 소리만 켜고 끈다 → 즉시 토글
        self.gate_enabled = True
        # 앱 자체 소음 억제: 마이크 목소리에만 적용 (사운드보드는 거치지 않음) → Discord 소음 억제를 꺼도 된다
        self.noise_suppression = True
        self._ns = NoiseSuppressor()
        self.level_in = 0.0
        self.level_out = 0.0
        self._chain: list = []
        self._chain_key = ""
        self._next: tuple[str, list] | None = None
        self._param_q: deque = deque()  # (프리셋 키, 단계, 속성, 값) — 오디오 스레드에서 적용
        self._fade_from: list | None = None
        self._fade_pos = 0
        self._gate = pb.NoiseGate(threshold_db=-45, ratio=10, attack_ms=2, release_ms=120)
        self._streams: list[sd._StreamBase] = []
        self._outs: list[tuple[RingBuffer, bool]] = []  # (버퍼, 모니터 여부)
        # 사운드보드: 목소리 효과를 거치지 않고 출력에 바로 섞는다
        self.soundboard_volume = 1.0
        self.sound_monitor = True  # 사운드는 '내 목소리 듣기'와 별개로 내 귀에도 들려준다
        self.sound_progress: dict[str, float] = {}  # 재생 중인 사운드 id → 진행률(0~1)
        self._sound_q: deque = deque()
        self._playing: dict[str, list] = {}  # id → [데이터, 위치, 볼륨]

    @property
    def running(self) -> bool:
        return bool(self._streams)

    def set_preset(self, preset: Preset, saved: dict | None = None) -> None:
        # 콜백이 다음 블록에서 집어가서 이전 체인과 크로스페이드한다 (참조 대입은 원자적)
        self._next = (preset.key, preset.build(saved))

    def set_param(self, preset_key: str, stage: int, attr: str, value: float) -> None:
        """체인을 다시 만들지 않고 값만 바꾼다 → 슬라이더를 끌어도 소리가 끊기지 않는다."""
        self._param_q.append((preset_key, stage, attr, value))

    @property
    def ns_strength(self) -> float:
        return self._ns.strength

    @ns_strength.setter
    def ns_strength(self, value: float) -> None:
        self._ns.strength = float(value)

    def play_sound(self, sound_id: str, data: np.ndarray, volume: float = 1.0) -> None:
        """mono float32 48kHz 데이터를 처음부터 재생 (재생 중이면 다시 시작)."""
        self._sound_q.append(("play", sound_id, data, volume))

    def stop_sound(self, sound_id: str) -> None:
        self._sound_q.append(("stop", sound_id))

    def stop_all_sounds(self) -> None:
        self._sound_q.append(("stop_all",))

    def set_sound_volume(self, sound_id: str, volume: float) -> None:
        self._sound_q.append(("volume", sound_id, volume))

    def start(self, input_idx: int, output_idx: int, monitor_idx: int | None = None) -> None:
        self.stop()
        target, max_lat = BLOCK * 2, BLOCK * 6  # 20ms 여유, 60ms 넘게 쌓이면 잘라냄
        self._outs = [(RingBuffer(target, max_lat), False)]
        targets = [output_idx]
        if monitor_idx is not None:
            self._outs.append((RingBuffer(target, max_lat), True))
            targets.append(monitor_idx)
        try:
            in_info = sd.query_devices(input_idx)
            self._streams.append(sd.InputStream(
                device=input_idx, channels=min(2, in_info["max_input_channels"]),
                samplerate=SAMPLE_RATE, blocksize=BLOCK, dtype="float32", latency="low",
                extra_settings=_extra(input_idx), callback=self._on_input))
            for (rb, _), idx in zip(self._outs, targets):
                out_info = sd.query_devices(idx)
                self._streams.append(sd.OutputStream(
                    device=idx, channels=min(2, out_info["max_output_channels"]),
                    samplerate=SAMPLE_RATE, blocksize=BLOCK, dtype="float32", latency="low",
                    extra_settings=_extra(idx), callback=self._make_output_cb(rb)))
            for s in self._streams:
                s.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        for s in self._streams:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._streams = []
        self._playing.clear()
        self._sound_q.clear()
        self.sound_progress = {}
        self.level_in = self.level_out = 0.0

    def _on_input(self, indata, frames, time, status) -> None:
        x = indata.mean(axis=1, dtype=np.float32)[None, :] * self.input_gain
        self.level_in = float(np.sqrt(np.mean(x * x)))
        if self.noise_suppression:
            x = self._ns.process(x, SAMPLE_RATE)
        if self.gate_enabled:
            x = self._gate.process(x, SAMPLE_RATE, reset=False)
        voice = self._process(x)[0] * self.output_volume
        sounds = self._mix_sounds(len(voice))
        y = np.clip(voice if sounds is None else voice + sounds, -1.0, 1.0)
        self.level_out = float(np.sqrt(np.mean(y * y))) if len(y) else 0.0
        for rb, is_monitor in self._outs:
            if not is_monitor:
                rb.write(y)
                continue
            m = voice * (self.monitor_volume if self.monitor_enabled else 0.0)
            if sounds is not None and self.sound_monitor:
                m = m + sounds * self.monitor_volume
            rb.write(np.clip(m, -1.0, 1.0))

    def _mix_sounds(self, n: int) -> np.ndarray | None:
        while self._sound_q:
            cmd = self._sound_q.popleft()
            if cmd[0] == "play":
                self._playing[cmd[1]] = [cmd[2], 0, cmd[3]]
            elif cmd[0] == "stop":
                self._playing.pop(cmd[1], None)
            elif cmd[0] == "stop_all":
                self._playing.clear()
            elif cmd[0] == "volume" and cmd[1] in self._playing:
                self._playing[cmd[1]][2] = cmd[2]
        if not self._playing:
            if self.sound_progress:
                self.sound_progress = {}
            return None
        out = np.zeros(n, dtype=np.float32)
        for sid, st in list(self._playing.items()):
            data, pos, vol = st
            chunk = data[pos:pos + n]
            out[:len(chunk)] += chunk * vol
            st[1] = pos + n
            if st[1] >= len(data):
                del self._playing[sid]
        self.sound_progress = {sid: st[1] / len(st[0]) for sid, st in self._playing.items()}
        return out * self.soundboard_volume

    def _process(self, x: np.ndarray) -> np.ndarray:
        nxt = self._next
        if nxt is not None:
            self._next = None
            self._fade_from, self._fade_pos = self._chain, 0
            self._chain_key, self._chain = nxt
        while self._param_q:
            key, stage, attr, value = self._param_q.popleft()
            if key == self._chain_key and stage < len(self._chain):
                try:
                    setattr(self._chain[stage], attr, value)
                except Exception:
                    pass  # 범위를 벗어난 값 등은 무시
        y = _safe_run(self._chain, x)
        if self._fade_from is not None:
            n = x.shape[1]
            w = np.minimum((self._fade_pos + np.arange(n)) / FADE_SAMPLES, 1.0).astype(np.float32)
            y = _safe_run(self._fade_from, x) * (1.0 - w) + y * w
            self._fade_pos += n
            if self._fade_pos >= FADE_SAMPLES:
                self._fade_from = None
        return y

    def _make_output_cb(self, rb: RingBuffer):
        def cb(outdata, frames, time, status):
            outdata[:] = rb.read(frames)[:, None]
        return cb


def _safe_run(chain: list, x: np.ndarray) -> np.ndarray:
    try:
        y = run_chain(chain, x, SAMPLE_RATE)
        return y if y.shape == x.shape else x
    except Exception:
        return x  # 한 블록 처리에 실패해도 소리는 계속 흐르게


def _extra(device_idx: int):
    api = sd.query_hostapis(sd.query_devices(device_idx)["hostapi"])["name"]
    if api == "Windows WASAPI":
        return sd.WasapiSettings(auto_convert=True)  # 장치 샘플레이트가 48k가 아니어도 동작
    return None
