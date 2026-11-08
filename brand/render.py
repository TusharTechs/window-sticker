"""Rasterise the brand mark: uv run --with resvg-py --with pillow python brand/render.py"""

from io import BytesIO
from pathlib import Path

import resvg_py
from PIL import Image

HERE = Path(__file__).parent
WEB = HERE.parent / "web"


def png(svg: Path, size: int) -> Image.Image:
    data = resvg_py.svg_to_bytes(svg_string=svg.read_text(), width=size, height=size)
    return Image.open(BytesIO(bytes(data))).convert("RGBA")


def main() -> None:
    mark, dark = HERE / "mark.svg", HERE / "mark-dark.svg"
    png(mark, 1024).save(HERE / "mark-1024.png")
    png(dark, 1024).save(HERE / "mark-dark-1024.png")
    # Apple touch icon: the mark on paper, with breathing room (iOS adds its own corner mask).
    tile = Image.new("RGBA", (180, 180), "#f5f2ea")
    tile.alpha_composite(png(mark, 144), (18, 18))
    tile.convert("RGB").save(WEB / "src/app/apple-icon.png")
    # Classic favicon for browsers that ignore SVG icons.
    png(mark, 64).save(WEB / "src/app/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("ok")


if __name__ == "__main__":
    main()
