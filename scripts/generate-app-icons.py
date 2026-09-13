#!/usr/bin/env python3
"""Regenera iconos de menú: emblema circular en canvas cuadrado (~8% margen)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "media" / "FullLogo_Transparent.png"
OUT = ROOT / "packaging" / "icons"
SIZES = (32, 48, 64, 128, 256)
PAD_FRAC = 0.08


def _row_span(px, width: int, y: int, thr: int = 10) -> tuple[int, int, int] | None:
    xs = [x for x in range(width) if px[x, y][3] > thr]
    if not xs:
        return None
    return xs[0], xs[-1], xs[-1] - xs[0] + 1


def emblem_from_full_logo(logo: Image.Image) -> Image.Image:
    """Recorta el sello circular (sin wordmark LIVE CAPTIONS / VOX)."""
    rgba = logo.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    content_rows = [y for y in range(h) if _row_span(px, w, y)]
    if not content_rows:
        raise SystemExit(f"sin píxeles opacos en {SRC}")

    top, bottom = content_rows[0], content_rows[-1]
    circle_ref = 0
    for y in range(top, min(bottom, 580) + 1):
        span = _row_span(px, w, y)
        if span:
            circle_ref = max(circle_ref, span[2])
    if circle_ref <= 0:
        raise SystemExit("no se detectó el emblema circular")

    cut = None
    for y in range(max(top, 550), bottom + 1):
        span = _row_span(px, w, y)
        if span and span[2] > circle_ref * 1.12:
            cut = y
            break
    if cut is None:
        cut = bottom + 1

    left, right = w, 0
    for y in range(top, cut):
        span = _row_span(px, w, y)
        if span:
            left = min(left, span[0])
            right = max(right, span[1])
    emblem = rgba.crop((left, top, right + 1, cut))
    bbox = emblem.getbbox()
    if bbox is None:
        raise SystemExit("emblema vacío tras crop")
    return emblem.crop(bbox)


def square_pad(img: Image.Image) -> Image.Image:
    cw, ch = img.size
    side = max(1, int(round(max(cw, ch) / (1.0 - 2.0 * PAD_FRAC))))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - cw) // 2, (side - ch) // 2), img)
    return canvas


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def write_svg(square: Image.Image, path: Path) -> None:
    master = square.resize((512, 512), Image.Resampling.LANCZOS)
    b64 = base64.b64encode(png_bytes(master)).decode("ascii")
    path.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'width="512" height="512" viewBox="0 0 512 512">\n'
            f'  <image width="512" height="512" href="data:image/png;base64,{b64}"/>\n'
            "</svg>\n"
        ),
        encoding="utf-8",
    )


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"falta {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    emblem = emblem_from_full_logo(Image.open(SRC))
    square = square_pad(emblem)
    print(
        f"emblem {emblem.size[0]}×{emblem.size[1]} → square {square.size[0]}×{square.size[1]} "
        f"(pad={PAD_FRAC:.0%})"
    )

    square.save(OUT / "whisper-live-captions.png", format="PNG", optimize=True)
    for size in SIZES:
        resized = square.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(OUT / f"whisper-live-captions-{size}.png", format="PNG", optimize=True)
        bbox = resized.getbbox()
        fill = ""
        if bbox:
            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            fill = f" fill≈{bw / size * 100:.0f}%×{bh / size * 100:.0f}%"
        print(f"  {size}px{fill}")

    write_svg(square, OUT / "whisper-live-captions.svg")
    print(f"OK → {OUT}")


if __name__ == "__main__":
    main()
