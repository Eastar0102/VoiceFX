"""프리셋 튜닝 도구: 내 목소리를 모든 프리셋에 통과시켜 wav로 저장한다.

    python tools/render_presets.py --record 5        # 마이크로 5초 녹음해서 사용
    python tools/render_presets.py my_voice.wav      # 기존 파일 사용
결과는 out/<프리셋>.wav. 실시간과 똑같이 10ms 블록 단위로 처리한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from pedalboard.io import AudioFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from voicefx.dsp import run_chain  # noqa: E402
from voicefx.engine import BLOCK, SAMPLE_RATE  # noqa: E402
from voicefx.presets import PRESETS  # noqa: E402


def load(path: str) -> np.ndarray:
    with AudioFile(path).resampled_to(SAMPLE_RATE) as f:
        audio = f.read(f.frames)
    return audio.mean(axis=0, keepdims=True).astype(np.float32)


def record(seconds: float) -> np.ndarray:
    import sounddevice as sd
    print(f"{seconds}초 녹음 시작... 말해보세요")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return audio.T.copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", help="입력 오디오 파일")
    ap.add_argument("--record", type=float, metavar="SEC", help="마이크로 녹음할 초")
    ap.add_argument("--out", default="out")
    ap.add_argument("--only", help="이 프리셋 키만 렌더링 (쉼표 구분)")
    args = ap.parse_args()

    if args.record:
        x = record(args.record)
    elif args.input:
        x = load(args.input)
    else:
        ap.error("입력 파일 또는 --record 가 필요합니다")

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    with AudioFile(str(out_dir / "_input.wav"), "w", SAMPLE_RATE, 1) as f:
        f.write(x)
    for p in PRESETS:
        if only and p.key not in only:
            continue
        chain = p.build()
        y = np.concatenate([run_chain(chain, x[:, i:i + BLOCK], SAMPLE_RATE)
                            for i in range(0, x.shape[1], BLOCK)], axis=1)
        y = np.clip(y, -1.0, 1.0)
        with AudioFile(str(out_dir / f"{p.key}.wav"), "w", SAMPLE_RATE, 1) as f:
            f.write(y)
        print(f"{p.name:6} → {out_dir / (p.key + '.wav')}")


if __name__ == "__main__":
    main()
