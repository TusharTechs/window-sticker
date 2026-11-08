"""Render the Open Graph card for link previews (web/public/og.png).

uv run --with pillow python tools/make_og.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / "web/public/og.png"
INK, PAPER, YELLOW, MUTED = "#0f1216", "#f6f3ec", "#ffd400", "#9aa4b2"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    names = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for candidate in names:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, filled: bool) -> None:
    import math

    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=YELLOW if filled else None, outline=YELLOW if filled else MUTED, width=3)


def main() -> None:
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img)
    # Hazard stripe along the top.
    for x in range(-40, w + 40, 40):
        d.polygon([(x, 0), (x + 20, 0), (x + 40, 18), (x + 20, 18)], fill=YELLOW)
    d.text((80, 80), "WINDOW STICKER", fill=YELLOW, font=font(34, bold=True))
    d.text((80, 150), "Every AI agent should ship", fill=PAPER, font=font(66, bold=True))
    d.text((80, 230), "with a crash-test rating.", fill=PAPER, font=font(66, bold=True))
    for i in range(5):
        star(d, 112 + i * 72, 380, 30, i < 4)
    d.text(
        (80, 450),
        "Dozens of runs per agent, each in its own microVM on Vultr,",
        fill=MUTED,
        font=font(30),
    )
    d.text(
        (80, 492),
        "against published traps. Stars from exact 95% intervals.",
        fill=MUTED,
        font=font(30),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
