from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from src.audio.devices import list_audio_monitors


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de subtítulos")
        self.setModal(True)
        self._config = dict(config)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QtWidgets.QLabel("Idioma (manual):"))
        self.language = QtWidgets.QLineEdit(str(config.get("language", "en")))
        layout.addWidget(self.language)

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

        layout.addWidget(QtWidgets.QLabel("Chunk mínimo (s):"))
        self.chunk = QtWidgets.QDoubleSpinBox()
        self.chunk.setRange(0.2, 5.0)
        self.chunk.setSingleStep(0.1)
        self.chunk.setValue(float(config.get("min_chunk_seconds", 0.8)))
        layout.addWidget(self.chunk)

        note = QtWidgets.QLabel(
            "Cambios de modelo/dispositivo/idioma se aplican al reiniciar el pipeline "
            "(Guardar y reiniciar)."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_font_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.font_color_btn.text()), self)
        if color.isValid():
            self.font_color_btn.setText(color.name())

    def _pick_bg_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.bg_color_btn.text()), self)
        if color.isValid():
            self.bg_color_btn.setText(color.name())

    def result_config(self) -> dict[str, Any]:
        cfg = dict(self._config)
        cfg.update(
            {
                "language": self.language.text().strip().lower() or "en",
                "model": self.model.currentText(),
                "audio_monitor": self.audio.currentText(),
                "font_size": self.font_size.value(),
                "padding": self.padding.value(),
                "font_color": self.font_color_btn.text(),
                "bg_color": self.bg_color_btn.text(),
                "bg_alpha": self.alpha.value() / 100.0,
                "min_chunk_seconds": self.chunk.value(),
            }
        )
        return cfg
