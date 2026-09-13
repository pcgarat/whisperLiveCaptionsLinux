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


def test_settings_geometry_snapshot_and_restore(qapp: QtWidgets.QApplication) -> None:
    from PyQt6 import QtCore

    dlg = SettingsDialog(
        None,
        validate_config(
            {
                "settings_window_width": 700,
                "settings_window_height": 800,
                "settings_window_pos": [120, 80],
            }
        ),
    )
    dlg.apply_saved_geometry()
    assert dlg.width() == 700
    assert dlg.height() == 800
    assert dlg.x() == 120
    assert dlg.y() == 80
    dlg.resize(750, 820)
    dlg.move(30, 40)
    snap = dlg.geometry_snapshot()
    assert snap == {
        "settings_window_pos": [30, 40],
        "settings_window_width": 750,
        "settings_window_height": 820,
    }
    cfg = dlg.result_config()
    assert cfg["settings_window_width"] == 750
    assert cfg["settings_window_height"] == 820
    assert cfg["settings_window_pos"] == [30, 40]

    dlg2 = SettingsDialog(None, validate_config({}))
    dlg2.apply_saved_geometry(fallback_center=QtCore.QPoint(500, 500))
    assert dlg2.x() == 500 - dlg2.width() // 2
    assert dlg2.y() == 500 - dlg2.height() // 2
    dlg.close()
    dlg2.close()


class _FakeAppPresetController:
    def __init__(self) -> None:
        self.applied: list[str | None] = []
        self.saved = 0
        self.saved_as: list[str] = []
        self.deleted = 0
        self.cfg = validate_config({})

    def apply_app_preset_from_settings(self, preset_id, settings_dlg):
        self.applied.append(preset_id)
        from src.config import apply_app_preset

        self.cfg = apply_app_preset(self.cfg, preset_id)
        settings_dlg.reload_from_config(self.cfg)
        return None

    def save_app_preset_from_settings(self, settings_dlg) -> None:
        self.saved += 1
        from src.config import save_app_preset

        self.cfg = save_app_preset(self.cfg, snapshot_src=settings_dlg.result_config())
        settings_dlg.reload_from_config(self.cfg)

    def save_app_preset_as_from_settings(self, name: str, settings_dlg) -> None:
        self.saved_as.append(name)
        from src.config import save_app_preset_as

        self.cfg = save_app_preset_as(
            self.cfg, name, snapshot_src=settings_dlg.result_config()
        )
        settings_dlg.reload_from_config(self.cfg)

    def delete_app_preset_from_settings(self, settings_dlg) -> None:
        self.deleted += 1
        from src.config import delete_app_preset

        self.cfg = delete_app_preset(self.cfg)
        settings_dlg.reload_from_config(self.cfg)


def test_app_preset_bar_disabled_without_controller(
    qapp: QtWidgets.QApplication,
) -> None:
    dlg = SettingsDialog(None, validate_config({}))
    assert dlg.app_preset_save_btn.isEnabled() is False
    assert dlg.app_preset_save_as_btn.isEnabled() is False
    assert dlg.app_preset_delete_btn.isEnabled() is False
    dlg.close()


def test_app_preset_bar_save_as_and_guardar(
    qapp: QtWidgets.QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctrl = _FakeAppPresetController()
    dlg = SettingsDialog(None, ctrl.cfg, controller=ctrl)
    assert dlg.app_preset_save_btn.isEnabled() is False
    assert dlg.app_preset_save_as_btn.isEnabled() is True

    monkeypatch.setattr(
        QtWidgets.QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Directo ES", True),
    )
    dlg._save_app_preset_as()
    assert ctrl.saved_as == ["Directo ES"]
    assert dlg.app_preset.currentData() == "directo-es"
    assert dlg.app_preset_save_btn.isEnabled() is True
    assert dlg.app_preset_delete_btn.isEnabled() is True

    dlg.font_size.setValue(42)
    dlg._save_app_preset()
    assert ctrl.saved == 1
    assert ctrl.cfg["app_presets"]["directo-es"]["font_size"] == 42
    dlg.close()


def test_app_preset_reload_updates_controls(qapp: QtWidgets.QApplication) -> None:
    dlg = SettingsDialog(None, validate_config({"font_size": 28}))
    dlg.reload_from_config(
        validate_config(
            {
                "font_size": 55,
                "language": "es",
                "latency_mode": "low",
                "text_align": "left",
                "settings_window_width": 600,
                "settings_window_height": 700,
                "settings_window_pos": [11, 22],
            }
        )
    )
    assert dlg.font_size.value() == 55
    assert dlg.language.currentData() == "es"
    assert dlg.latency_mode.currentData() == "low"
    assert dlg.text_align.currentData() == "left"
    assert dlg.width() == 600
    assert dlg.height() == 700
    dlg.close()
