from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from src.config import TRANSLATION_FACTORY_PRESETS, validate_config
from src.ui.settings import (
    TOOLTIP_ALLOW_REWRITE,
    TOOLTIP_SHOW_PARTIALS,
    SettingsDialog,
    _friendly_audio_label,
    detect_partials_sticky_conflict,
)


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_friendly_audio_bluetooth() -> None:
    assert (
        _friendly_audio_label("bluez_output.44_73_D6_C9_A1_5F.1.monitor")
        == "Bluetooth · 44:73:D6:C9:A1:5F"
    )


def test_friendly_audio_alsa() -> None:
    assert (
        _friendly_audio_label("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor")
        == "Salida ALSA · pci-0000_00_1f.3.analog-stereo"
    )


def test_friendly_audio_empty() -> None:
    assert _friendly_audio_label("") == "(sin dispositivo)"


def test_settings_edit_decode_switches_to_custom(qapp: QtWidgets.QApplication) -> None:
    dlg = SettingsDialog(
        None, validate_config({"translation_decode_preset": "balanced"})
    )
    assert dlg.tx_preset.currentData() == "balanced"
    dlg.tx_beam.setValue(7)
    assert dlg.tx_preset.currentData() == "custom"
    cfg = dlg.result_config()
    assert cfg["translation_decode_preset"] == "custom"
    assert cfg["translation_profiles"]["custom"]["beam_size"] == 7
    dlg.close()


def test_settings_factory_preset_in_result(qapp: QtWidgets.QApplication) -> None:
    dlg = SettingsDialog(None, validate_config({}))
    idx = dlg.tx_preset.findData("quality")
    dlg.tx_preset.setCurrentIndex(idx)
    cfg = dlg.result_config()
    assert cfg["translation_decode_preset"] == "quality"
    assert (
        cfg["translation_profiles"]["quality"] == TRANSLATION_FACTORY_PRESETS["quality"]
    )
    assert not dlg.tx_delete_btn.isEnabled()
    dlg.close()


def test_settings_captions_display_toggles(qapp: QtWidgets.QApplication) -> None:
    dlg = SettingsDialog(None, validate_config({}))
    assert dlg.captions_show_partials.isChecked()
    assert dlg.captions_allow_rewrite.isChecked()
    assert TOOLTIP_SHOW_PARTIALS in (dlg.captions_show_partials.toolTip() or "")
    assert TOOLTIP_ALLOW_REWRITE in (dlg.captions_allow_rewrite.toolTip() or "")
    dlg.captions_show_partials.setChecked(False)
    dlg.captions_allow_rewrite.setChecked(False)
    cfg = dlg.result_config()
    assert cfg["captions_show_partials"] is False
    assert cfg["captions_allow_rewrite"] is False
    dlg.close()


def test_settings_appearance_tab_text_align(qapp: QtWidgets.QApplication) -> None:
    from PyQt6 import QtCore

    dlg = SettingsDialog(None, validate_config({}))
    assert dlg.text_align.currentData() == "center"
    idx = dlg.text_align.findData("left")
    dlg.text_align.setCurrentIndex(idx)
    cfg = dlg.result_config()
    assert cfg["text_align"] == "left"
    assert (
        dlg._preview_caption.alignment() & QtCore.Qt.AlignmentFlag.AlignLeft
        == QtCore.Qt.AlignmentFlag.AlignLeft
    )
    dlg.close()


def test_detect_partials_sticky_conflict_none_when_compatible() -> None:
    assert (
        detect_partials_sticky_conflict(
            show_partials=True, sticky_mode="partials", changed="partials"
        )
        is None
    )
    assert (
        detect_partials_sticky_conflict(
            show_partials=False, sticky_mode="committed", changed="sticky"
        )
        is None
    )


def test_detect_partials_sticky_conflict_fix_targets() -> None:
    turned_off = detect_partials_sticky_conflict(
        show_partials=False, sticky_mode="partials", changed="partials"
    )
    assert turned_off is not None
    assert turned_off.fix_sticky_mode == "committed"
    assert turned_off.fix_show_partials is None

    set_sticky = detect_partials_sticky_conflict(
        show_partials=False, sticky_mode="partials", changed="sticky"
    )
    assert set_sticky is not None
    assert set_sticky.fix_show_partials is True
    assert set_sticky.fix_sticky_mode is None


def test_settings_conflict_cancel_reverts_partials(
    qapp: QtWidgets.QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    dlg = SettingsDialog(
        None,
        validate_config({"translation_sticky_mode": "partials"}),
    )
    monkeypatch.setattr(dlg, "_prompt_mode_conflict", lambda _c: False)
    dlg.captions_show_partials.setChecked(False)
    assert dlg.captions_show_partials.isChecked() is True
    assert dlg.tx_sticky_mode.currentData() == "partials"
    dlg.close()


def test_settings_conflict_fix_changes_sticky(
    qapp: QtWidgets.QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    dlg = SettingsDialog(
        None,
        validate_config({"translation_sticky_mode": "partials"}),
    )
    monkeypatch.setattr(dlg, "_prompt_mode_conflict", lambda _c: True)
    dlg.captions_show_partials.setChecked(False)
    assert dlg.captions_show_partials.isChecked() is False
    assert dlg.tx_sticky_mode.currentData() == "committed"
    dlg.close()


def test_settings_conflict_fix_enables_partials_from_sticky(
    qapp: QtWidgets.QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    dlg = SettingsDialog(
        None,
        validate_config(
            {
                "captions_show_partials": False,
                "translation_sticky_mode": "off",
            }
        ),
    )
    monkeypatch.setattr(dlg, "_prompt_mode_conflict", lambda _c: True)
    idx = dlg.tx_sticky_mode.findData("partials")
    dlg.tx_sticky_mode.setCurrentIndex(idx)
    assert dlg.captions_show_partials.isChecked() is True
    assert dlg.tx_sticky_mode.currentData() == "partials"
    dlg.close()
