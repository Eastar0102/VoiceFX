"""앱 아이콘 생성: 화면 로고와 같은 디자인 (보라→하늘 그라디언트 둥근 사각형 + 음파 막대).

    python tools/make_icon.py   → voicefx/assets/icon.ico (16~256px), icon.png (README용)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "voicefx" / "assets" / "icon.ico"
S = 1024  # 크게 그린 뒤 줄여서 계단 현상 없이


def main():
    grad = Image.new("RGBA", (S, S))
    a, b = (124, 92, 255), (34, 211, 238)  # 화면의 --accent, --accent-2
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.23), fill=255)
    icon = Image.new("RGBA", (S, S))
    icon.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(icon)
    bars = [0.18, 0.40, 0.66, 0.40, 0.18]  # 로고의 음파 막대 높이 비율
    w, gap = S * 0.085, S * 0.075
    x0 = (S - (len(bars) * w + (len(bars) - 1) * gap)) / 2
    for i, h in enumerate(bars):
        x = x0 + i * (w + gap)
        d.rounded_rectangle((x, S / 2 - h * S / 2, x + w, S / 2 + h * S / 2), radius=w / 2, fill="white")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    icon.save(OUT, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.resize((256, 256), Image.LANCZOS).save(OUT.with_suffix(".png"))  # README용
    print("saved", OUT)


if __name__ == "__main__":
    main()
