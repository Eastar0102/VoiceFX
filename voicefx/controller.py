"""UI와 무관한 앱 로직: 장치/프리셋/사운드보드/설정/단축키/기본 마이크 전환."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
import warnings
from pathlib import Path

import sounddevice as sd

from . import i18n, windefault
from .i18n import t
from .engine import AudioEngine, Device, list_devices
from .presets import MODULES_BY_KEY, PRESETS, Preset, custom_preset
from .soundboard import DEFAULT_SOUNDS_VERSION, SoundError, SoundLibrary

warnings.filterwarnings("ignore", module="pycaw")  # 일부 장치 속성 조회 경고

SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "VoiceFX" / "settings.json"
CABLE_PLAYBACK = "CABLE Input"   # 우리가 소리를 써넣는 쪽 (재생 장치)
CABLE_RECORDING = "CABLE Output"  # Discord가 마이크로 듣는 쪽 (녹음 장치)
VIRTUAL_HINTS = ("cable", "voicemod", "vb-audio")

DEFAULTS = {
    "language": "auto", "preset": "chipmunk", "voice_on": True, "monitor_on": False, "auto_default": True, "auto_cable": True,
    "gate": True, "noise_suppression": True, "ns_strength": 1.0, "input_gain": 1.0, "output_volume": 1.0, "monitor_volume": 0.8,
    "favorites": [], "favorites_on_top": True, "voice_params": {},
    # 내 목소리: [{key, name, icon, color, description, modules: [모듈 키]}] — 값은 voice_params에 저장
    "custom_voices": [],
    # 단축키는 기본값 없이 사용자가 직접 지정한다: {동작 id: "ctrl+shift+1"}
    # 동작 id: "voice:<프리셋>", "toggle:voice", "toggle:monitor", "sound:<id>", "sound:stop_all"
    "hotkeys": {},
    "sounds": [], "soundboard_volume": 1.0, "sound_monitor": True,
}


def restore_system_audio() -> None:
    """앱이 바꿔둔 Windows 기본 마이크·VB-CABLE 상태를 설정 파일 기록대로 되돌린다 (제거 프로그램용)."""
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    mic = settings.pop("restore_mic_id", None)
    ids = settings.pop("restore_disabled_ids", None) or []
    if not mic and not ids:
        return
    if mic:
        try:
            windefault.set_default_capture(mic)
        except Exception:
            pass
    for endpoint in ids:
        try:
            windefault.set_endpoint_enabled(endpoint, False)
        except Exception:
            pass
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _is_virtual(name: str) -> bool:
    return any(h in name.lower() for h in VIRTUAL_HINTS)


class Controller:
    def __init__(self):
        self.engine = AudioEngine()
        self.settings = {**DEFAULTS, **self._load()}
        i18n.set_language(self.settings["language"])
        self.error: str | None = None
        self._lock = threading.RLock()
        self._hotkeys_paused = False
        self._hotkey_handles: list = []
        self.sounds = SoundLibrary(SETTINGS_PATH.parent / "sounds", self.settings["sounds"])
        self._install_default_sounds()
        self.engine.soundboard_volume = float(self.settings["soundboard_volume"])
        self.engine.sound_monitor = bool(self.settings["sound_monitor"])
        self._restore_default_mic()  # 지난번에 비정상 종료됐다면 원래 마이크로 복구
        self.refresh_devices()
        for k in ("input_gain", "output_volume", "monitor_volume"):
            setattr(self.engine, k, float(self.settings[k]))
        self.engine.gate_enabled = bool(self.settings["gate"])
        self.engine.noise_suppression = bool(self.settings["noise_suppression"])
        self.engine.ns_strength = float(self.settings["ns_strength"])
        self.engine.monitor_enabled = bool(self.settings["monitor_on"])
        self._apply_preset()

    # ---------- 장치 ----------
    def refresh_devices(self) -> None:
        if not self.engine.running:
            # PortAudio는 시작 시점의 장치 목록을 캐시하므로 새로 켜진 장치를 보려면 재초기화해야 한다
            sd._terminate()
            sd._initialize()
        inputs, outputs = list_devices()
        # 같은 장치가 MME/DirectSound/WASAPI로 중복 노출되므로 지연이 가장 낮은 WASAPI만 쓴다
        self.inputs = [d for d in inputs if d.hostapi == "Windows WASAPI"] or inputs
        self.outputs = [d for d in outputs if d.hostapi == "Windows WASAPI"] or outputs
        s = self.settings
        names_in = [d.name for d in self.inputs]
        names_out = [d.name for d in self.outputs]
        if s.get("input") not in names_in:
            s["input"] = self._guess_mic()
        if s.get("output") not in names_out:
            s["output"] = next((n for n in names_out if CABLE_PLAYBACK.lower() in n.lower()), None)
        if s.get("monitor") not in names_out:
            s["monitor"] = self._default_speaker()

    def _guess_mic(self) -> str | None:
        real = [d.name for d in self.inputs if not _is_virtual(d.name)]
        default = windefault.get_default_capture_name()
        return default if default in real else (real[0] if real else None)

    def _default_speaker(self) -> str | None:
        try:
            api = next(i for i, a in enumerate(sd.query_hostapis()) if a["name"] == "Windows WASAPI")
            idx = sd.query_hostapis(api)["default_output_device"]
            name = sd.query_devices(idx)["name"]
            if not _is_virtual(name):
                return name
        except (StopIteration, sd.PortAudioError):
            pass
        return next((d.name for d in self.outputs if not _is_virtual(d.name)), None)

    def cable_status(self) -> str:
        """ok | disabled | missing"""
        if any(CABLE_PLAYBACK.lower() in d.name.lower() for d in self.outputs):
            return "ok"
        try:
            from pycaw.pycaw import AudioUtilities
            if any("vb-audio virtual cable" in (d.FriendlyName or "").lower()
                   for d in AudioUtilities.GetAllDevices()):
                return "disabled"
        except Exception:
            pass
        return "missing"

    def _find(self, devices: list[Device], name: str | None) -> Device | None:
        return next((d for d in devices if d.name == name), None)

    # ---------- 시작/정지 ----------
    def start(self) -> bool:
        with self._lock:
            self.error = None
            if self.settings["auto_cable"]:
                self._enable_cable()
            mic = self._find(self.inputs, self.settings.get("input"))
            out = self._find(self.outputs, self.settings.get("output"))
            mon = self._find(self.outputs, self.settings.get("monitor"))
            if mic is None:
                self.error = t("마이크를 찾을 수 없습니다. 설정에서 마이크를 선택하세요.")
                return False
            if out is None:
                self.error = t("가상 케이블(CABLE Input)이 없습니다. VB-CABLE을 켜거나 설치하세요.")
                return False
            try:
                self.engine.start(mic.index, out.index, mon.index if mon else None)
            except Exception as e:
                self.error = t("오디오 장치를 열 수 없습니다: {e}", e=e)
                return False
            if self.settings["auto_default"]:
                self._switch_default_mic()
            return True

    def stop(self) -> None:
        with self._lock:
            self.engine.stop()
            self._restore_default_mic()
            self._restore_cable()

    def restart(self) -> None:
        if self.engine.running:
            self.engine.stop()  # 기본 마이크는 그대로 둔 채 스트림만 다시 연다
            self.start()

    def shutdown(self) -> None:
        if getattr(self, "_shut_down", False):
            return
        self._shut_down = True
        self.save()
        self.stop()
        try:
            self._clear_hotkeys()
        except ImportError:
            pass

    # ---------- VB-CABLE 켜기/복구 ----------
    def _enable_cable(self) -> None:
        """'사용 안 함' 상태인 CABLE 장치를 켜고, 종료 시 다시 끌 수 있게 기록해 둔다."""
        try:
            targets = [i for i, name in windefault.list_disabled_endpoints()
                       if name.startswith((CABLE_PLAYBACK, CABLE_RECORDING))]
            if not targets:
                return
            pending = self.settings.setdefault("restore_disabled_ids", [])
            pending.extend(i for i in targets if i not in pending)
            self.save()  # 앱이 죽어도 다음 실행 후 종료할 때 되돌릴 수 있게 먼저 저장
            for i in targets:
                windefault.set_endpoint_enabled(i, True)
            for _ in range(15):  # 장치가 오디오 스택에 나타날 때까지 잠깐 기다린다
                time.sleep(0.2)
                self.refresh_devices()
                if self.cable_status() == "ok":
                    return
        except Exception as e:
            self.error = t("VB-CABLE을 켜지 못했습니다: {e}", e=e)

    def _restore_cable(self) -> None:
        ids = self.settings.pop("restore_disabled_ids", None)
        if not ids:
            return
        for i in ids:
            try:
                windefault.set_endpoint_enabled(i, False)
            except Exception:
                pass
        self.save()

    # ---------- 기본 마이크 ----------
    def _switch_default_mic(self) -> None:
        try:
            cable_id = windefault.find_capture_endpoint(CABLE_RECORDING)
            if cable_id is None:
                self.error = t("'CABLE Output' 녹음 장치가 없어 기본 마이크를 바꾸지 못했습니다.")
                return
            original = windefault.get_default_capture_id()
            if original and original != cable_id and "restore_mic_id" not in self.settings:
                # 복구용으로 먼저 저장 → 앱이 죽어도 다음 실행 때 되돌릴 수 있게
                self.settings["restore_mic_id"] = original
                self.save()
            windefault.set_default_capture(cable_id)
        except Exception as e:
            self.error = t("기본 마이크 전환 실패: {e}", e=e)

    def _restore_default_mic(self) -> None:
        original = self.settings.pop("restore_mic_id", None)
        if not original:
            return
        try:
            windefault.set_default_capture(original)
        except Exception:
            pass  # 장치가 사라졌으면 그냥 넘어간다
        self.save()

    # ---------- 프리셋/토글 ----------
    @property
    def presets(self) -> dict[str, Preset]:
        """기본 목소리 + 내 목소리 (키 → Preset)."""
        result = {p.key: p for p in PRESETS}
        for spec in self.settings["custom_voices"]:
            result[spec["key"]] = custom_preset(spec)
        return result

    def select_preset(self, key: str) -> None:
        if key in self.presets:
            self.settings["preset"] = key
            self.settings["voice_on"] = True
            self._apply_preset()

    def set_voice(self, on: bool) -> None:
        self.settings["voice_on"] = bool(on)
        self._apply_preset()

    def set_monitor(self, on: bool) -> None:
        self.settings["monitor_on"] = bool(on)
        self.engine.monitor_enabled = bool(on)

    def _active_key(self) -> str:
        key = self.settings["preset"] if self.settings["voice_on"] else "clean"
        return key if key in self.presets else PRESETS[0].key

    def _apply_preset(self) -> None:
        key = self._active_key()
        self.engine.set_preset(self.presets[key], self.settings["voice_params"].get(key))

    # ---------- 목소리별 세부 설정 ----------
    def param_values(self, key: str) -> dict[str, float]:
        return self.presets[key].values(self.settings["voice_params"].get(key))

    def set_param(self, key: str, param_key: str, value: float) -> None:
        preset = self.presets.get(key)
        param = preset and preset.param(param_key)
        if not param:
            return
        value = min(max(float(value), param.min), param.max)
        self.settings["voice_params"].setdefault(key, {})[param_key] = value
        self.engine.set_param(key, param.stage, param.attr, value)  # 다른 목소리면 엔진이 무시
        self._save_throttled()

    def reset_params(self, key: str) -> dict[str, float]:
        if key in self.presets:
            self.settings["voice_params"].pop(key, None)
            if key == self._active_key():
                self._apply_preset()
            self.save()
        return self.param_values(key)

    # ---------- 내 목소리 ----------
    def _custom_spec(self, key: str) -> dict | None:
        return next((s for s in self.settings["custom_voices"] if s["key"] == key), None)

    def create_custom(self, base_key: str | None = None) -> str:
        """새 내 목소리를 만든다. base_key가 있으면 그 목소리의 모듈과 현재 값을 그대로 복사한다."""
        base = self.presets.get(base_key) if base_key else None
        key = "custom_" + uuid.uuid4().hex[:8]
        if base:
            name = t("{name} 복사본", name=base.name) if base.custom else t("내 {name}", name=t(base.name))
            spec = {"key": key, "name": name[:30], "icon": base.icon, "color": base.color,
                    "description": t(base.description), "modules": base.modules}
            self.settings["voice_params"][key] = dict(self.param_values(base.key))
        else:
            n = len(self.settings["custom_voices"]) + 1
            spec = {"key": key, "name": t("내 목소리 {n}", n=n), "icon": "🎛️", "color": "#7c5cff",
                    "description": t("내가 만든 목소리"), "modules": ["pitch"]}
        self.settings["custom_voices"].append(spec)
        self.select_preset(key)
        self.save()
        return key

    def update_custom(self, key: str, field: str, value) -> None:
        spec = self._custom_spec(key)
        if spec is None or field not in ("name", "icon", "color", "description"):
            return
        value = str(value).strip()
        if value:
            spec[field] = value[:30] if field == "name" else value[:80]
        self.save()

    def set_custom_module(self, key: str, module: str, enabled: bool) -> None:
        """내 목소리의 효과 모듈을 켜고 끈다. 단계 구성이 바뀌므로 체인을 다시 만든다."""
        spec = self._custom_spec(key)
        if spec is None or module not in MODULES_BY_KEY:
            return
        mods = [m for m in spec["modules"] if m != module]
        if enabled:
            mods.append(module)
        else:  # 끈 모듈의 값은 지운다 (다시 켜면 기본값부터)
            values = self.settings["voice_params"].get(key, {})
            for k in [k for k in values if k.startswith(module + ".")]:
                del values[k]
        spec["modules"] = mods
        if key == self._active_key():
            self._apply_preset()
        self.save()

    def delete_custom(self, key: str) -> None:
        spec = self._custom_spec(key)
        if spec is None:
            return
        self.settings["custom_voices"].remove(spec)
        self.settings["voice_params"].pop(key, None)
        if key in self.settings["favorites"]:
            self.settings["favorites"].remove(key)
        if self.settings["hotkeys"].pop(f"voice:{key}", None):
            self.apply_hotkeys()
        if self.settings["preset"] == key:
            self.settings["preset"] = PRESETS[0].key
            self._apply_preset()
        self.save()

    def _save_throttled(self) -> None:
        # 슬라이더를 끄는 동안 초당 수십 번 호출되므로 파일 쓰기는 0.5초에 한 번만
        if time.monotonic() - getattr(self, "_last_save", 0.0) > 0.5:
            self.save()
            self._last_save = time.monotonic()

    def toggle_favorite(self, key: str) -> None:
        favs = self.settings["favorites"]
        if key in favs:
            favs.remove(key)
        else:
            favs.append(key)
        self.save()

    def set_option(self, key: str, value) -> None:
        s = self.settings
        if key in ("input_gain", "output_volume", "monitor_volume", "ns_strength"):
            s[key] = float(value)
            setattr(self.engine, key, float(value))
        elif key == "gate":
            s[key] = self.engine.gate_enabled = bool(value)
        elif key == "noise_suppression":
            s[key] = self.engine.noise_suppression = bool(value)
        elif key == "language":
            s[key] = value if value in ("auto", *i18n.LANGUAGES) else "auto"
            i18n.set_language(s[key])
        elif key in ("auto_cable", "favorites_on_top"):
            s[key] = bool(value)
        elif key == "soundboard_volume":
            s[key] = self.engine.soundboard_volume = float(value)
        elif key == "sound_monitor":
            s[key] = self.engine.sound_monitor = bool(value)
        elif key == "auto_default":
            s[key] = bool(value)
            if self.engine.running:
                self._switch_default_mic() if value else self._restore_default_mic()
        elif key in ("input", "output", "monitor"):
            s[key] = value
            self.restart()
        self.save()

    # ---------- 사운드보드 ----------
    def add_sounds(self, paths: list[str]) -> dict:
        added, errors = [], []
        for path in paths:
            try:
                added.append(self.sounds.add(path))
            except (SoundError, OSError) as e:
                errors.append(f"{Path(path).name}: {e}")
        if added:
            self.save()
        return {"added": [e["id"] for e in added], "errors": errors}

    def _install_default_sounds(self) -> None:
        """첫 실행 때 기본 효과음을 넣고, 기본 효과음 세트가 바뀌었으면 예전 것을 새것으로 교체한다."""
        s = self.settings
        installed = s.get("default_sounds_version", 1 if s.get("default_sounds_installed") else 0)
        if installed >= DEFAULT_SOUNDS_VERSION:
            return
        try:
            if installed:
                for sound_id in self.sounds.remove_defaults():
                    s["hotkeys"].pop(f"sound:{sound_id}", None)
            self.sounds.add_defaults()
        except (SoundError, OSError):
            pass
        s.pop("default_sounds_installed", None)
        s["default_sounds_version"] = DEFAULT_SOUNDS_VERSION
        self.save()

    def restore_default_sounds(self) -> int:
        added = self.sounds.add_defaults()
        if added:
            self.save()
        return len(added)

    def play_sound(self, sound_id: str, toggle: bool = False) -> str | None:
        """재생 (toggle이면 재생 중일 때 정지). 문제가 있으면 오류 메시지를 돌려준다."""
        if not self.engine.running:
            return t("VoiceFX가 꺼져 있어 사운드를 재생할 수 없습니다. 먼저 켜 주세요.")
        if toggle and sound_id in self.engine.sound_progress:
            self.engine.stop_sound(sound_id)
            return None
        entry = self.sounds.get(sound_id)
        data = self.sounds.data(sound_id)
        if entry is None or data is None:
            return t("사운드 파일을 읽을 수 없습니다.")
        self.engine.play_sound(sound_id, data, float(entry["volume"]))
        return None

    def stop_all_sounds(self) -> None:
        self.engine.stop_all_sounds()

    def update_sound(self, sound_id: str, field: str, value) -> dict | None:
        entry = self.sounds.update(sound_id, field, value)
        if entry and field == "volume":
            self.engine.set_sound_volume(sound_id, entry["volume"])
        self._save_throttled() if field == "volume" else self.save()
        return entry

    def remove_sound(self, sound_id: str) -> None:
        self.engine.stop_sound(sound_id)
        self.sounds.remove(sound_id)
        if self.settings["hotkeys"].pop(f"sound:{sound_id}", None):
            self.apply_hotkeys()
        self.save()

    # ---------- 단축키 ----------
    def set_hotkey(self, action: str, combo: str | None) -> str | None:
        """단축키 지정/해제. 같은 조합을 쓰던 다른 동작이 있으면 그 동작 id를 돌려준다 (자동 해제됨)."""
        hotkeys = self.settings["hotkeys"]
        moved_from = None
        if combo:
            combo = combo.lower()
            moved_from = next((a for a, k in hotkeys.items() if k == combo and a != action), None)
            if moved_from:
                del hotkeys[moved_from]
            hotkeys[action] = combo
        else:
            hotkeys.pop(action, None)
        self.apply_hotkeys()
        self.save()
        return moved_from

    def pause_hotkeys(self, paused: bool) -> None:
        """단축키 입력 칸에서 키를 누르는 동안 기존 단축키가 실행되지 않게 한다."""
        self._hotkeys_paused = bool(paused)

    def apply_hotkeys(self) -> str | None:
        try:
            import keyboard
        except ImportError:
            return t("keyboard 모듈이 없어 단축키를 쓸 수 없습니다.")
        self._clear_hotkeys()
        failed = []
        for action, combo in list(self.settings["hotkeys"].items()):
            try:
                self._hotkey_handles.append(keyboard.add_hotkey(combo, lambda a=action: self._on_hotkey(a)))
            except Exception:
                failed.append(combo)
        return t("단축키 등록 실패: {keys}", keys=", ".join(failed)) if failed else None

    def _clear_hotkeys(self) -> None:
        # keyboard.unhook_all_hotkeys()는 리스너가 아직 없을 때 예외를 던지므로 직접 등록한 것만 해제
        import keyboard
        for handle in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._hotkey_handles = []

    def _on_hotkey(self, action: str) -> None:
        if self._hotkeys_paused:
            return
        kind, _, arg = action.partition(":")
        if kind == "voice":
            self.select_preset(arg)
        elif action == "toggle:voice":
            self.set_voice(not self.settings["voice_on"])
        elif action == "toggle:monitor":
            self.set_monitor(not self.settings["monitor_on"])
        elif action == "sound:stop_all":
            self.stop_all_sounds()
        elif kind == "sound":
            self.play_sound(arg)
    # ---------- 기타 ----------
    @staticmethod
    def open_sound_settings() -> None:
        subprocess.Popen(["control", "mmsys.cpl,,1"])  # 소리 설정 → 녹음 탭

    def _load(self) -> dict:
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self) -> None:
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
