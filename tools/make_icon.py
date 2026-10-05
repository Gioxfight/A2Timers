"""Draw assets/icon.ico (stopwatch on a dark rounded square). Requires Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
SIZE = 512
BG = (20, 22, 28, 255)
RING = (216, 220, 230, 255)
GREEN = (74, 222, 128, 255)
ORANGE = (251, 146, 60, 255)


def draw() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=110, fill=BG)
    cx, cy, r = SIZE // 2, SIZE // 2 + 24, 150
    d.rounded_rectangle((cx - 34, cy - r - 70, cx + 34, cy - r - 30), radius=12, fill=RING)  # crown
    d.rectangle((cx - 14, cy - r - 34, cx + 14, cy - r + 4), fill=RING)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=RING, width=30)
    d.pieslice((cx - r + 40, cy - r + 40, cx + r - 40, cy + r - 40), start=-90, end=30, fill=GREEN)
    d.line((cx, cy, cx, cy - r + 58), fill=ORANGE, width=22)
    d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=ORANGE)
    return img


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw().resize((256, 256), Image.LANCZOS).save(OUT.with_suffix(".png"))
    print(f"Icon written to {OUT}")


if __name__ == "__main__":
    main()
