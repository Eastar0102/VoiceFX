"""실행 진입점: 로그 설정, 중복 실행 방지, `--restore`(제거 프로그램용) 처리 후 GUI를 띄운다.

    VoiceFX.exe            앱 실행 (이미 켜져 있으면 기존 창을 앞으로)
    VoiceFX.exe --restore  켜져 있는 VoiceFX를 닫고 기본 마이크·VB-CABLE을 원래대로 되돌린 뒤 종료
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "VoiceFX"
LOG_PATH = APP_DIR / "voicefx.log"
MUTEX_NAME = "Local\\VoiceFX-SingleInstance"
WINDOW_TITLE = "VoiceFX"
ERROR_ALREADY_EXISTS = 183

log = logging.getLogger("voicefx")


def _setup_logging() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # 콘솔 없는 EXE에서는 stdout/stderr가 None이라, 무언가 출력하는 라이브러리가 죽지 않도록 로그로 돌린다
    if sys.stdout is None or sys.stderr is None:
        stream = open(LOG_PATH.with_suffix(".out.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    sys.excepthook = lambda *exc: log.critical("처리되지 않은 오류", exc_info=exc)
    threading.excepthook = lambda a: log.error("스레드 오류 (%s)", a.thread, exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def _find_window() -> int:
    return ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)


def _focus_existing() -> None:
    hwnd = _find_window()
    if hwnd:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)


def _app_running() -> bool:
    """다른 VoiceFX가 실행 중인지: 실행 중인 앱이 잡고 있는 뮤텍스가 있는지 본다."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False


def _restore() -> None:
    """제거 프로그램이 부른다: 실행 중인 앱을 정상 종료시키고(종료 시 스스로 복구), 남은 설정이 있으면 직접 복구."""
    hwnd = _find_window()
    if hwnd:
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    # 창이 닫힌 뒤에도 앱은 마이크 복구 등 정리를 하므로, 프로세스가 완전히 끝날 때까지(뮤텍스가 풀릴 때까지) 기다린다.
    # 그래야 제거 프로그램이 사용 중인 파일 때문에 지우지 못하는 일이 없다.
    for _ in range(150):
        if not _app_running():
            break
        time.sleep(0.1)
    from .controller import restore_system_audio
    restore_system_audio()


def main() -> None:
    _setup_logging()
    if "--restore" in sys.argv:
        log.info("--restore 실행")
        _restore()
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _focus_existing()
        return
    log.info("VoiceFX %s 시작 (frozen=%s)", __version__, getattr(sys, "frozen", False))
    try:
        from .webui import main as run_gui
        run_gui()
    except Exception:
        log.exception("실행 중 오류")
        from .i18n import t
        ctypes.windll.user32.MessageBoxW(
            None, t("VoiceFX 실행 중 오류가 발생했습니다.\n자세한 내용: {path}", path=LOG_PATH), "VoiceFX", 0x10)
        raise
    # 뮤텍스는 직접 풀지 않는다: 프로세스가 완전히 끝날 때 Windows가 풀어 주므로,
    # --restore(제거 프로그램)가 "정리까지 다 끝났는지"를 이것으로 판단할 수 있다.
    _keep = mutex  # noqa: F841
