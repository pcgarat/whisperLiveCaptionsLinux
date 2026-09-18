from __future__ import annotations

import re

from PyQt6 import QtGui

from src.config import FONT_WEIGHT_MODES

# Curadas por legibilidad sobre vídeo: palo seco humanista primero, luego
# condensadas (más caracteres por línea) y por último serif.
CAPTION_FONT_PRESETS: tuple[str, ...] = (
    "Inter",
    "Noto Sans",
    "Roboto",
    "Open Sans",
    "Source Sans 3",
    "Lato",
    "Ubuntu",
    "Cantarell",
    "DejaVu Sans",
    "Liberation Sans",
    "Noto Sans Display",
    "Liberation Sans Narrow",
    "DejaVu Sans Condensed",
    "Noto Serif",
    "DejaVu Serif",
)

FONT_WEIGHT_CSS: dict[str, int] = {
    "normal": 400,
    "semibold": 600,
    "bold": 700,
}

# fontconfig expone la misma familia una vez por fundición («Nimbus Sans [urw]»).
# Ese nombre no resuelve como `font-family` en QSS, así que el sufijo se recorta.
_FOUNDRY_SUFFIX = re.compile(r"\s*\[[^\]]*\]\s*$")


def _strip_foundry(family: str) -> str:
    return _FOUNDRY_SUFFIX.sub("", str(family)).strip()


def _usable_latin_families() -> list[str]:
    """Familias instaladas que sirven para texto latino, sin duplicados.

    El sistema de escritura latino ya descarta símbolos, emoji y alfabetos que
    en un subtítulo se verían como cajas.
    """
    db = QtGui.QFontDatabase
    out: list[str] = []
    seen: set[str] = set()
    for raw in db.families(QtGui.QFontDatabase.WritingSystem.Latin):
        if db.isPrivateFamily(raw) or not db.isSmoothlyScalable(raw):
            continue
        family = _strip_foundry(raw)
        key = family.casefold()
        if not family or key in seen:
            continue
        seen.add(key)
        out.append(family)
    return out


def available_caption_fonts() -> tuple[list[str], list[str]]:
    """`(curadas instaladas, resto de familias)`, en ese orden de presentación."""
    installed = _usable_latin_families()
    by_key = {family.casefold(): family for family in installed}
    curated = [
        by_key[preset.casefold()]
        for preset in CAPTION_FONT_PRESETS
        if preset.casefold() in by_key
    ]
    curated_keys = {family.casefold() for family in curated}
    rest = sorted(
        (family for family in installed if family.casefold() not in curated_keys),
        key=str.casefold,
    )
    return curated, rest


def is_font_installed(family: str) -> bool:
    if not family:
        return True
    key = family.casefold()
    return any(
        installed.casefold() == key for installed in _usable_latin_families()
    )


def font_weight_css(weight: str) -> int:
    key = str(weight or "").strip().lower()
    if key not in FONT_WEIGHT_MODES:
        key = "semibold"
    return FONT_WEIGHT_CSS[key]


def font_family_qss(family: str) -> str:
    """Declaración `font-family` para QSS; `""` deja la fuente por defecto de Qt."""
    name = str(family or "").strip()
    return f'font-family: "{name}";' if name else ""
