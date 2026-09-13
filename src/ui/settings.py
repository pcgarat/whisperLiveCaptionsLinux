from __future__ import annotations

from copy import deepcopy
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from src.asr.languages import (
    AVAILABLE_LANGUAGES,
    language_label,
    merge_installed_languages,
    pending_languages,
)
from src.audio.devices import list_audio_monitors
from src.config import (
    LATENCY_FACTORY_PRESETS,
    effective_latency_profile,
    reset_latency_profile,
)

TOOLTIP_CONFIDENCE = (
    "Cuántas hipótesis consecutivas del ASR deben coincidir en un prefijo antes de "
    "confirmarlo. Más alto = más estable y más lento; más bajo = más rápido e inestable."
)
TOOLTIP_MAX_LATENCY = (
    "Techo en segundos: si el subtítulo provisional no se confirma a tiempo, se fuerza "
    "un commit. Más bajo = menos retraso, más riesgo de confirmar texto prematuro."
)


class InstallLanguagesDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        installed: list[str],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Instalar idiomas")
        self.setModal(True)
        self._installed = list(installed)
        self._checks: dict[str, QtWidgets.QCheckBox] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel("Marca los idiomas a añadir a los selectores:")
        )

        pending = pending_languages(self._installed)
        if not pending:
            layout.addWidget(
                QtWidgets.QLabel("Todos los idiomas del catálogo ya están instalados.")
            )
        else:
            for code in pending:
                box = QtWidgets.QCheckBox(language_label(code))
                self._checks[code] = box
                layout.addWidget(box)

        buttons = QtWidgets.QDialogButtonBox()
        self.install_btn = buttons.addButton(
            "Instalar seleccionados",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.install_btn.setEnabled(bool(pending))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_codes(self) -> list[str]:
        return [code for code, box in self._checks.items() if box.isChecked()]


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de subtítulos")
        self.setModal(True)
        self._config = dict(config)
        if not isinstance(self._config.get("latency_profiles"), dict):
            self._config["latency_profiles"] = deepcopy(LATENCY_FACTORY_PRESETS)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QtWidgets.QLabel("Idioma (manual):"))
        lang_row = QtWidgets.QHBoxLayout()
        self.language = QtWidgets.QComboBox()
        lang_row.addWidget(self.language, stretch=1)
        self.install_langs_btn = QtWidgets.QPushButton("Instalar nuevos…")
        self.install_langs_btn.setToolTip(
            "Añade idiomas del catálogo a los selectores de Settings y del overlay."
        )
        self.install_langs_btn.clicked.connect(self._install_languages)
        lang_row.addWidget(self.install_langs_btn)
        layout.addLayout(lang_row)
        self._refresh_language_combo(str(config.get("language", "en")))

        layout.addWidget(QtWidgets.QLabel("Modelo Whisper:"))
        self.model = QtWidgets.QComboBox()
        for name in ["small", "medium", "large-v3-turbo", "large-v3"]:
            self.model.addItem(name)
        current_model = str(config.get("model", "medium"))
        idx = self.model.findText(current_model)
        self.model.setCurrentIndex(idx if idx >= 0 else 1)
        layout.addWidget(self.model)

        layout.addWidget(QtWidgets.QLabel("Dispositivo de audio (monitor):"))
        self.audio = QtWidgets.QComboBox()
        try:
            devices = list_audio_monitors()
        except Exception as exc:
            devices = []
            layout.addWidget(QtWidgets.QLabel(f"Aviso audio: {exc}"))
        if not devices:
            devices = [str(config.get("audio_monitor") or "")]
        for dev in devices:
            if dev:
                self.audio.addItem(dev)
        current = str(config.get("audio_monitor") or "")
        if current:
            pos = self.audio.findText(current)
            if pos >= 0:
                self.audio.setCurrentIndex(pos)
            elif current not in devices:
                self.audio.insertItem(0, current)
                self.audio.setCurrentIndex(0)
        layout.addWidget(self.audio)

        layout.addWidget(QtWidgets.QLabel("Modo de latencia:"))
        self.latency_mode = QtWidgets.QComboBox()
        self.latency_mode.addItem("Estable (stable)", "stable")
        self.latency_mode.addItem("Baja latencia (low)", "low")
        mode = str(config.get("latency_mode", "stable"))
        mode_idx = self.latency_mode.findData(mode)
        self.latency_mode.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        self.latency_mode.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.latency_mode)

        conf_row = QtWidgets.QHBoxLayout()
        conf_label = QtWidgets.QLabel("Confianza:")
        conf_label.setToolTip(TOOLTIP_CONFIDENCE)
        conf_row.addWidget(conf_label)
        self.confidence = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.confidence.setRange(1, 5)
        self.confidence.setToolTip(TOOLTIP_CONFIDENCE)
        self.confidence_value = QtWidgets.QLabel("2")
        conf_row.addWidget(self.confidence, stretch=1)
        conf_row.addWidget(self.confidence_value)
        layout.addLayout(conf_row)
        self.confidence.valueChanged.connect(self._on_confidence_changed)

        lat_row = QtWidgets.QHBoxLayout()
        lat_label = QtWidgets.QLabel("Latencia máxima (s):")
        lat_label.setToolTip(TOOLTIP_MAX_LATENCY)
        lat_row.addWidget(lat_label)
        self.max_latency = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.max_latency.setRange(5, 50)  # 0.5–5.0 s en décimas
        self.max_latency.setToolTip(TOOLTIP_MAX_LATENCY)
        self.max_latency_value = QtWidgets.QLabel("3.0")
        lat_row.addWidget(self.max_latency, stretch=1)
        lat_row.addWidget(self.max_latency_value)
        layout.addLayout(lat_row)
        self.max_latency.valueChanged.connect(self._on_max_latency_changed)

        self.reset_btn = QtWidgets.QPushButton("Restablecer modo")
        self.reset_btn.setToolTip("Vuelve a los valores de fábrica del modo seleccionado.")
        self.reset_btn.clicked.connect(self._reset_mode)
        layout.addWidget(self.reset_btn)

        note = QtWidgets.QLabel(
            "El tamaño de chunk lo fija el modo (stable≈0.8 s, low≈0.35 s). "
            "Cambios de modelo/dispositivo/idioma/latencia se aplican al reiniciar el pipeline "
            "(Guardar)."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addWidget(QtWidgets.QLabel("Tamaño de texto:"))
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(10, 100)
        self.font_size.setValue(int(config.get("font_size", 28)))
        layout.addWidget(self.font_size)

        layout.addWidget(QtWidgets.QLabel("Padding:"))
        self.padding = QtWidgets.QSpinBox()
        self.padding.setRange(0, 100)
        self.padding.setValue(int(config.get("padding", 24)))
        layout.addWidget(self.padding)

        layout.addWidget(QtWidgets.QLabel("Color de texto:"))
        self.font_color_btn = QtWidgets.QPushButton(str(config.get("font_color", "#ffffff")))
        self.font_color_btn.clicked.connect(self._pick_font_color)
        layout.addWidget(self.font_color_btn)

        layout.addWidget(QtWidgets.QLabel("Color de fondo:"))
        self.bg_color_btn = QtWidgets.QPushButton(str(config.get("bg_color", "#000000")))
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        layout.addWidget(self.bg_color_btn)

        layout.addWidget(QtWidgets.QLabel("Transparencia fondo (%):"))
        self.alpha = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha.setRange(5, 100)
        self.alpha.setValue(int(float(config.get("bg_alpha", 0.55)) * 100))
        layout.addWidget(self.alpha)

        self.show_asr_line = QtWidgets.QCheckBox("Mostrar línea ASR (con traducción ON)")
        self.show_asr_line.setChecked(bool(config.get("show_asr_line", True)))
        self.show_asr_line.setToolTip(
            "Con traducción activa, muestra también el texto ASR original debajo del español."
        )
        layout.addWidget(self.show_asr_line)

        catalog_note = QtWidgets.QLabel(
            "Catálogo disponible: "
            + ", ".join(f"{AVAILABLE_LANGUAGES[c]} ({c})" for c in AVAILABLE_LANGUAGES)
        )
        catalog_note.setWordWrap(True)
        layout.addWidget(catalog_note)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._loading_profile = False
        self._load_profile_into_sliders(str(self.latency_mode.currentData()))

    def _installed_languages(self) -> list[str]:
        raw = self._config.get("installed_languages") or ["en", "es"]
        if not isinstance(raw, list):
            return ["en", "es"]
        return merge_installed_languages(raw, [])

    def _refresh_language_combo(self, preferred: str | None = None) -> None:
        current = preferred
        if current is None and self.language.count() > 0:
            current = str(self.language.currentData() or "")
        if not current:
            current = str(self._config.get("language", "en"))
        installed = self._installed_languages()
        if current not in installed:
            installed = merge_installed_languages(installed, [current])
            self._config["installed_languages"] = installed
        self.language.blockSignals(True)
        self.language.clear()
        for code in installed:
            self.language.addItem(language_label(code), code)
        idx = self.language.findData(current)
        self.language.setCurrentIndex(idx if idx >= 0 else 0)
        self.language.blockSignals(False)

    def _install_languages(self) -> None:
        dlg = InstallLanguagesDialog(self, self._installed_languages())
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        selected = dlg.selected_codes()
        if not selected:
            return
        merged = merge_installed_languages(self._installed_languages(), selected)
        self._config["installed_languages"] = merged
        self._refresh_language_combo()

    def _current_mode(self) -> str:
        data = self.latency_mode.currentData()
        return str(data) if data else "stable"

    def _profiles(self) -> dict[str, dict[str, float | int]]:
        profiles = self._config.setdefault("latency_profiles", deepcopy(LATENCY_FACTORY_PRESETS))
        if not isinstance(profiles, dict):
            profiles = deepcopy(LATENCY_FACTORY_PRESETS)
            self._config["latency_profiles"] = profiles
        return profiles

    def _load_profile_into_sliders(self, mode: str) -> None:
        self._loading_profile = True
        try:
            profile = effective_latency_profile({**self._config, "latency_mode": mode})
            self.confidence.setValue(int(profile["agreement_n"]))
            self.confidence_value.setText(str(int(profile["agreement_n"])))
            tenths = int(round(float(profile["max_latency_sec"]) * 10))
            self.max_latency.setValue(tenths)
            self.max_latency_value.setText(f"{tenths / 10:.1f}")
        finally:
            self._loading_profile = False

    def _write_sliders_to_profile(self) -> None:
        if self._loading_profile:
            return
        mode = self._current_mode()
        profiles = self._profiles()
        current = dict(profiles.get(mode) or LATENCY_FACTORY_PRESETS.get(mode, {}))
        current["agreement_n"] = int(self.confidence.value())
        current["max_latency_sec"] = self.max_latency.value() / 10.0
        if "min_chunk_seconds" not in current:
            current["min_chunk_seconds"] = LATENCY_FACTORY_PRESETS[mode]["min_chunk_seconds"]
        profiles[mode] = current
        self._config["latency_profiles"] = profiles

    def _on_mode_changed(self) -> None:
        self._load_profile_into_sliders(self._current_mode())

    def _on_confidence_changed(self, value: int) -> None:
        self.confidence_value.setText(str(value))
        self._write_sliders_to_profile()

    def _on_max_latency_changed(self, value: int) -> None:
        self.max_latency_value.setText(f"{value / 10:.1f}")
        self._write_sliders_to_profile()

    def _reset_mode(self) -> None:
        mode = self._current_mode()
        self._config = reset_latency_profile(self._config, mode)
        self._load_profile_into_sliders(mode)

    def _pick_font_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.font_color_btn.text()), self)
        if color.isValid():
            self.font_color_btn.setText(color.name())

    def _pick_bg_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.bg_color_btn.text()), self)
        if color.isValid():
            self.bg_color_btn.setText(color.name())

    def result_config(self) -> dict[str, Any]:
        self._write_sliders_to_profile()
        lang = str(self.language.currentData() or "en").strip().lower() or "en"
        installed = merge_installed_languages(self._installed_languages(), [lang])
        cfg = dict(self._config)
        cfg.update(
            {
                "language": lang,
                "installed_languages": installed,
                "model": self.model.currentText(),
                "audio_monitor": self.audio.currentText(),
                "latency_mode": self._current_mode(),
                "latency_profiles": deepcopy(self._profiles()),
                "font_size": self.font_size.value(),
                "padding": self.padding.value(),
                "font_color": self.font_color_btn.text(),
                "bg_color": self.bg_color_btn.text(),
                "bg_alpha": self.alpha.value() / 100.0,
                "show_asr_line": self.show_asr_line.isChecked(),
            }
        )
        return cfg
