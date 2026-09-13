from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
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
    TEXT_ALIGN_LABELS,
    TEXT_ALIGN_MODES,
    TRANSLATION_FACTORY_PRESETS,
    TRANSLATION_PRESET_LABELS,
    TRANSLATION_RESERVED_PRESET_IDS,
    TRANSLATION_STICKY_LABELS,
    TRANSLATION_STICKY_MODES,
    add_translation_user_preset,
    delete_translation_user_preset,
    effective_latency_profile,
    effective_translation_decode,
    reset_latency_profile,
    slugify_translation_preset_name,
    translation_user_preset_ids,
    validate_config,
)

TOOLTIP_CONFIDENCE = (
    "Cuántas hipótesis consecutivas del ASR deben coincidir en un prefijo antes de "
    "confirmarlo. Más alto = más estable y más lento; más bajo = más rápido e inestable."
)
TOOLTIP_MAX_LATENCY = (
    "Techo en segundos: si el subtítulo provisional no se confirma a tiempo, se fuerza "
    "un commit. Más bajo = menos retraso, más riesgo de confirmar texto prematuro."
)
TOOLTIP_TX_BEAM = (
    "Beam search del traductor. Más alto = mejor calidad y más CPU/latencia."
)
TOOLTIP_TX_LENGTH = "Penalización de longitud NLLB. ≈1.0 es neutro; algo >1 favorece salidas un poco más largas."
TOOLTIP_TX_NGRAM = "Evita repetir n-gramas. 0 = desactivado; 3 suele reducir bucles raros en subtítulos."
TOOLTIP_TX_STICKY = (
    "Normal: solo confirmados, re-traduce en rewrites. "
    "Sticky: no re-traduce prefijos ya enviados a NLLB. "
    "Sticky + parciales: también traduce la hipótesis en vivo (más CPU)."
)
TOOLTIP_SHOW_PARTIALS = (
    "Activado: el overlay muestra la hipótesis del ASR en vivo (texto que aún puede "
    "cambiar). Desactivado: solo se envía y pinta texto confirmado; más estable, "
    "pero el subtítulo aparece a saltos al confirmar."
)
TOOLTIP_ALLOW_REWRITE = (
    "Activado: la frase actual puede corregirse in-place si el ASR cambia de "
    "opinión (mismo prefijo de palabras); una hipótesis totalmente nueva se "
    "añade al scrollback sin borrar lo anterior. Desactivado: lo escrito solo "
    "puede crecer. El overlay es un scroll anclado abajo: siempre se ve lo último."
)

MSG_PARTIALS_STICKY_CONFLICT = (
    "«Mostrar texto parcial» está desactivado y el modo sticky es "
    "«Sticky + parciales».\n\n"
    "Sticky + parciales traduce la hipótesis ASR en vivo; sin texto parcial "
    "ese modo no tiene efecto.\n\n"
    "Cancelar deshace el último cambio. El otro botón deja una combinación compatible."
)


@dataclass(frozen=True)
class SettingsModeConflict:
    message: str
    fix_button_label: str
    # None = no cambiar ese knob al pulsar «compatible».
    fix_show_partials: bool | None = None
    fix_sticky_mode: str | None = None


def detect_partials_sticky_conflict(
    *,
    show_partials: bool,
    sticky_mode: str,
    changed: str,
) -> SettingsModeConflict | None:
    """Conflicto: sin parciales + sticky=partials.

    `changed`: ``partials`` | ``sticky`` | ``save`` — decide el botón de arreglo
    (cambiar la *otra* opción) y el mensaje de acción.
    """
    sticky = str(sticky_mode or "").strip().lower()
    if show_partials or sticky != "partials":
        return None
    if changed == "partials":
        return SettingsModeConflict(
            message=MSG_PARTIALS_STICKY_CONFLICT,
            fix_button_label="Cambiar sticky a solo confirmados",
            fix_sticky_mode="committed",
        )
    if changed == "sticky":
        return SettingsModeConflict(
            message=MSG_PARTIALS_STICKY_CONFLICT,
            fix_button_label="Activar texto parcial",
            fix_show_partials=True,
        )
    # Guardar u origen desconocido: preferimos conservar «sin parciales».
    return SettingsModeConflict(
        message=MSG_PARTIALS_STICKY_CONFLICT,
        fix_button_label="Cambiar sticky a solo confirmados",
        fix_sticky_mode="committed",
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
QComboBox, QSpinBox, QDoubleSpinBox {
    background: #22262f;
    color: #eef0f4;
    border: 1px solid #3a4152;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 18px;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #5a6478;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
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
QTabWidget::pane {
    border: 1px solid #2c3140;
    border-radius: 10px;
    top: -1px;
    background: transparent;
}
QTabBar::tab {
    background: #1c1f27;
    color: #8b93a7;
    border: 1px solid #2c3140;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 14px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #22262f;
    color: #f4f5f7;
    border-color: #3a4152;
}
QTabBar::tab:hover:!selected {
    color: #e8b86d;
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
            empty = QtWidgets.QLabel(
                "Todos los idiomas del catálogo ya están instalados."
            )
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

    def add_row(
        self, label: str, widget: QtWidgets.QWidget, tip: str | None = None
    ) -> None:
        lab = QtWidgets.QLabel(label)
        lab.setObjectName("FieldLabel")
        if tip:
            lab.setToolTip(tip)
            widget.setToolTip(tip)
        self.body.addRow(lab, widget)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(
        self, parent: QtWidgets.QWidget | None, config: dict[str, Any]
    ) -> None:
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
        self._config = validate_config(self._config)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        header = QtWidgets.QVBoxLayout()
        header.setSpacing(2)
        title = QtWidgets.QLabel("Configuración")
        title.setObjectName("DialogTitle")
        header.addWidget(title)
        subtitle = QtWidgets.QLabel(
            "Captura, latencia, apariencia y calidad de traducción"
        )
        subtitle.setObjectName("DialogSubtitle")
        header.addWidget(subtitle)
        root.addLayout(header)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_general_tab(config), "General")
        tabs.addTab(self._build_appearance_tab(config), "Apariencia")
        tabs.addTab(self._build_translation_tab(config), "Traducciones")
        root.addWidget(tabs, stretch=1)

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
        self._loading_tx = False
        self._guarding_mode_conflict = False
        self._prev_sticky_mode = str(
            self.tx_sticky_mode.currentData() or "off"
        )
        self.captions_show_partials.toggled.connect(self._on_show_partials_toggled)
        self.tx_sticky_mode.currentIndexChanged.connect(self._on_sticky_mode_changed)
        self._load_profile_into_sliders(str(self.latency_mode.currentData()))
        self._refresh_translation_preset_combo()
        self._load_translation_decode_into_spins()
        self._sync_translation_preset_actions()
        self._refresh_preview()

    def accept(self) -> None:
        if not self._ensure_modes_compatible(changed="save"):
            return
        super().accept()

    def _on_show_partials_toggled(self, checked: bool) -> None:
        if self._guarding_mode_conflict:
            return
        if checked:
            return
        self._ensure_modes_compatible(changed="partials")

    def _on_sticky_mode_changed(self, _index: int) -> None:
        if self._guarding_mode_conflict:
            return
        sticky = str(self.tx_sticky_mode.currentData() or "off")
        if not self._ensure_modes_compatible(changed="sticky"):
            return
        self._prev_sticky_mode = sticky

    def _ensure_modes_compatible(self, *, changed: str) -> bool:
        conflict = detect_partials_sticky_conflict(
            show_partials=self.captions_show_partials.isChecked(),
            sticky_mode=str(self.tx_sticky_mode.currentData() or "off"),
            changed=changed,
        )
        if conflict is None:
            return True
        if not self._prompt_mode_conflict(conflict):
            self._revert_mode_change(changed)
            return False
        self._apply_mode_conflict_fix(conflict)
        return True

    def _prompt_mode_conflict(self, conflict: SettingsModeConflict) -> bool:
        """True = aplicar arreglo compatible; False = cancelar."""
        box = QtWidgets.QMessageBox(self)
        box.setObjectName("SettingsDialog")
        box.setStyleSheet(_SETTINGS_QSS)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("Opciones incompatibles")
        box.setText("Combinación no compatible")
        box.setInformativeText(conflict.message)
        cancel_btn = box.addButton(
            "Cancelar", QtWidgets.QMessageBox.ButtonRole.RejectRole
        )
        fix_btn = box.addButton(
            conflict.fix_button_label,
            QtWidgets.QMessageBox.ButtonRole.AcceptRole,
        )
        box.setDefaultButton(fix_btn)
        box.exec()
        clicked = box.clickedButton()
        return clicked is fix_btn and clicked is not cancel_btn

    def _revert_mode_change(self, changed: str) -> None:
        self._guarding_mode_conflict = True
        try:
            if changed == "partials":
                self.captions_show_partials.setChecked(True)
            elif changed == "sticky":
                idx = self.tx_sticky_mode.findData(self._prev_sticky_mode)
                self.tx_sticky_mode.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._guarding_mode_conflict = False

    def _apply_mode_conflict_fix(self, conflict: SettingsModeConflict) -> None:
        self._guarding_mode_conflict = True
        try:
            if conflict.fix_show_partials is not None:
                self.captions_show_partials.setChecked(conflict.fix_show_partials)
            if conflict.fix_sticky_mode is not None:
                idx = self.tx_sticky_mode.findData(conflict.fix_sticky_mode)
                if idx >= 0:
                    self.tx_sticky_mode.setCurrentIndex(idx)
                    self._prev_sticky_mode = conflict.fix_sticky_mode
        finally:
            self._guarding_mode_conflict = False

    def _wrap_scroll(self, body: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(body)
        return scroll

    def _build_general_tab(self, config: dict[str, Any]) -> QtWidgets.QWidget:
        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 8, 8, 0)
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
        self.reset_btn.setToolTip(
            "Vuelve a los valores de fábrica del modo seleccionado."
        )
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

        captions = _Section("Subtítulos")
        self.captions_show_partials = QtWidgets.QCheckBox("Mostrar texto parcial")
        self.captions_show_partials.setChecked(
            bool(config.get("captions_show_partials", True))
        )
        self.captions_show_partials.setToolTip(TOOLTIP_SHOW_PARTIALS)
        captions.body.addRow(self.captions_show_partials)
        self.captions_allow_rewrite = QtWidgets.QCheckBox(
            "Permitir reescritura de lo ya mostrado"
        )
        self.captions_allow_rewrite.setChecked(
            bool(config.get("captions_allow_rewrite", True))
        )
        self.captions_allow_rewrite.setToolTip(TOOLTIP_ALLOW_REWRITE)
        captions.body.addRow(self.captions_allow_rewrite)
        body_layout.addWidget(captions)
        body_layout.addStretch(1)
        return self._wrap_scroll(body)

    def _build_appearance_tab(self, config: dict[str, Any]) -> QtWidgets.QWidget:
        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 8, 8, 0)
        body_layout.setSpacing(18)

        self._preview_stage = QtWidgets.QFrame()
        self._preview_stage.setObjectName("PreviewStage")
        preview_layout = QtWidgets.QVBoxLayout(self._preview_stage)
        preview_layout.setContentsMargins(16, 14, 16, 16)
        preview_layout.setSpacing(10)
        preview_hint = QtWidgets.QLabel("VISTA PREVIA")
        preview_hint.setObjectName("PreviewHint")
        preview_layout.addWidget(preview_hint)
        self._preview_caption = QtWidgets.QLabel(
            "Hello, this is a live caption preview"
        )
        self._preview_caption.setObjectName("PreviewCaption")
        self._preview_caption.setWordWrap(True)
        self._preview_caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._preview_caption)
        body_layout.addWidget(self._preview_stage)

        look = _Section("Texto y colores")
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

        self.text_align = QtWidgets.QComboBox()
        for mode_key in TEXT_ALIGN_MODES:
            self.text_align.addItem(TEXT_ALIGN_LABELS[mode_key], mode_key)
        current_align = str(config.get("text_align", "center"))
        align_idx = self.text_align.findData(current_align)
        self.text_align.setCurrentIndex(align_idx if align_idx >= 0 else 0)
        self.text_align.setToolTip(
            "Alineación horizontal del subtítulo en el overlay (centro o izquierda)."
        )
        self.text_align.currentIndexChanged.connect(self._refresh_preview)
        look.add_row("Alineación", self.text_align)

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
        body_layout.addStretch(1)
        return self._wrap_scroll(body)

    def _build_translation_tab(self, config: dict[str, Any]) -> QtWidgets.QWidget:
        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 8, 8, 0)
        body_layout.setSpacing(18)

        display = _Section("Visualización")
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
        display.add_row("Segunda línea", self.second_line_mode)

        self.tx_sticky_mode = QtWidgets.QComboBox()
        for mode_key in TRANSLATION_STICKY_MODES:
            self.tx_sticky_mode.addItem(TRANSLATION_STICKY_LABELS[mode_key], mode_key)
        sticky = str(config.get("translation_sticky_mode", "off"))
        sticky_idx = self.tx_sticky_mode.findData(sticky)
        self.tx_sticky_mode.setCurrentIndex(sticky_idx if sticky_idx >= 0 else 0)
        display.add_row("Modo sticky", self.tx_sticky_mode, TOOLTIP_TX_STICKY)
        body_layout.addWidget(display)

        quality = _Section("Calidad de decoding")
        self.tx_preset = QtWidgets.QComboBox()
        self.tx_preset.currentIndexChanged.connect(self._on_tx_preset_changed)
        quality.add_row("Preset", self.tx_preset)

        self.tx_beam = QtWidgets.QSpinBox()
        self.tx_beam.setRange(1, 8)
        self.tx_beam.valueChanged.connect(self._on_tx_decode_edited)
        quality.add_row("Beam size", self.tx_beam, TOOLTIP_TX_BEAM)

        self.tx_length = QtWidgets.QDoubleSpinBox()
        self.tx_length.setRange(0.6, 1.5)
        self.tx_length.setSingleStep(0.1)
        self.tx_length.setDecimals(1)
        self.tx_length.valueChanged.connect(self._on_tx_decode_edited)
        quality.add_row("Length penalty", self.tx_length, TOOLTIP_TX_LENGTH)

        self.tx_ngram = QtWidgets.QSpinBox()
        self.tx_ngram.setRange(0, 5)
        self.tx_ngram.valueChanged.connect(self._on_tx_decode_edited)
        quality.add_row("No-repeat n-gram", self.tx_ngram, TOOLTIP_TX_NGRAM)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.tx_save_btn = QtWidgets.QPushButton("Guardar como preset…")
        self.tx_save_btn.setObjectName("SecondaryButton")
        self.tx_save_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.tx_save_btn.clicked.connect(self._save_translation_preset)
        self.tx_delete_btn = QtWidgets.QPushButton("Borrar preset")
        self.tx_delete_btn.setObjectName("GhostButton")
        self.tx_delete_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.tx_delete_btn.clicked.connect(self._delete_translation_preset)
        actions.addWidget(self.tx_save_btn)
        actions.addWidget(self.tx_delete_btn)
        actions.addStretch(1)
        actions_wrap = QtWidgets.QWidget()
        actions_wrap.setLayout(actions)
        quality.body.addRow("", actions_wrap)

        tx_note = QtWidgets.QLabel(
            "Rápido / Equilibrado / Calidad son de fábrica (no se borran). "
            "Editar un valor pasa a Custom. Los cambios se aplican al Guardar sin reiniciar Whisper."
        )
        tx_note.setObjectName("FieldHint")
        tx_note.setWordWrap(True)
        quality.body.addRow("", tx_note)
        body_layout.addWidget(quality)
        body_layout.addStretch(1)
        return self._wrap_scroll(body)

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

    def _preview_alignment(self) -> QtCore.Qt.AlignmentFlag:
        align = str(self.text_align.currentData() or "center")
        if align == "left":
            return QtCore.Qt.AlignmentFlag.AlignLeft
        return QtCore.Qt.AlignmentFlag.AlignHCenter

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
        self._preview_caption.setAlignment(
            self._preview_alignment() | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
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
        profiles = self._config.setdefault(
            "latency_profiles", deepcopy(LATENCY_FACTORY_PRESETS)
        )
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
            current["min_chunk_seconds"] = LATENCY_FACTORY_PRESETS[mode][
                "min_chunk_seconds"
            ]
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

    def _current_tx_preset(self) -> str:
        data = self.tx_preset.currentData()
        return str(data) if data else "balanced"

    def _translation_profiles(self) -> dict[str, dict[str, float | int]]:
        profiles = self._config.setdefault(
            "translation_profiles",
            {
                **deepcopy(TRANSLATION_FACTORY_PRESETS),
                "custom": deepcopy(TRANSLATION_FACTORY_PRESETS["balanced"]),
            },
        )
        if not isinstance(profiles, dict):
            profiles = {
                **deepcopy(TRANSLATION_FACTORY_PRESETS),
                "custom": deepcopy(TRANSLATION_FACTORY_PRESETS["balanced"]),
            }
            self._config["translation_profiles"] = profiles
        return profiles

    def _spins_decode(self) -> dict[str, float | int]:
        return {
            "beam_size": int(self.tx_beam.value()),
            "length_penalty": float(self.tx_length.value()),
            "no_repeat_ngram_size": int(self.tx_ngram.value()),
        }

    def _refresh_translation_preset_combo(self) -> None:
        current = str(self._config.get("translation_decode_preset", "balanced"))
        self.tx_preset.blockSignals(True)
        self.tx_preset.clear()
        for preset_id in ("fast", "balanced", "quality", "custom"):
            label = TRANSLATION_PRESET_LABELS.get(preset_id, preset_id)
            self.tx_preset.addItem(label, preset_id)
        for preset_id in translation_user_preset_ids(self._config):
            self.tx_preset.addItem(preset_id, preset_id)
        idx = self.tx_preset.findData(current)
        self.tx_preset.setCurrentIndex(
            idx if idx >= 0 else self.tx_preset.findData("balanced")
        )
        self.tx_preset.blockSignals(False)

    def _load_translation_decode_into_spins(self) -> None:
        self._loading_tx = True
        try:
            decode = effective_translation_decode(
                {
                    **self._config,
                    "translation_decode_preset": self._current_tx_preset(),
                }
            )
            self.tx_beam.setValue(int(decode["beam_size"]))
            self.tx_length.setValue(float(decode["length_penalty"]))
            self.tx_ngram.setValue(int(decode["no_repeat_ngram_size"]))
        finally:
            self._loading_tx = False

    def _write_spins_to_custom_profile(self) -> None:
        profiles = self._translation_profiles()
        profiles["custom"] = self._spins_decode()
        self._config["translation_profiles"] = profiles
        self._config["translation_decode_preset"] = "custom"

    def _on_tx_preset_changed(self) -> None:
        preset = self._current_tx_preset()
        self._config["translation_decode_preset"] = preset
        self._load_translation_decode_into_spins()
        self._sync_translation_preset_actions()

    def _on_tx_decode_edited(self, *_args: Any) -> None:
        if self._loading_tx:
            return
        self._write_spins_to_custom_profile()
        if self._current_tx_preset() != "custom":
            self.tx_preset.blockSignals(True)
            idx = self.tx_preset.findData("custom")
            if idx >= 0:
                self.tx_preset.setCurrentIndex(idx)
            self.tx_preset.blockSignals(False)
        self._sync_translation_preset_actions()

    def _sync_translation_preset_actions(self) -> None:
        preset = self._current_tx_preset()
        self.tx_delete_btn.setEnabled(preset not in TRANSLATION_RESERVED_PRESET_IDS)

    def _save_translation_preset(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Guardar preset",
            "Nombre del preset:",
        )
        if not ok:
            return
        slug = slugify_translation_preset_name(name)
        if not slug:
            QtWidgets.QMessageBox.warning(self, "Preset", "Nombre vacío o inválido.")
            return
        if slug in TRANSLATION_RESERVED_PRESET_IDS:
            QtWidgets.QMessageBox.warning(
                self,
                "Preset",
                f"«{slug}» está reservado. Elige otro nombre.",
            )
            return
        try:
            self._config = add_translation_user_preset(
                self._config,
                slug,
                self._spins_decode(),
            )
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Preset", str(exc))
            return
        self._refresh_translation_preset_combo()
        self._load_translation_decode_into_spins()
        self._sync_translation_preset_actions()

    def _delete_translation_preset(self) -> None:
        preset = self._current_tx_preset()
        if preset in TRANSLATION_RESERVED_PRESET_IDS:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Borrar preset",
            f"¿Borrar el preset «{preset}»?",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self._config = delete_translation_user_preset(self._config, preset)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Preset", str(exc))
            return
        self._refresh_translation_preset_combo()
        self._load_translation_decode_into_spins()
        self._sync_translation_preset_actions()

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
        preset = self._current_tx_preset()
        if preset == "custom":
            self._write_spins_to_custom_profile()
        else:
            self._config["translation_decode_preset"] = preset
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
                "text_align": str(self.text_align.currentData() or "center"),
                "font_color": self.font_color_btn.text(),
                "bg_color": self.bg_color_btn.text(),
                "bg_alpha": self.alpha.value() / 100.0,
                "captions_show_partials": self.captions_show_partials.isChecked(),
                "captions_allow_rewrite": self.captions_allow_rewrite.isChecked(),
                "second_line_mode": str(
                    self.second_line_mode.currentData() or "live_asr"
                ),
                "translation_sticky_mode": str(
                    self.tx_sticky_mode.currentData() or "off"
                ),
                "translation_decode_preset": preset,
                "translation_profiles": deepcopy(self._translation_profiles()),
            }
        )
        return validate_config(cfg)
