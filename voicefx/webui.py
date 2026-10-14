"""pywebview 기반 GUI. 화면은 ui/index.html, 로직은 Controller."""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from . import __version__, i18n
from .i18n import t
from .controller import Controller
from .presets import MODULES, Preset
from .soundboard import AUDIO_EXTS, DEFAULT_SOUNDS

UI_DIR = Path(__file__).resolve().parent / "ui"


class Api:
    """JS에서 window.pywebview.api.* 로 호출. (pywebview가 공개 속성을 순회하므로 내부 객체는 _ 접두사)"""

    def __init__(self, controller: Controller):
        self._c = controller
        self._window: webview.Window | None = None
        self._hotkey_error: str | None = None

    def _voice(self, p: Preset) -> dict:
        tr = (lambda s: s) if p.custom else t
        return {"key": p.key, "name": tr(p.name), "icon": p.icon, "color": p.color, "category": p.category,
                "description": tr(p.description), "custom": p.custom, "modules": p.modules,
                "params": [{"key": q.key, "label": t(q.label), "min": q.min, "max": q.max, "step": q.step,
                            "default": q.default, "unit": q.unit, "module": q.module} for q in p.panel_params],
                "values": self._c.param_values(p.key)}

    def voices(self) -> list:
        return [self._voice(p) for p in self._c.presets.values()]

    def init(self) -> dict:
        return {
            "presets": self.voices(),
            "modules": [{"key": m.key, "label": t(m.label), "icon": m.icon, "description": t(m.description)}
                        for m in MODULES],
            "i18n": {"lang": i18n.current(), "strings": i18n.table(), "languages": i18n.LANGUAGES},
            "sounds": self.sounds(),
            "version": __version__,
            **self.devices(),
            **self.state(),
        }

    def devices(self) -> dict:
        c = self._c
        return {"inputs": [d.name for d in c.inputs], "outputs": [d.name for d in c.outputs]}

    def state(self) -> dict:
        c = self._c
        s = c.settings
        return {
            "running": c.engine.running,
            "error": c.error or self._hotkey_error,
            "cable": c.cable_status(),
            "settings": {k: s.get(k) for k in (
                "language", "preset", "voice_on", "monitor_on", "auto_cable", "auto_default", "gate", "noise_suppression",
                "ns_strength", "input_gain",
                "output_volume", "monitor_volume", "favorites", "favorites_on_top", "hotkeys",
                "soundboard_volume", "sound_monitor", "input", "output", "monitor")},
        }

    def poll(self) -> dict:
        """화면이 주기적으로 호출: 레벨 미터, 사운드 재생 진행률, 단축키로 바뀐 상태."""
        c = self._c
        s = c.settings
        return {"level_in": c.engine.level_in, "level_out": c.engine.level_out,
                "preset": s["preset"], "voice_on": s["voice_on"], "monitor_on": s["monitor_on"],
                "playing": dict(c.engine.sound_progress),
                "running": c.engine.running, "error": c.error or self._hotkey_error}

    # ---------- 목소리 ----------
    def select_preset(self, key: str) -> None:
        self._c.select_preset(key)

    def set_voice(self, on: bool) -> None:
        self._c.set_voice(on)

    def set_monitor(self, on: bool) -> None:
        self._c.set_monitor(on)

    def set_param(self, key: str, param_key: str, value: float) -> None:
        self._c.set_param(key, param_key, value)

    def reset_params(self, key: str) -> dict:
        return self._c.reset_params(key)

    # ---------- 내 목소리 ----------
    def create_custom(self, base_key: str | None = None) -> dict:
        key = self._c.create_custom(base_key)
        return {"key": key, "presets": self.voices()}

    def update_custom(self, key: str, field: str, value) -> list:
        self._c.update_custom(key, field, value)
        return self.voices()

    def set_custom_module(self, key: str, module: str, enabled: bool) -> list:
        self._c.set_custom_module(key, module, enabled)
        return self.voices()

    def delete_custom(self, key: str) -> dict:
        self._c.delete_custom(key)
        return {"presets": self.voices(), **self.state()}

    def toggle_favorite(self, key: str) -> list:
        self._c.toggle_favorite(key)
        return self._c.settings["favorites"]

    # ---------- 사운드보드 ----------
    def sounds(self) -> list:
        # 기본 효과음은 이름을 바꾸지 않았다면 현재 언어로 보여준다
        return [self._sound_view(e) for e in self._c.settings["sounds"]]

    @staticmethod
    def _sound_view(e: dict | None) -> dict | None:
        if e and e.get("default") and e.get("name") == dict(DEFAULT_SOUNDS).get(e["default"]):
            return {**e, "name": t(e["name"])}
        return e

    def add_sounds_dialog(self) -> dict:
        patterns = ";".join(f"*{e}" for e in AUDIO_EXTS)
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=(t("오디오 파일 ({patterns})", patterns=patterns), t("모든 파일") + " (*.*)"))
        if not paths:
            return {"added": [], "errors": [], "sounds": self.sounds()}
        return self._add(list(paths))

    def _add(self, paths: list[str]) -> dict:
        result = self._c.add_sounds(paths)
        return {**result, "sounds": self.sounds()}

    def restore_default_sounds(self) -> dict:
        return {"added": self._c.restore_default_sounds(), "sounds": self.sounds()}

    def play_sound(self, sound_id: str) -> str | None:
        return self._c.play_sound(sound_id, toggle=True)

    def stop_all_sounds(self) -> None:
        self._c.stop_all_sounds()

    def update_sound(self, sound_id: str, field: str, value) -> dict | None:
        return self._sound_view(self._c.update_sound(sound_id, field, value))

    def remove_sound(self, sound_id: str) -> dict:
        self._c.remove_sound(sound_id)
        return {"sounds": self.sounds(), "hotkeys": self._c.settings["hotkeys"]}

    # ---------- 단축키 ----------
    def set_hotkey(self, action: str, combo: str | None) -> dict:
        moved_from = self._c.set_hotkey(action, combo)
        return {"hotkeys": self._c.settings["hotkeys"], "moved_from": moved_from}

    def pause_hotkeys(self, paused: bool) -> None:
        self._c.pause_hotkeys(paused)

    # ---------- 설정/기타 ----------
    def set_option(self, key: str, value) -> dict:
        self._c.set_option(key, value)
        return self.state()

    def toggle_power(self) -> dict:
        if self._c.engine.running:
            self._c.stop()
        else:
            self._c.start()
        return self.state()

    def refresh_devices(self) -> dict:
        self._c.refresh_devices()
        if not self._c.engine.running:
            self._c.start()
        return {**self.devices(), **self.state()}

    def open_sound_settings(self) -> None:
        self._c.open_sound_settings()

    def open_cable_download(self) -> None:
        webbrowser.open("https://vb-audio.com/Cable/")

    # ---------- 파일 끌어다 놓기 ----------
    def _on_drop(self, event: dict) -> None:
        # 브라우저 JS는 보안상 실제 경로를 못 보므로 pywebview가 넘겨주는 전체 경로를 쓴다
        files = (event.get("dataTransfer") or {}).get("files") or []
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if not paths:
            return
        result = self._add(paths)
        self._window.evaluate_js(f"window.onSoundsDropped({json.dumps(result, ensure_ascii=False)})")


def main() -> None:
    controller = Controller()
    api = Api(controller)
    api._hotkey_error = controller.apply_hotkeys()
    controller.start()  # Voicemod처럼 실행하자마자 적용
    window = webview.create_window(
        "VoiceFX", str(UI_DIR / "index.html"), js_api=api,
        width=1180, height=740, min_size=(940, 580), background_color="#0f1117",
    )
    api._window = window

    def on_loaded():
        window.dom.document.events.drop += DOMEventHandler(api._on_drop, prevent_default=True, stop_propagation=True)

    window.events.loaded += on_loaded
    webview.start()
    controller.shutdown()  # 창이 닫히면 여기서 마이크·VB-CABLE 복구까지 끝낸 뒤 종료한다
