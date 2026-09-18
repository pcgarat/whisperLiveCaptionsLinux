from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtGui, QtWidgets

from src.ui.fonts import (
    CAPTION_FONT_PRESETS,
    available_caption_fonts,
    font_family_qss,
    font_weight_css,
    is_font_installed,
)


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_available_fonts_split(qapp: QtWidgets.QApplication) -> None:
    curated, rest = available_caption_fonts()
    assert rest, "el sistema debería tener alguna familia latina más"
    curated_keys = {family.casefold() for family in curated}
    assert curated_keys <= {preset.casefold() for preset in CAPTION_FONT_PRESETS}
    # Sin solapes entre ambos bloques ni duplicados dentro de cada uno.
    assert curated_keys.isdisjoint({family.casefold() for family in rest})
    assert len(curated_keys) == len(curated)
    assert len({family.casefold() for family in rest}) == len(rest)
    assert rest == sorted(rest, key=str.casefold)


def test_available_fonts_are_usable_names(qapp: QtWidgets.QApplication) -> None:
    """Sin sufijo de fundición: «Nimbus Sans [urw]» no resuelve como font-family."""
    curated, rest = available_caption_fonts()
    for family in [*curated, *rest]:
        assert "[" not in family and "]" not in family
        assert family == family.strip()
        assert not QtGui.QFontDatabase.isPrivateFamily(family)


def test_curated_fonts_come_first_in_preference_order(
    qapp: QtWidgets.QApplication,
) -> None:
    curated, _rest = available_caption_fonts()
    order = [preset for preset in CAPTION_FONT_PRESETS if preset in curated]
    assert curated == order


def test_is_font_installed(qapp: QtWidgets.QApplication) -> None:
    curated, rest = available_caption_fonts()
    installed = [*curated, *rest]
    assert is_font_installed(installed[0])
    assert is_font_installed(installed[0].upper())
    assert is_font_installed("")  # «Sistema» siempre vale
    assert not is_font_installed("Familia Que No Existe 1234")


def test_font_family_qss() -> None:
    assert font_family_qss("Noto Sans") == 'font-family: "Noto Sans";'
    assert font_family_qss("") == ""
    assert font_family_qss("   ") == ""


def test_font_weight_css() -> None:
    assert font_weight_css("normal") == 400
    assert font_weight_css("semibold") == 600
    assert font_weight_css("bold") == 700
    assert font_weight_css("nope") == 600
    assert font_weight_css("") == 600
