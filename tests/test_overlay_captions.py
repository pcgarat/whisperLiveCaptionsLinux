from __future__ import annotations

import os
import queue
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from src.asr.types import CaptionUpdate
from src.ui.overlay import SubtitleOverlay


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _overlay(qapp: QtWidgets.QApplication) -> tuple[SubtitleOverlay, queue.Queue]:
    del qapp
    q: queue.Queue[CaptionUpdate] = queue.Queue()
    cfg = {
        "language": "en",
        "translation_enabled": True,
        "translation_target": "es",
        "second_line_mode": "live_asr",
        "always_on_top": False,
        "window_width": 800,
        "font_size": 22,
        "font_color": "#FFFFFF",
        "bg_opacity": 0.55,
    }
    ov = SubtitleOverlay(text_queue=q, config=cfg)
    ov._timer.stop()
    return ov, q


def test_append_translation_for_extension(qapp: QtWidgets.QApplication) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Hello",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Hola",
            seq=1,
            translation_append=False,
        )
    )
    q.put(
        CaptionUpdate(
            text="Hello world",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="mundo",
            seq=2,
            translation_append=True,
        )
    )
    ov._poll_queue()
    assert ov._final_text == "Hello world"
    assert ov._translated_text == "Hola mundo"
    ov.close()


def test_stale_translation_does_not_overwrite(qapp: QtWidgets.QApplication) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Second phrase",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Segunda frase",
            seq=2,
            translation_append=False,
        )
    )
    ov._poll_queue()
    q.put(
        CaptionUpdate(
            text="First phrase revised",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Primera frase cambiada",
            seq=1,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._final_text == "Second phrase"
    assert ov._translated_text == "Segunda frase"
    ov.close()


def test_translation_prefix_does_not_shrink_final(
    qapp: QtWidgets.QApplication,
) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Hello world today",
            is_final=True,
            language="en",
            ts_mono=now,
            seq=3,
        )
    )
    ov._poll_queue()
    q.put(
        CaptionUpdate(
            text="Hello",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Hola",
            seq=3,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._final_text == "Hello world today"
    assert ov._translated_text == "Hola"
    ov.close()


def test_late_translation_applies_if_same_final_text(
    qapp: QtWidgets.QApplication,
) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Hello world",
            is_final=True,
            language="en",
            ts_mono=now,
            seq=2,
        )
    )
    ov._poll_queue()
    q.put(
        CaptionUpdate(
            text="Hello world",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Hola mundo",
            seq=1,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._caption_seq == 2
    assert ov._translated_text == "Hola mundo"
    ov.close()


def test_new_segment_keeps_old_translation_until_ready(
    qapp: QtWidgets.QApplication,
) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Old",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Viejo",
            seq=1,
        )
    )
    ov._poll_queue()
    q.put(
        CaptionUpdate(
            text="Brand new",
            is_final=True,
            language="en",
            ts_mono=now,
            seq=2,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._final_text == "Brand new"
    assert ov._translated_text == "Viejo"
    q.put(
        CaptionUpdate(
            text="Brand new",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Nuevo",
            seq=2,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._translated_text == "Nuevo"
    ov.close()


def test_partial_can_carry_translation(qapp: QtWidgets.QApplication) -> None:
    ov, q = _overlay(qapp)
    now = time.monotonic()
    q.put(
        CaptionUpdate(
            text="Hello",
            is_final=True,
            language="en",
            ts_mono=now,
            translated_text="Hola",
            seq=1,
            translation_append=False,
        )
    )
    ov._poll_queue()
    q.put(
        CaptionUpdate(
            text="Hello world",
            is_final=False,
            language="en",
            ts_mono=now,
            translated_text="Hola mundo",
            seq=1,
            translation_append=False,
        )
    )
    ov._poll_queue()
    assert ov._final_text == "Hello"
    assert ov._partial_text == "world"
    assert ov._translated_text == "Hola mundo"
    ov.close()
