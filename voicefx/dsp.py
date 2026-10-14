"""실시간용 저지연 커스텀 DSP.

모든 스테이지는 pedalboard 플러그인과 같은 시그니처를 따른다:
    process(x: np.ndarray[float32, (channels, n)], sample_rate, reset=False) -> np.ndarray
"""
from __future__ import annotations

import ctypes
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pylibrb as rb


_RNNOISE = None


def _rnnoise_lib():
    """rnnoise.dll만 직접 불러온다.

    pyrnnoise 패키지를 import하면 쓰지도 않는 audiolab/av(FFmpeg)까지 딸려 와서 시작이 느려지고
    EXE도 커지므로, 패키지는 실행하지 않고 위치만 찾아 DLL을 연다. EXE에서는 실행 폴더에 둔다.
    """
    global _RNNOISE
    if _RNNOISE is None:
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys._MEIPASS) / "rnnoise.dll")
        spec = importlib.util.find_spec("pyrnnoise")
        if spec and spec.submodule_search_locations:
            candidates.append(Path(next(iter(spec.submodule_search_locations))) / "rnnoise.dll")
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            raise OSError("rnnoise.dll을 찾을 수 없습니다")
        lib = ctypes.CDLL(str(path))
        lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        lib.rnnoise_create.restype = ctypes.c_void_p
        lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
                                              ctypes.POINTER(ctypes.c_float)]
        lib.rnnoise_process_frame.restype = ctypes.c_float
        _RNNOISE = lib
    return _RNNOISE


class PitchShifter:
    """Rubber Band R3 실시간 피치 시프터. 높이(semitones)와 음색(formant)을 따로 조절한다.

    pedalboard.PitchShift는 같은 라이브러리지만 오프라인 모드라 지연이 ~1초여서, 실시간 모드
    (짧은 창)를 직접 쓴다. 지연은 약 20~45ms. 출력 길이가 블록마다 조금씩 달라서 FIFO로 맞춘다.
    """

    def __init__(self, semitones: float = 0.0, formant: float | None = None, sample_rate: int = 48000):
        o = rb.Option
        self._st = rb.RubberBandStretcher(
            sample_rate, 1,
            o.PROCESS_REALTIME | o.ENGINE_FINER | o.WINDOW_SHORT | o.PitchHighConsistency | o.FORMANT_PRESERVED)
        self._semitones = float(semitones)
        # 음색(포먼트) 이동량(반음). None이면 높이를 따라간다 (다람쥐처럼 만화 같은 느낌)
        self._formant = self._semitones if formant is None else float(formant)
        self._apply()
        # 실시간 모드 권장 사용법: 앞에 무음을 채워 넣고, 그만큼의 시작 지연은 출력에서 버린다
        self._st.process(np.zeros((1, self._st.get_preferred_start_pad()), np.float32), False)
        self._discard = self._st.get_start_delay()
        self._fifo = np.zeros(0, np.float32)
        self._primed = False

    @property
    def semitones(self) -> float:
        return self._semitones

    @semitones.setter
    def semitones(self, value: float) -> None:
        self._semitones = float(value)
        self._apply()

    @property
    def formant(self) -> float:
        return self._formant

    @formant.setter
    def formant(self, value: float) -> None:
        self._formant = float(value)
        self._apply()

    def _apply(self) -> None:
        pitch = 2.0 ** (self._semitones / 12.0)
        self._st.pitch_scale = pitch
        # formant_scale은 피치 이동 후 신호 기준 비율 → 원래 목소리 기준 이동량으로 환산
        self._st.formant_scale = 2.0 ** (self._formant / 12.0) / pitch

    def process(self, x: np.ndarray, sample_rate: float, reset: bool = False) -> np.ndarray:
        n = x.shape[1]
        self._st.process(np.ascontiguousarray(x[:1]), False)
        avail = self._st.available()
        if avail > 0:
            y = self._st.retrieve(avail)[0]
            if self._discard:
                cut = min(self._discard, len(y))
                y, self._discard = y[cut:], self._discard - cut
            self._fifo = np.concatenate([self._fifo, y])
        # 블록 하나만큼 여유를 두고 내보내서, 출력이 조금 늦게 나오는 블록이 있어도 끊기지 않게 한다
        if not self._primed:
            if len(self._fifo) < 2 * n:
                return np.zeros_like(x)
            self._primed = True
        if len(self._fifo) < n:
            self._primed = False
            out = np.zeros(n, np.float32)
            out[:len(self._fifo)] = self._fifo
            self._fifo = self._fifo[:0]
        else:
            out, self._fifo = self._fifo[:n], self._fifo[n:]
        return np.repeat(out[None, :], x.shape[0], axis=0)

class NoiseSuppressor:
    """RNNoise 기반 마이크 잡음 제거 (48kHz, 480샘플 프레임). 지연 20ms.

    pyrnnoise의 고수준 함수는 int16으로 변환해 정밀도를 잃으므로 C 함수를 float 그대로 호출한다.
    strength < 1이면 같은 만큼 지연시킨 원본을 섞어서 억제 강도를 낮춘다.
    """

    FRAME = 480
    DELAY = 960  # RNNoise 고유 지연 (측정값)

    def __init__(self, strength: float = 1.0):
        self._lib = _rnnoise_lib()
        self._state = self._lib.rnnoise_create(None)
        self.strength = strength
        self._dry = np.zeros(self.DELAY, np.float32)

    def __del__(self):
        try:
            self._lib.rnnoise_destroy(self._state)
        except Exception:
            pass

    def process(self, x: np.ndarray, sample_rate: float, reset: bool = False) -> np.ndarray:
        mono = x[0]
        if len(mono) % self.FRAME:
            return x  # 엔진은 항상 480샘플 블록이라 실제로는 오지 않는다
        wet = np.empty_like(mono)
        ptr_t = ctypes.POINTER(ctypes.c_float)
        for i in range(0, len(mono), self.FRAME):
            frame = np.ascontiguousarray(mono[i:i + self.FRAME] * 32768.0, dtype=np.float32)
            p = frame.ctypes.data_as(ptr_t)
            self._lib.rnnoise_process_frame(self._state, p, p)
            wet[i:i + self.FRAME] = frame / 32768.0
        s = min(max(float(self.strength), 0.0), 1.0)
        buf = np.concatenate([self._dry, mono])
        dry, self._dry = buf[:len(mono)], buf[len(mono):]
        y = wet if s >= 1.0 else wet * s + dry * (1.0 - s)
        return np.repeat(y[None, :], x.shape[0], axis=0)

class RingModulator:
    """입력에 사인파를 곱해서 금속성/로봇 느낌을 준다."""

    def __init__(self, freq_hz: float = 50.0, mix: float = 1.0):
        self.freq_hz = freq_hz
        self.mix = mix
        self._phase = 0.0

    def process(self, x: np.ndarray, sample_rate: float, reset: bool = False) -> np.ndarray:
        if reset:
            self._phase = 0.0
        n = x.shape[1]
        inc = 2.0 * np.pi * self.freq_hz / sample_rate
        ph = self._phase + inc * np.arange(n)
        self._phase = float((ph[-1] + inc) % (2.0 * np.pi))
        mod = np.sin(ph).astype(np.float32)
        return x * (1.0 - self.mix) + x * mod * self.mix


class Gain:
    def __init__(self, gain: float = 1.0):
        self.gain = gain

    def process(self, x: np.ndarray, sample_rate: float, reset: bool = False) -> np.ndarray:
        return x * self.gain


def run_chain(chain: list, x: np.ndarray, sample_rate: float) -> np.ndarray:
    for stage in chain:
        x = stage.process(x, sample_rate, reset=False)
    return x
