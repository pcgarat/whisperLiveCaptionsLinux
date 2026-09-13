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
    SECOND_LINE_MODES,
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

# Cinema lower-third: carbón profundo + ámbar de marquesina (no GNOME blue genérico).
_SETTINGS_QSS = """
QDialog#SettingsDialog {
    background: #16181e;
    color: #e8eaef;
}
QScrollArea#SettingsScroll {
    background: transparent;
    border: none;
}
QWidget#SettingsBody {
    background: transparent;
}
QLabel#DialogTitle {
    color: #f4f5f7;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.2px;
}
QLabel#DialogSubtitle {
    color: #8b93a7;
    font-size: 12px;
}
QFrame#PreviewStage {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #0c0d10, stop:0.55 #12141a, stop:1 #1a1520
    );
    border: 1px solid #2c3140;
    border-radius: 14px;
}
QLabel#PreviewHint {
    color: #6d758a;
    font-size: 11px;
    letter-spacing: 0.8px;
}
QLabel#PreviewCaption {
    font-weight: 600;
}
QLabel#SectionTitle {
    color: #e8b86d;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
}
QFrame#SectionRule {
    background: #2c3140;
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QLabel#FieldLabel {
    color: #c5cad6;
    font-size: 13px;
}
QLabel#FieldHint {
    color: #7a8296;
    font-size: 11px;
}
QLabel#ValueChip {
    color: #e8b86d;
    font-size: 12px;
    font-weight: 600;
    min-width: 28px;
}
QComboBox, QSpinBox {
    background: #22262f;
    color: #eef0f4;
    border: 1px solid #3a4152;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 18px;
}
QComboBox:hover, QSpinBox:hover {
    border-color: #5a6478;
}
QComboBox:focus, QSpinBox:focus {
    border-color: #e8b86d;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox QAbstractItemView {
    background: #22262f;
    color: #eef0f4;
    border: 1px solid #3a4152;
    selection-background-color: #3a3224;
    selection-color: #f7e3bc;
    outline: none;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #2a2f3a;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background: #e8b86d;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #c4923f;
    border-radius: 3px;
}
QPushButton#SecondaryButton {
    background: #22262f;
    color: #d5dae6;
    border: 1px solid #3a4152;
    border-radius: 8px;
    padding: 7px 12px;
}
QPushButton#SecondaryButton:hover {
    background: #2a303c;
    border-color: #5a6478;
}
QPushButton#GhostButton {
    background: transparent;
    color: #9aa3b5;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 10px;
    text-align: left;
}
QPushButton#GhostButton:hover {
    color: #e8b86d;
    border-color: #3a4152;
}
QPushButton#ColorSwatch {
    border: 1px solid #4a5164;
    border-radius: 8px;
    padding: 8px 12px;
    text-align: left;
    font-family: "JetBrains Mono", "Cascadia Code", "Ubuntu Mono", monospace;
    font-size: 12px;
}
QPushButton#ColorSwatch:hover {
    border-color: #e8b86d;
}
QPushButton#PrimaryButton {
    background: #e8b86d;
    color: #1a140c;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    min-width: 96px;
    min-height: 32px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background: #f0c784;
}
QPushButton#DialogCancel {
    background: #22262f;
    color: #d5dae6;
    border: 1px solid #3a4152;
    border-radius: 8px;
    padding: 8px 16px;
    min-width: 96px;
    min-height: 32px;
}
QPushButton#DialogCancel:hover {
    background: #2a303c;
    border-color: #5a6478;
}
QCheckBox {
    color: #e8eaef;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3a4152;
    background: #22262f;
}
QCheckBox::indicator:checked {
    background: #e8b86d;
    border-color: #e8b86d;
}
"""


def _friendly_audio_label(device: str) -> str:
    """Etiqueta legible sin perder el id técnico en el tooltip."""
    name = device.strip()
    if not name:
        return "(sin dispositivo)"
    short = name
    if short.endswith(".monitor"):
        short = short[: -len(".monitor")]
    if short.startswith("bluez_output."):
        mac = short.removeprefix("bluez_output.").rsplit(".", 1)[0].replace("_", ":")
        return f"Bluetooth · {mac}"
    if short.startswith("alsa_output."):
        rest = short.removeprefix("alsa_output.")
        return f"Salida ALSA · {rest}"
    if "." in short:
        kind, rest = short.split(".", 1)
        return f"{kind} · {rest}"
    return short


def _contrast_text(bg: QtGui.QColor) -> str:
    # YIQ aproximado: texto oscuro sobre swatches claros.
    yiq = (bg.red() * 299 + bg.green() * 587 + bg.blue() * 114) / 1000
    return "#1a140c" if yiq > 150 else "#f4f5f7"


class InstallLanguagesDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        installed: list[str],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Instalar idiomas")
        self.setModal(True)
        self.setStyleSheet(_SETTINGS_QSS)
        self._installed = list(installed)
        self._checks: dict[str, QtWidgets.QCheckBox] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Añadir idiomas")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        subtitle = QtWidgets.QLabel(
            "Se añadirá a los selectores de Settings y del overlay."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        pending = pending_languages(self._installed)
        if not pending:
            empty = QtWidgets.QLabel("Todos los idiomas del catálogo ya están instalados.")
            empty.setObjectName("FieldHint")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            for code in pending:
                box = QtWidgets.QCheckBox(language_label(code))
                self._checks[code] = box
                layout.addWidget(box)

        catalog = QtWidgets.QLabel(
            "Catálogo: "
            + ", ".join(f"{AVAILABLE_LANGUAGES[c]} ({c})" for c in AVAILABLE_LANGUAGES)
        )
        catalog.setObjectName("FieldHint")
        catalog.setWordWrap(True)
        layout.addWidget(catalog)

        buttons = QtWidgets.QDialogButtonBox()
        self.install_btn = buttons.addButton(
            "Instalar seleccionados",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole,
        )
        cancel = buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.install_btn.setObjectName("PrimaryButton")
        if cancel is not None:
            cancel.setText("Cancelar")
            cancel.setObjectName("DialogCancel")
        self.install_btn.setEnabled(bool(pending))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_codes(self) -> list[str]:
        return [code for code, box in self._checks.items() if box.isChecked()]


class _Section(QtWidgets.QWidget):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)
        label = QtWidgets.QLabel(title.upper())
        label.setObjectName("SectionTitle")
        header.addWidget(label)
        rule = QtWidgets.QFrame()
        rule.setObjectName("SectionRule")
        rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        header.addWidget(rule, stretch=1)
        root.addLayout(header)

        self.body = QtWidgets.QFormLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setHorizontalSpacing(16)
        self.body.setVerticalSpacing(10)
        self.body.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.body.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.body.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        root.addLayout(self.body)

    def add_row(self, label: str, widget: QtWidgets.QWidget, tip: str | None = None) -> None:
        lab = QtWidgets.QLabel(label)
        lab.setObjectName("FieldLabel")
        if tip:
            lab.setToolTip(tip)
            widget.setToolTip(tip)
        self.body.addRow(lab, widget)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Configuración de subtítulos")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(640)
        self.resize(560, 720)
        self.setStyleSheet(_SETTINGS_QSS)

        self._config = dict(config)
        if not isinstance(self._config.get("latency_profiles"), dict):
            self._config["latency_profiles"] = deepcopy(LATENCY_FACTORY_PRESETS)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        header = QtWidgets.QVBoxLayout()
        header.setSpacing(2)
        title = QtWidgets.QLabel("Configuración")
        title.setObjectName("DialogTitle")
        header.addWidget(title)
        subtitle = QtWidgets.QLabel("Captura, latencia y aspecto del overlay")
        subtitle.setObjectName("DialogSubtitle")
        header.addWidget(subtitle)
        root.addLayout(header)

        self._preview_stage = QtWidgets.QFrame()
        self._preview_stage.setObjectName("PreviewStage")
        preview_layout = QtWidgets.QVBoxLayout(self._preview_stage)
        preview_layout.setContentsMargins(16, 14, 16, 16)
        preview_layout.setSpacing(10)
        preview_hint = QtWidgets.QLabel("VISTA PREVIA")
        preview_hint.setObjectName("PreviewHint")
        preview_layout.addWidget(preview_hint)
        self._preview_caption = QtWidgets.QLabel("Hello, this is a live caption preview")
        self._preview_caption.setObjectName("PreviewCaption")
        self._preview_caption.setWordWrap(True)
        self._preview_caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_caption)
        root.addWidget(self._preview_stage)

        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(18)

        capture = _Section("Captura")
        lang_row = QtWidgets.QHBoxLayout()
        lang_row.setSpacing(8)
        self.language = QtWidgets.QComboBox()
        lang_row.addWidget(self.language, stretch=1)
        self.install_langs_btn = QtWidgets.QPushButton("Instalar…")
        self.install_langs_btn.setObjectName("SecondaryButton")
        self.install_langs_btn.setToolTip(
            "Añade idiomas del catálogo a los selectores de Settings y del overlay."
        )
        self.install_langs_btn.clicked.connect(self._install_languages)
        lang_row.addWidget(self.install_langs_btn)
        lang_wrap = QtWidgets.QWidget()
        lang_wrap.setLayout(lang_row)
        capture.add_row("Idioma", lang_wrap)
        self._refresh_language_combo(str(config.get("language", "en")))

        self.model = QtWidgets.QComboBox()
        for name in ["small", "medium", "large-v3-turbo", "large-v3"]:
            self.model.addItem(name)
        current_model = str(config.get("model", "medium"))
        idx = self.model.findText(current_model)
        self.model.setCurrentIndex(idx if idx >= 0 else 1)
        capture.add_row("Modelo Whisper", self.model)

        self.audio = QtWidgets.QComboBox()
        audio_error: str | None = None
        try:
            devices = list_audio_monitors()
        except Exception as exc:
            devices = []
            audio_error = str(exc)
        if not devices:
            devices = [str(config.get("audio_monitor") or "")]
        for dev in devices:
            if not dev:
                continue
            self.audio.addItem(_friendly_audio_label(dev), dev)
            self.audio.setItemData(
                self.audio.count() - 1, dev, QtCore.Qt.ItemDataRole.ToolTipRole
            )
        current = str(config.get("audio_monitor") or "")
        if current:
            pos = self.audio.findData(current)
            if pos >= 0:
                self.audio.setCurrentIndex(pos)
            else:
                self.audio.insertItem(0, _friendly_audio_label(current), current)
                self.audio.setItemData(0, current, QtCore.Qt.ItemDataRole.ToolTipRole)
                self.audio.setCurrentIndex(0)
        capture.add_row("Audio (monitor)", self.audio)
        if audio_error:
            err = QtWidgets.QLabel(f"Aviso audio: {audio_error}")
            err.setObjectName("FieldHint")
            err.setWordWrap(True)
            capture.body.addRow("", err)
        body_layout.addWidget(capture)

        latency = _Section("Latencia")
        self.latency_mode = QtWidgets.QComboBox()
        self.latency_mode.addItem("Estable — más preciso", "stable")
        self.latency_mode.addItem("Baja latencia — más rápido", "low")
        mode = str(config.get("latency_mode", "stable"))
        mode_idx = self.latency_mode.findData(mode)
        self.latency_mode.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        self.latency_mode.currentIndexChanged.connect(self._on_mode_changed)
        latency.add_row("Modo", self.latency_mode)

        conf_wrap = QtWidgets.QWidget()
        conf_row = QtWidgets.QHBoxLayout(conf_wrap)
        conf_row.setContentsMargins(0, 0, 0, 0)
        conf_row.setSpacing(10)
        self.confidence = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.confidence.setRange(1, 5)
        self.confidence_value = QtWidgets.QLabel("2")
        self.confidence_value.setObjectName("ValueChip")
        self.confidence_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        conf_row.addWidget(self.confidence, stretch=1)
        conf_row.addWidget(self.confidence_value)
        latency.add_row("Confianza", conf_wrap, TOOLTIP_CONFIDENCE)
        self.confidence.valueChanged.connect(self._on_confidence_changed)

        lat_wrap = QtWidgets.QWidget()
        lat_row = QtWidgets.QHBoxLayout(lat_wrap)
        lat_row.setContentsMargins(0, 0, 0, 0)
        lat_row.setSpacing(10)
        self.max_latency = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.max_latency.setRange(5, 50)  # 0.5–5.0 s en décimas
        self.max_latency_value = QtWidgets.QLabel("3.0")
        self.max_latency_value.setObjectName("ValueChip")
        self.max_latency_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        lat_row.addWidget(self.max_latency, stretch=1)
        lat_row.addWidget(self.max_latency_value)
        latency.add_row("Techo (s)", lat_wrap, TOOLTIP_MAX_LATENCY)
        self.max_latency.valueChanged.connect(self._on_max_latency_changed)

        self.reset_btn = QtWidgets.QPushButton("Restablecer valores del modo")
        self.reset_btn.setObjectName("GhostButton")
        self.reset_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Vuelve a los valores de fábrica del modo seleccionado.")
        self.reset_btn.clicked.connect(self._reset_mode)
        latency.body.addRow("", self.reset_btn)

        note = QtWidgets.QLabel(
            "El chunk lo fija el modo (estable ≈ 0.8 s, baja ≈ 0.35 s). "
            "Idioma, modelo, audio y latencia se aplican al guardar (reinicia el pipeline)."
        )
        note.setObjectName("FieldHint")
        note.setWordWrap(True)
        latency.body.addRow("", note)
        body_layout.addWidget(latency)

        look = _Section("Apariencia")
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(10, 100)
        self.font_size.setValue(int(config.get("font_size", 28)))
        self.font_size.valueChanged.connect(self._refresh_preview)
        look.add_row("Tamaño de texto", self.font_size)

        self.padding = QtWidgets.QSpinBox()
        self.padding.setRange(0, 100)
        self.padding.setValue(int(config.get("padding", 24)))
        self.padding.valueChanged.connect(self._refresh_preview)
        look.add_row("Padding", self.padding)

        self.font_color_btn = QtWidgets.QPushButton()
        self.font_color_btn.setObjectName("ColorSwatch")
        self.font_color_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._set_swatch(self.font_color_btn, str(config.get("font_color", "#ffffff")))
        self.font_color_btn.clicked.connect(self._pick_font_color)
        look.add_row("Color de texto", self.font_color_btn)

        self.bg_color_btn = QtWidgets.QPushButton()
        self.bg_color_btn.setObjectName("ColorSwatch")
        self.bg_color_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._set_swatch(self.bg_color_btn, str(config.get("bg_color", "#000000")))
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        look.add_row("Color de fondo", self.bg_color_btn)

        alpha_wrap = QtWidgets.QWidget()
        alpha_row = QtWidgets.QHBoxLayout(alpha_wrap)
        alpha_row.setContentsMargins(0, 0, 0, 0)
        alpha_row.setSpacing(10)
        self.alpha = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha.setRange(5, 100)
        self.alpha.setValue(int(float(config.get("bg_alpha", 0.55)) * 100))
        self.alpha_value = QtWidgets.QLabel(f"{self.alpha.value()}%")
        self.alpha_value.setObjectName("ValueChip")
        self.alpha_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        alpha_row.addWidget(self.alpha, stretch=1)
        alpha_row.addWidget(self.alpha_value)
        self.alpha.valueChanged.connect(self._on_alpha_changed)
        look.add_row("Transparencia", alpha_wrap)
        body_layout.addWidget(look)

        translate = _Section("Traducción")
        self.second_line_mode = QtWidgets.QComboBox()
        second_line_labels = {
            "live_asr": "ASR en vivo",
            "original": "Idioma original confirmado",
            "none": "Nada",
        }
        for mode_key in SECOND_LINE_MODES:
            self.second_line_mode.addItem(second_line_labels[mode_key], mode_key)
        current_mode = str(config.get("second_line_mode", "live_asr"))
        idx = self.second_line_mode.findData(current_mode)
        self.second_line_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.second_line_mode.setToolTip(
            "Con traducción activa: línea 1 = traducción; línea 2 = ASR en vivo, "
            "solo el texto confirmado en el idioma original, o ninguna."
        )
        translate.add_row("Segunda línea", self.second_line_mode)
        body_layout.addWidget(translate)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        assert save_btn is not None and cancel_btn is not None
        save_btn.setText("Guardar")
        save_btn.setObjectName("PrimaryButton")
        cancel_btn.setText("Cancelar")
        cancel_btn.setObjectName("DialogCancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._loading_profile = False
        self._load_profile_into_sliders(str(self.latency_mode.currentData()))
        self._refresh_preview()

    def _set_swatch(self, button: QtWidgets.QPushButton, hex_color: str) -> None:
        color = QtGui.QColor(hex_color)
        if not color.isValid():
            color = QtGui.QColor("#000000")
            hex_color = color.name()
        button.setText(hex_color)
        button.setStyleSheet(
            f"""
            QPushButton#ColorSwatch {{
                background: {hex_color};
                color: {_contrast_text(color)};
                border: 1px solid #4a5164;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
                font-family: "JetBrains Mono", "Cascadia Code", "Ubuntu Mono", monospace;
                font-size: 12px;
            }}
            QPushButton#ColorSwatch:hover {{
                border-color: #e8b86d;
            }}
            """
        )

    def _refresh_preview(self) -> None:
        font_size = int(self.font_size.value())
        font_color = self.font_color_btn.text()
        bg = QtGui.QColor(self.bg_color_btn.text())
        if not bg.isValid():
            bg = QtGui.QColor("#000000")
        alpha = self.alpha.value() / 100.0
        bg.setAlphaF(alpha)
        pad = int(self.padding.value())
        rgba = f"rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alphaF():.2f})"
        self._preview_caption.setStyleSheet(
            f"""
            QLabel#PreviewCaption {{
                color: {font_color};
                font-size: {font_size}px;
                font-weight: 600;
                background: {rgba};
                border-radius: 12px;
                padding: {pad}px;
            }}
            """
        )

    def _on_alpha_changed(self, value: int) -> None:
        self.alpha_value.setText(f"{value}%")
        self._refresh_preview()

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
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.font_color_btn.text()), self
        )
        if color.isValid():
            self._set_swatch(self.font_color_btn, color.name())
            self._refresh_preview()

    def _pick_bg_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.bg_color_btn.text()), self
        )
        if color.isValid():
            self._set_swatch(self.bg_color_btn, color.name())
            self._refresh_preview()

    def result_config(self) -> dict[str, Any]:
        self._write_sliders_to_profile()
        lang = str(self.language.currentData() or "en").strip().lower() or "en"
        installed = merge_installed_languages(self._installed_languages(), [lang])
        audio = self.audio.currentData()
        if audio is None:
            audio = self.audio.currentText()
        cfg = dict(self._config)
        cfg.update(
            {
                "language": lang,
                "installed_languages": installed,
                "model": self.model.currentText(),
                "audio_monitor": str(audio or ""),
                "latency_mode": self._current_mode(),
                "latency_profiles": deepcopy(self._profiles()),
                "font_size": self.font_size.value(),
                "padding": self.padding.value(),
                "font_color": self.font_color_btn.text(),
                "bg_color": self.bg_color_btn.text(),
                "bg_alpha": self.alpha.value() / 100.0,
                "second_line_mode": str(self.second_line_mode.currentData() or "live_asr"),
            }
        )
        return cfg
