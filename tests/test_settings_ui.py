from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from src.config import TRANSLATION_FACTORY_PRESETS, validate_config
from src.ui.settings import SettingsDialog, _friendly_audio_label


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
