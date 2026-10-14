"""다국어 지원.

원문(한국어) 문장 자체를 키로 쓰는 gettext 방식: t("마이크 없음") → 현재 언어의 번역, 없으면 원문 그대로.
번역은 voicefx/locales/<언어>.json ({"원문": "번역"}). 화면(index.html)도 같은 표를 받아 쓴다.
빠진 번역 찾기: python tools/i18n_check.py
"""
from __future__ import annotations

import ctypes
import json
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
LANGUAGES = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "简体中文"}
SOURCE_LANG = "ko"

_current = SOURCE_LANG
_table: dict[str, str] = {}


def system_language() -> str:
    """Windows 표시 언어 → 지원 언어 코드 (없으면 영어)."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except Exception:
        return "en"
    return {0x12: "ko", 0x11: "ja", 0x04: "zh"}.get(primary, "en")


def set_language(code: str) -> str:
    """언어를 바꾼다. "auto"면 Windows 표시 언어를 따른다. 실제로 적용된 언어 코드를 돌려준다."""
    global _current, _table
    lang = system_language() if code in (None, "", "auto") else code
    if lang not in LANGUAGES:
        lang = "en"
    table = {}
    if lang != SOURCE_LANG:
        try:
            table = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            table = {}
    _current, _table = lang, table
    return lang


def current() -> str:
    return _current


def table() -> dict[str, str]:
    return _table


def t(text: str, **values) -> str:
    """원문을 현재 언어로. {이름} 자리는 values로 채운다."""
    out = _table.get(text) or text
    return out.format(**values) if values else out
