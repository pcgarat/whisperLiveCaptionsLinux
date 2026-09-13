from __future__ import annotations

import queue
from collections.abc import Callable
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from src.asr.types import CaptionUpdate


class SubtitleOverlay(QtWidgets.QWidget):
    def __init__(
        self,
        text_queue: queue.Queue[CaptionUpdate],
        config: dict[str, Any],
        on_open_settings: Callable[[], None] | None = None,
        on_close_app: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.text_queue = text_queue
        self.config = config
        self.on_open_settings = on_open_settings
        self.on_close_app = on_close_app
        self._final_text = ""
        self._partial_text = ""
        self._drag_offset: QtCore.QPoint | None = None
        self._build_ui()
        self._apply_style()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(80)

    def _build_ui(self) -> None:
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.panel = QtWidgets.QFrame()
        self.panel.setObjectName("captionPanel")
        panel_layout = QtWidgets.QVBoxLayout(self.panel)
        pad = int(self.config.get("padding", 24))
        panel_layout.setContentsMargins(pad, pad // 2, pad, pad // 2)

        top = QtWidgets.QHBoxLayout()
        self.lang_label = QtWidgets.QLabel(str(self.config.get("language", "en")).upper())
        self.lang_label.setObjectName("langLabel")
        top.addWidget(self.lang_label)
        top.addStretch(1)

        self.settings_btn = QtWidgets.QPushButton("⚙")
        self.settings_btn.setFixedWidth(36)
        self.settings_btn.clicked.connect(self._handle_settings)
        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setFixedWidth(36)
        self.close_btn.clicked.connect(self._handle_close)
        top.addWidget(self.settings_btn)
        top.addWidget(self.close_btn)
        panel_layout.addLayout(top)

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

        panel_layout.addWidget(self.final_label)
        panel_layout.addWidget(self.partial_label)
        root.addWidget(self.panel)

        width = int(self.config.get("window_width", 900))
        self.resize(width, 150)
        pos = self.config.get("window_pos")
        if isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.move(geo.center().x() - width // 2, geo.bottom() - 220)

    def _apply_style(self) -> None:
        font_size = int(self.config.get("font_size", 28))
        font_color = str(self.config.get("font_color", "#ffffff"))
        bg = str(self.config.get("bg_color", "#000000"))
        alpha = float(self.config.get("bg_alpha", 0.55))
        # Convert hex + alpha to rgba
        color = QtGui.QColor(bg)
        color.setAlphaF(alpha)
        rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF():.2f})"
        partial = QtGui.QColor(font_color)
        partial.setAlphaF(0.55)
        partial_rgba = (
            f"rgba({partial.red()}, {partial.green()}, {partial.blue()}, {partial.alphaF():.2f})"
        )

        self.setStyleSheet(
            f"""
            QFrame#captionPanel {{
                background: {rgba};
                border-radius: 12px;
            }}
            QLabel#finalCaption {{
                color: {font_color};
                font-size: {font_size}px;
                font-weight: 600;
            }}
            QLabel#partialCaption {{
                color: {partial_rgba};
                font-size: {max(12, font_size - 6)}px;
                font-style: italic;
            }}
            QLabel#langLabel {{
                color: {partial_rgba};
                font-size: 12px;
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
        self.panel.layout().setContentsMargins(pad, pad // 2, pad, pad // 2)
        self.lang_label.setText(str(config.get("language", "en")).upper())
        self.resize(int(config.get("window_width", 900)), self.height())
        self._apply_style()

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
            else:
                # partial carries committed+partial already from pipeline
                if self._final_text and item.text.startswith(self._final_text):
                    self._partial_text = item.text[len(self._final_text) :].strip()
                else:
                    self._partial_text = item.text
            updated = True
        if updated:
            self.final_label.setText(self._final_text)
            self.partial_label.setText(self._partial_text)

    def current_position(self) -> list[int]:
        return [self.x(), self.y()]

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_offset = None
        event.accept()

    def _handle_settings(self) -> None:
        if self.on_open_settings:
            self.on_open_settings()

    def _handle_close(self) -> None:
        if self.on_close_app:
            self.on_close_app()
        else:
            self.close()
