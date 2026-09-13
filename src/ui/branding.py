"""Rutas y pixmaps de marca (LIVE CAPTIONS PGL)."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtGui

from src.config import resolve_app_root

_FULL_LOGO = "FullLogo_Transparent.png"
_PRINT_SVG = "Print_Transparent.svg"

# FullLogo_Transparent.png 1280×1024; arte útil PIL bbox (238,225)–(1041,790).
# Mitad de margen arriba/lados; abajo solo 1/4 del pad original (mitad de la mitad).
_FULL_LOGO_NATIVE = (1280, 1024)
_FULL_LOGO_HALF_MARGIN_CROP = QtCore.QRect(119, 112, 1042, 736)


def repo_or_app_root() -> Path:
    installed = resolve_app_root()
    if installed is not None:
        return installed
    return Path(__file__).resolve().parents[2]


def media_dir() -> Path:
    return repo_or_app_root() / "assets" / "media"


def brand_logo_path() -> Path:
    return media_dir() / _FULL_LOGO


def brand_print_svg_path() -> Path:
    return media_dir() / _PRINT_SVG


def _crop_with_half_margin(pixmap: QtGui.QPixmap) -> QtGui.QPixmap:
    """Deja la mitad del aire transparente del master (más marca, menos vacío)."""
    if (pixmap.width(), pixmap.height()) != _FULL_LOGO_NATIVE:
        return pixmap
    return pixmap.copy(_FULL_LOGO_HALF_MARGIN_CROP)


def load_brand_logo_pixmap(*, height: int, device_pixel_ratio: float = 1.0) -> QtGui.QPixmap:
    """Wordmark transparente escalado a `height` lógicos (respeta DPR)."""
    path = brand_logo_path()
    if not path.is_file():
        return QtGui.QPixmap()
    dpr = max(1.0, float(device_pixel_ratio) or 1.0)
    target_h = max(1, int(round(height * dpr)))
    raw = QtGui.QPixmap(str(path))
    if raw.isNull():
        return QtGui.QPixmap()
    cropped = _crop_with_half_margin(raw)
    scaled = cropped.scaledToHeight(
        target_h,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(dpr)
    return scaled
