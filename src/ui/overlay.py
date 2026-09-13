from __future__ import annotations

import queue
import subprocess
from collections.abc import Callable
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from src.asr.languages import language_label
from src.asr.types import CaptionUpdate


class SubtitleOverlay(QtWidgets.QWidget):
    def __init__(
        self,
        text_queue: queue.Queue[CaptionUpdate],
        config: dict[str, Any],
        on_open_settings: Callable[[], None] | None = None,
        on_close_app: Callable[[], None] | None = None,
        on_save_config: Callable[[dict[str, Any]], None] | None = None,
        on_restart_pipeline: Callable[[], None] | None = None,
        on_translation_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.text_queue = text_queue
        self.config = config
        self.on_open_settings = on_open_settings
        self.on_close_app = on_close_app
        self.on_save_config = on_save_config
        self.on_restart_pipeline = on_restart_pipeline
        self.on_translation_changed = on_translation_changed
        self._final_text = ""
        self._partial_text = ""
        self._translated_text = ""
        self._drag_offset: QtCore.QPoint | None = None
        self._always_on_top = bool(config.get("always_on_top", True))
        self._ignore_move_save = False
        self._save_pos_timer = QtCore.QTimer(self)
        self._save_pos_timer.setSingleShot(True)
        self._save_pos_timer.timeout.connect(self._persist_geometry)
        self._build_ui()
        self._apply_style()
        self._build_context_menu()
        self._sync_translation_ui()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(80)

        self._keep_above_timer = QtCore.QTimer(self)
        self._keep_above_timer.timeout.connect(self._ensure_on_top)
        self._keep_above_timer.start(1500)

    def _window_flags(self) -> QtCore.Qt.WindowType:
        flags = (
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.CustomizeWindowHint
        )
        if self._always_on_top:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        return flags

    def _build_ui(self) -> None:
        self.setWindowTitle("Subtítulos en directo")
        self.setWindowFlags(self._window_flags())
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.panel = QtWidgets.QFrame()
        self.panel.setObjectName("captionPanel")
        self.panel.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        self.panel.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.panel.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.panel.mapToParent(pos))
        )
        panel_layout = QtWidgets.QVBoxLayout(self.panel)
        pad = int(self.config.get("padding", 24))
        panel_layout.setContentsMargins(pad, pad // 2, pad, pad // 2)

        top = QtWidgets.QHBoxLayout()
        self.lang_label = QtWidgets.QLabel(str(self.config.get("language", "en")).upper())
        self.lang_label.setObjectName("langLabel")
        self.lang_label.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.lang_label.setToolTip("Clic para cambiar idioma ASR")
        top.addWidget(self.lang_label)

        self.translate_btn = QtWidgets.QPushButton("ES")
        self.translate_btn.setObjectName("translateToggle")
        self.translate_btn.setCheckable(True)
        self.translate_btn.setChecked(bool(self.config.get("translation_enabled", False)))
        self.translate_btn.setFixedWidth(36)
        self.translate_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.translate_btn.setToolTip("Traducir a español (solo texto confirmado)")
        self.translate_btn.toggled.connect(self._on_translate_toggled)
        top.addWidget(self.translate_btn)
        top.addStretch(1)

        self.settings_btn = QtWidgets.QPushButton("⚙")
        self.settings_btn.setFixedWidth(36)
        self.settings_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self._handle_settings)
        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setFixedWidth(36)
        self.close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._handle_close)
        top.addWidget(self.settings_btn)
        top.addWidget(self.close_btn)
        panel_layout.addLayout(top)

        self.translated_label = QtWidgets.QLabel("")
        self.translated_label.setWordWrap(True)
        self.translated_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.translated_label.setObjectName("translatedCaption")

        self.final_label = QtWidgets.QLabel("")
        self.final_label.setWordWrap(True)
        self.final_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.final_label.setObjectName("finalCaption")

        self.partial_label = QtWidgets.QLabel("")
        self.partial_label.setWordWrap(True)
        self.partial_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.partial_label.setObjectName("partialCaption")

        panel_layout.addWidget(self.translated_label)
        panel_layout.addWidget(self.final_label)
        panel_layout.addWidget(self.partial_label)
        root.addWidget(self.panel)

        for widget in (
            self,
            self.panel,
            self.lang_label,
            self.translated_label,
            self.final_label,
            self.partial_label,
        ):
            widget.installEventFilter(self)
            widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        self.lang_label.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.lang_label.mapTo(self, pos))
        )
        self.translated_label.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.translated_label.mapTo(self, pos))
        )
        self.final_label.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.final_label.mapTo(self, pos))
        )
        self.partial_label.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.partial_label.mapTo(self, pos))
        )

        width = int(self.config.get("window_width", 900))
        self.resize(width, 150)
        self._restore_position()

    def _saved_position(self) -> list[int] | None:
        pos = self.config.get("window_pos")
        if isinstance(pos, list) and len(pos) == 2:
            try:
                return [int(pos[0]), int(pos[1])]
            except (TypeError, ValueError):
                return None
        return None

    def _clamp_to_screens(self, x: int, y: int) -> tuple[int, int]:
        screens = QtGui.QGuiApplication.screens()
        if not screens:
            return x, y
        point = QtCore.QPoint(x, y)
        for screen in screens:
            if screen.geometry().contains(point):
                return x, y
        # Si quedó fuera (cambio de monitor), ancla abajo-centro del primario.
        geo = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        return geo.center().x() - self.width() // 2, geo.bottom() - max(180, self.height() + 40)

    def _restore_position(self) -> None:
        saved = self._saved_position()
        self._ignore_move_save = True
        try:
            if saved is not None:
                x, y = self._clamp_to_screens(saved[0], saved[1])
                self.move(x, y)
            else:
                screen = QtGui.QGuiApplication.primaryScreen()
                if screen is not None:
                    geo = screen.availableGeometry()
                    self.move(geo.center().x() - self.width() // 2, geo.bottom() - 220)
        finally:
            self._ignore_move_save = False

    def _schedule_persist_geometry(self) -> None:
        if self._ignore_move_save or not self.isVisible():
            return
        self.config["window_pos"] = [self.x(), self.y()]
        self.config["window_width"] = self.width()
        self._save_pos_timer.start(250)

    def _persist_geometry(self) -> None:
        self.config["window_pos"] = [self.x(), self.y()]
        self.config["window_width"] = self.width()
        if self.on_save_config is not None:
            self.on_save_config(self.config)

    def _reapply_flags(self, *, show_again: bool) -> None:
        """setWindowFlags recrea la ventana nativa y pierde la posición si no se restaura."""
        pos = [self.x(), self.y()] if self.isVisible() else self._saved_position()
        self._ignore_move_save = True
        try:
            self.setWindowFlags(self._window_flags())
            if pos is not None:
                x, y = self._clamp_to_screens(int(pos[0]), int(pos[1]))
                self.move(x, y)
                self.config["window_pos"] = [x, y]
            if show_again:
                self.show()
        finally:
            self._ignore_move_save = False

    def _build_context_menu(self) -> None:
        self._menu = QtWidgets.QMenu(self)
        self._menu.setStyleSheet(
            """
            QMenu {
                background: #2b2b2b;
                color: #f0f0f0;
                border: 1px solid #555;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 28px 6px 12px;
            }
            QMenu::item:selected {
                background: #3584e4;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 4px 8px;
            }
            """
        )

        self._act_hide = self._menu.addAction("Ocultar")
        self._act_hide.triggered.connect(self.hide)

        self._act_above = self._menu.addAction("Siempre encima")
        self._act_above.setCheckable(True)
        self._act_above.setChecked(self._always_on_top)
        self._act_above.toggled.connect(self.set_always_on_top)

        self._menu.addSeparator()
        self._act_settings = self._menu.addAction("Configuración…")
        self._act_settings.triggered.connect(self._handle_settings)
        self._act_close = self._menu.addAction("Cerrar")
        self._act_close.triggered.connect(self._handle_close)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        self._act_above.blockSignals(True)
        self._act_above.setChecked(self._always_on_top)
        self._act_above.blockSignals(False)
        self._menu.exec(self.mapToGlobal(pos))

    def set_always_on_top(self, enabled: bool) -> None:
        self._always_on_top = bool(enabled)
        self.config["always_on_top"] = self._always_on_top
        self._reapply_flags(show_again=True)
        self._ensure_on_top()
        self._persist_geometry()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._restore_position()
        QtCore.QTimer.singleShot(0, self._restore_position)
        QtCore.QTimer.singleShot(50, self._restore_position)
        QtCore.QTimer.singleShot(0, self._ensure_on_top)
        QtCore.QTimer.singleShot(200, self._ensure_on_top)

    def moveEvent(self, event: QtGui.QMoveEvent) -> None:
        super().moveEvent(event)
        self._schedule_persist_geometry()

    def _ensure_on_top(self) -> None:
        if not self.isVisible() or not self._always_on_top:
            return
        flags = self.windowFlags()
        if not (flags & QtCore.Qt.WindowType.WindowStaysOnTopHint):
            self._reapply_flags(show_again=True)
            return
        self.raise_()
        self._apply_x11_above(True)

    def _apply_x11_above(self, enabled: bool) -> None:
        """Refuerza _NET_WM_STATE_ABOVE en XWayland/X11 (como el menú de GNOME)."""
        if QtGui.QGuiApplication.platformName() != "xcb":
            return
        wid = int(self.winId())
        if wid <= 0:
            return
        action = "add" if enabled else "remove"
        # wmctrl es opcional; si no está, el hint de Qt suele bastar bajo xcb.
        try:
            subprocess.run(
                ["wmctrl", "-i", "-r", hex(wid), "-b", f"{action},above"],
                check=False,
                capture_output=True,
                timeout=1.5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    def _apply_style(self) -> None:
        font_size = int(self.config.get("font_size", 28))
        font_color = str(self.config.get("font_color", "#ffffff"))
        bg = str(self.config.get("bg_color", "#000000"))
        alpha = float(self.config.get("bg_alpha", 0.55))
        color = QtGui.QColor(bg)
        color.setAlphaF(alpha)
        rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF():.2f})"
        partial = QtGui.QColor(font_color)
        partial.setAlphaF(0.55)
        partial_rgba = (
            f"rgba({partial.red()}, {partial.green()}, {partial.blue()}, {partial.alphaF():.2f})"
        )

        asr_size = max(12, font_size - 4) if self._translation_active() else font_size
        self.setStyleSheet(
            f"""
            QFrame#captionPanel {{
                background: {rgba};
                border-radius: 12px;
            }}
            QLabel#translatedCaption {{
                color: {font_color};
                font-size: {font_size}px;
                font-weight: 600;
            }}
            QLabel#finalCaption {{
                color: {font_color};
                font-size: {asr_size}px;
                font-weight: 600;
            }}
            QLabel#partialCaption {{
                color: {partial_rgba};
                font-size: {max(12, asr_size - 6)}px;
                font-style: italic;
            }}
            QLabel#langLabel {{
                color: {partial_rgba};
                font-size: 12px;
            }}
            QPushButton#translateToggle {{
                background: transparent;
                color: {partial_rgba};
                border: 1px solid {partial_rgba};
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 4px;
            }}
            QPushButton#translateToggle:checked {{
                color: {font_color};
                border-color: {font_color};
                background: rgba(255, 255, 255, 0.12);
            }}
            QPushButton {{
                background: transparent;
                color: {font_color};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{
                color: #ffd27a;
            }}
            """
        )

    def apply_config(self, config: dict[str, Any]) -> None:
        self.config = config
        pad = int(config.get("padding", 24))
        layout = self.panel.layout()
        if layout is not None:
            layout.setContentsMargins(pad, pad // 2, pad, pad // 2)
        self.lang_label.setText(str(config.get("language", "en")).upper())
        self.translate_btn.blockSignals(True)
        self.translate_btn.setChecked(bool(config.get("translation_enabled", False)))
        self.translate_btn.blockSignals(False)
        self.resize(int(config.get("window_width", 900)), self.height())
        self._apply_style()
        self._sync_translation_ui()
        desired = bool(config.get("always_on_top", True))
        if desired != self._always_on_top:
            self.set_always_on_top(desired)
        else:
            self._ensure_on_top()

    def _translation_active(self) -> bool:
        if not bool(self.config.get("translation_enabled", False)):
            return False
        lang = str(self.config.get("language", "en")).strip().lower()
        target = str(self.config.get("translation_target") or "es").strip().lower() or "es"
        return lang != target

    def _second_line_mode(self) -> str:
        mode = str(self.config.get("second_line_mode", "live_asr")).strip().lower()
        if mode not in ("live_asr", "original", "none"):
            return "live_asr"
        return mode

    def _sync_translation_ui(self) -> None:
        translation_on = self._translation_active()
        self.translated_label.setVisible(translation_on)
        if not translation_on:
            self._translated_text = ""
            self.translated_label.setText("")
            self.final_label.setVisible(True)
            self.partial_label.setVisible(True)
        else:
            mode = self._second_line_mode()
            show_second = mode != "none"
            self.final_label.setVisible(show_second)
            # Con traducción nunca usamos partial como tercera línea visual.
            self.partial_label.setVisible(False)
        self._refresh_caption_texts()
        self._apply_style()

    def _refresh_caption_texts(self) -> None:
        translation_on = self._translation_active()
        self.translated_label.setText(self._translated_text if translation_on else "")
        if not translation_on:
            self.final_label.setText(self._final_text)
            self.partial_label.setText(self._partial_text)
            return

        mode = self._second_line_mode()
        if mode == "live_asr":
            parts = [part for part in (self._final_text, self._partial_text) if part]
            self.final_label.setText(" ".join(parts).strip())
        elif mode == "original":
            self.final_label.setText(self._final_text)
        else:
            self.final_label.setText("")
        self.partial_label.setText("")

    def _on_translate_toggled(self, enabled: bool) -> None:
        self.config["translation_enabled"] = bool(enabled)
        if not enabled:
            self._translated_text = ""
        self._sync_translation_ui()
        if self.on_save_config is not None:
            self.on_save_config(self.config)
        if self.on_translation_changed is not None:
            self.on_translation_changed()

    def _show_language_menu(self) -> None:
        langs = self.config.get("installed_languages") or ["en", "es"]
        if not isinstance(langs, list) or not langs:
            langs = ["en", "es"]
        menu = QtWidgets.QMenu(self)
        for code in langs:
            lang = str(code).strip().lower()
            if not lang:
                continue
            action = menu.addAction(language_label(lang))
            action.triggered.connect(lambda _checked=False, c=lang: self._set_language(c))
        menu.exec(self.lang_label.mapToGlobal(self.lang_label.rect().bottomLeft()))

    def _set_language(self, language: str) -> None:
        lang = language.strip().lower() or "en"
        if lang == str(self.config.get("language", "en")).lower():
            return
        self.config["language"] = lang
        installed = list(self.config.get("installed_languages") or [])
        if lang not in installed:
            self.config["installed_languages"] = [lang, *installed]
        self.lang_label.setText(lang.upper())
        self._sync_translation_ui()
        if self.on_save_config is not None:
            self.on_save_config(self.config)
        # Idioma ASR va en WhisperEngine: requiere reinicio del pipeline.
        if self.on_restart_pipeline is not None:
            self.on_restart_pipeline()

    def _poll_queue(self) -> None:
        updated = False
        while True:
            try:
                item = self.text_queue.get_nowait()
            except queue.Empty:
                break
            if item.is_final:
                self._final_text = item.text
                self._partial_text = ""
                if item.translated_text is not None:
                    self._translated_text = item.translated_text
            else:
                if self._final_text and item.text.startswith(self._final_text):
                    self._partial_text = item.text[len(self._final_text) :].strip()
                else:
                    self._partial_text = item.text
            updated = True
        if updated:
            self._refresh_caption_texts()

    def current_position(self) -> list[int]:
        return [self.x(), self.y()]

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.MouseButtonPress and isinstance(
            event, QtGui.QMouseEvent
        ):
            if obj in (self.settings_btn, self.close_btn, self.translate_btn):
                return False
            if obj is self.lang_label and event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._show_language_menu()
                return True
            if event.button() == QtCore.Qt.MouseButton.RightButton:
                self._show_context_menu(self.mapFromGlobal(event.globalPosition().toPoint()))
                return True
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                if self._begin_drag(event):
                    return True
        if event.type() == QtCore.QEvent.Type.MouseMove and isinstance(event, QtGui.QMouseEvent):
            if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            self._drag_offset = None
        return super().eventFilter(obj, event)

    def _begin_drag(self, event: QtGui.QMouseEvent) -> bool:
        handle = self.windowHandle()
        if handle is not None and handle.startSystemMove():
            return True
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        return True

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self._show_context_menu(event.pos())
            event.accept()
            return
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._begin_drag(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def _handle_settings(self) -> None:
        if self.on_open_settings:
            self.on_open_settings()

    def _handle_close(self) -> None:
        if self.on_close_app:
            self.on_close_app()
        else:
            self.close()
