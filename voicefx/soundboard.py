"""사운드보드 파일 관리: 추가(앱 폴더로 복사), 디코딩/캐시, 이름·볼륨·즐겨찾기, 삭제.

메타데이터는 설정의 "sounds" 목록에 저장하고, 오디오 파일은 sounds/ 폴더에 보관한다.
"""
from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

import numpy as np
from pedalboard.io import AudioFile

from .engine import SAMPLE_RATE
from .i18n import t

AUDIO_EXTS = (".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif")

# 앱에 포함된 기본 효과음: freesound.org의 CC0 소리 (tools/fetch_default_sounds.py, 출처는 CREDITS.md)
DEFAULT_SOUNDS_DIR = Path(__file__).resolve().parent / "assets" / "sounds"
DEFAULT_SOUNDS_VERSION = 2  # 1 = 예전 합성 효과음
DEFAULT_SOUNDS = [
    ("airhorn", "에어혼"), ("rimshot", "바둠츠"), ("sad_trombone", "슬픈 트롬본"), ("applause", "박수"),
    ("crickets", "귀뚜라미"), ("tada", "짜잔"), ("correct", "정답"), ("buzzer", "땡"),
    ("drumroll", "드럼롤"), ("laugh", "관객 웃음"), ("scratch", "레코드 긁기"), ("boing", "뿅"),
    ("fall", "추락"), ("explosion", "폭발"),
]
MAX_SECONDS = 180
MAX_BYTES = 50 * 1024 * 1024


class SoundError(Exception):
    pass


def decode(path: Path) -> np.ndarray:
    """오디오 파일 → mono float32 48kHz."""
    try:
        with AudioFile(str(path)).resampled_to(SAMPLE_RATE) as f:
            if f.frames > MAX_SECONDS * SAMPLE_RATE:
                raise SoundError(t("{n}분 이하 파일만 넣을 수 있습니다", n=MAX_SECONDS // 60))
            audio = f.read(f.frames)
    except SoundError:
        raise
    except Exception as e:
        raise SoundError(t("읽을 수 없는 오디오 파일입니다 ({err})", err=e.__class__.__name__)) from e
    data = audio.mean(axis=0).astype(np.float32)
    peak = float(np.abs(data).max()) if len(data) else 0.0
    if peak > 1.0:
        data /= peak
    return data


class SoundLibrary:
    def __init__(self, folder: Path, entries: list[dict]):
        self.folder = folder
        self.entries = entries  # 설정의 "sounds" 목록을 그대로 공유 (수정이 곧 저장 대상)
        self._cache: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()
        # 첫 재생이 늦지 않도록 미리 디코딩
        threading.Thread(target=self._preload, daemon=True).start()

    def get(self, sound_id: str) -> dict | None:
        return next((e for e in self.entries if e["id"] == sound_id), None)

    def data(self, sound_id: str) -> np.ndarray | None:
        with self._lock:
            if sound_id in self._cache:
                return self._cache[sound_id]
        entry = self.get(sound_id)
        if entry is None:
            return None
        try:
            data = decode(self.folder / entry["file"])
        except SoundError:
            return None
        with self._lock:
            self._cache[sound_id] = data
        return data

    def add(self, path: str) -> dict:
        src = Path(path)
        if src.suffix.lower() not in AUDIO_EXTS:
            raise SoundError(t("지원하지 않는 형식입니다 ({exts})", exts=", ".join(AUDIO_EXTS)))
        if not src.is_file():
            raise SoundError(t("파일을 찾을 수 없습니다"))
        if src.stat().st_size > MAX_BYTES:
            raise SoundError(t("50MB 이하 파일만 넣을 수 있습니다"))
        data = decode(src)  # 복사 전에 재생 가능한지 확인
        sound_id = uuid.uuid4().hex[:10]
        self.folder.mkdir(parents=True, exist_ok=True)
        dest = self.folder / f"{sound_id}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        entry = {"id": sound_id, "name": src.stem[:40], "file": dest.name, "volume": 1.0,
                 "favorite": False, "duration": round(len(data) / SAMPLE_RATE, 2)}
        with self._lock:
            self._cache[sound_id] = data
        self.entries.append(entry)
        return entry

    def add_defaults(self) -> list[dict]:
        """기본 효과음 중 아직 없는 것만 추가한다 (지웠던 것 복원에도 쓴다)."""
        have = {e.get("default") for e in self.entries}
        added = []
        for key, name in DEFAULT_SOUNDS:
            path = DEFAULT_SOUNDS_DIR / f"{key}.wav"
            if key in have or not path.is_file():
                continue
            entry = self.add(str(path))
            entry["name"] = name
            entry["default"] = key
            added.append(entry)
        return added

    def remove_defaults(self) -> list[str]:
        """기본 효과음으로 추가된 항목을 모두 지운다 (기본 효과음 교체용). 지운 id 목록을 돌려준다."""
        ids = [e["id"] for e in self.entries if e.get("default")]
        for sound_id in ids:
            self.remove(sound_id)
        return ids

    def remove(self, sound_id: str) -> None:
        entry = self.get(sound_id)
        if entry is None:
            return
        self.entries.remove(entry)
        with self._lock:
            self._cache.pop(sound_id, None)
        try:
            (self.folder / entry["file"]).unlink()
        except OSError:
            pass

    def update(self, sound_id: str, field: str, value) -> dict | None:
        entry = self.get(sound_id)
        if entry is None:
            return None
        if field == "name":
            entry["name"] = str(value).strip()[:40] or entry["name"]
        elif field == "volume":
            entry["volume"] = min(max(float(value), 0.0), 2.0)
        elif field == "favorite":
            entry["favorite"] = bool(value)
        return entry

    def _preload(self) -> None:
        for e in list(self.entries):
            self.data(e["id"])
