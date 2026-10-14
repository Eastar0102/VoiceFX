"""기본 사운드보드 효과음 받기: freesound.org의 CC0(퍼블릭 도메인) 소리만 사용한다.

    python tools/fetch_default_sounds.py
원본 미리듣기(mp3)를 받아 앞뒤 무음 정리 → 길이 자르기 → 음량 맞추기 후
voicefx/assets/sounds/<키>.wav 로 저장하고, 출처를 voicefx/assets/sounds/CREDITS.md 에 기록한다.
CC0라 출처 표기 의무는 없지만 어디서 왔는지 남겨둔다.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import numpy as np
import pedalboard as pb
from pedalboard.io import AudioFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from voicefx.soundboard import DEFAULT_SOUNDS_DIR  # noqa: E402

SR = 48000
TARGET_RMS = 0.06  # 소리가 나는 구간 기준 평균 크기 (약 -24 dBFS). 목소리보다 살짝 작게
PEAK = 0.6
CACHE = ROOT / "tools" / ".freesound_cache"

# (키, 표시 이름, freesound ID, 사용자 ID, 원본 제목, 작성자, 최대 길이(초))
SOURCES = [
    ("airhorn", "에어혼", 414208, 6938106, "Airhorn", "jacksonacademyashmore", 3.0),
    ("rimshot", "바둠츠", 383898, 7146007, "Rimshot Joke Funny", "?", 3.2),
    ("sad_trombone", "슬픈 트롬본", 175409, 1326576, "wah wah sad trombone.wav", "?", 6.0),
    ("applause", "박수", 160493, 341440, "Large crowd applause.wav", "?", 4.0),
    ("crickets", "귀뚜라미", 129678, 2362707, "crickets", "?", 4.0),
    ("tada", "짜잔", 397355, 4284968, "Tada Fanfare A", "?", 3.0),
    ("correct", "정답", 421002, 7614679, "Correct.wav", "?", 2.0),
    ("buzzer", "땡", 54047, 533680, "buzzer.wav", "?", 2.0),
    ("drumroll", "드럼롤", 191718, 185249, "drumroll.wav", "?", 6.0),
    ("laugh", "관객 웃음", 383207, 2247456, "Sitcom Laughter 9x, Small Audience", "?", 2.8),
    ("scratch", "레코드 긁기", 43404, 465423, "record_scratch.wav", "?", 2.0),
    ("boing", "뿅", 161122, 2750714, "Cartoon Boing.wav", "?", 2.5),
    ("fall", "추락", 395443, 4284968, "Cartoon Fall", "?", 2.5),
    ("explosion", "폭발", 47252, 364925, "bad explosion", "?", 3.0),
]


def preview_url(sound_id: int, user_id: int) -> str:
    return f"https://cdn.freesound.org/previews/{sound_id // 1000}/{sound_id}_{user_id}-hq.mp3"


def download(sound_id: int, user_id: int) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{sound_id}.mp3"
    if not path.exists():
        req = urllib.request.Request(preview_url(sound_id, user_id), headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return path


def load(path: Path) -> np.ndarray:
    with AudioFile(str(path)).resampled_to(SR) as f:
        return f.read(f.frames).mean(axis=0).astype(np.float32)


def frame_rms(x: np.ndarray, n: int = 480) -> np.ndarray:
    x = x[: len(x) // n * n]
    return np.sqrt((x.reshape(-1, n) ** 2).mean(1)) if len(x) else np.zeros(1)


def process(x: np.ndarray, max_sec: float) -> np.ndarray:
    fr = frame_rms(x)
    thr = fr.max() * 0.03
    active = np.flatnonzero(fr > thr)
    start = max(0, active[0] * 480 - 480)  # 첫 소리 10ms 전부터
    end = min(len(x), (active[-1] + 1) * 480 + 2400)
    x = x[start:end]
    if len(x) > max_sec * SR:  # 길면 자르고 끝을 부드럽게 줄인다
        x = x[: int(max_sec * SR)]
        fade = int(0.4 * SR)
        x[-fade:] *= np.linspace(1, 0, fade) ** 2
    fade_in = 120
    x[:fade_in] *= np.linspace(0, 1, fade_in)
    # 무음 구간을 빼고, 소리가 나는 구간의 평균 크기로 맞춘다
    fr = frame_rms(x)
    loud = fr[fr > fr.max() * 0.1]
    x = x * (TARGET_RMS / (np.sqrt((loud ** 2).mean()) + 1e-9))
    x = pb.Pedalboard([pb.Limiter(threshold_db=20 * np.log10(PEAK), release_ms=60)])(x[None, :], SR)[0]
    x = x * (TARGET_RMS / (np.sqrt((frame_rms(x)[frame_rms(x) > frame_rms(x).max() * 0.1] ** 2).mean()) + 1e-9))
    return x / max(1.0, np.abs(x).max() / PEAK)


def main():
    DEFAULT_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    credits = ["# 기본 효과음 출처", "",
               "모두 freesound.org의 **Creative Commons 0 (퍼블릭 도메인)** 소리입니다. 길이와 음량만 손봤습니다.", "",
               "| 파일 | 이름 | 원본 |", "|---|---|---|"]
    for key, name, sid, uid, title, _author, max_sec in SOURCES:
        x = process(load(download(sid, uid)), max_sec)
        with AudioFile(str(DEFAULT_SOUNDS_DIR / f"{key}.wav"), "w", SR, 1) as f:
            f.write(x[None, :].astype(np.float32))
        credits.append(f"| {key}.wav | {name} | [{title}](https://freesound.org/s/{sid}/) |")
        print(f"{name:8} {len(x) / SR:4.1f}s  peak {np.abs(x).max():.2f}  ← freesound #{sid}")
    (DEFAULT_SOUNDS_DIR / "CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
