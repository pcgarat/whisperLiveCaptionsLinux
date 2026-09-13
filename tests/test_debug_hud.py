from __future__ import annotations

import os
import queue

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from src.asr.types import CaptionUpdate
from src.debug.live_metrics import (
    PERF,
    LivePerfMetrics,
    LivePerfSnapshot,
    format_perf_chip,
)
from src.debug.trace import debug_hud_enabled
from src.debug.vram import query_vram
from src.ui.overlay import SubtitleOverlay


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_debug_hud_enabled_config_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WLCL_DEBUG_HUD", raising=False)
    monkeypatch.delenv("WLCL_DEBUG_TRACE", raising=False)
    assert not debug_hud_enabled({})
    assert not debug_hud_enabled({"debug_hud": False})
    assert debug_hud_enabled({"debug_hud": True})

    monkeypatch.setenv("WLCL_DEBUG_HUD", "1")
    assert debug_hud_enabled({"debug_hud": False})

    monkeypatch.delenv("WLCL_DEBUG_HUD", raising=False)
    monkeypatch.setenv("WLCL_DEBUG_TRACE", "true")
    assert debug_hud_enabled({"debug_hud": False})


def test_live_perf_metrics_snapshot() -> None:
    m = LivePerfMetrics()
    m.set_asr_busy(True)
    assert m.snapshot().asr_busy is True
    m.note_asr_infer(infer_ms=180.0, audio_sec=0.8, buffer_sec=2.5)
    snap = m.snapshot()
    assert snap.asr_busy is False
    assert snap.asr_infer_ms == 180.0
    assert snap.buffer_sec == 2.5
    assert snap.asr_rtf is not None
    assert abs(snap.asr_rtf - 0.225) < 1e-6
    m.note_out_queue(3)
    assert m.snapshot().out_queue == 3


def test_format_perf_chip() -> None:
    snap = LivePerfSnapshot(
        asr_infer_ms=180.0,
        asr_audio_sec=0.8,
        asr_rtf=0.225,
        asr_busy=False,
        buffer_sec=2.5,
        out_queue=1,
        ts_mono=1.0,
    )
    text = format_perf_chip(snap, vram_used_mb=3200.0, vram_total_mb=8192.0)
    assert "ASR 180ms" in text
    assert "rtf0.23" in text
    assert "q1" in text
    assert "buf2.5s" in text
    assert "VRAM 3.1/8.0G" in text

    busy = LivePerfSnapshot(
        asr_infer_ms=None,
        asr_audio_sec=None,
        asr_rtf=None,
        asr_busy=True,
        buffer_sec=None,
        out_queue=0,
        ts_mono=1.0,
    )
    assert format_perf_chip(busy).startswith("ASR …")


def test_query_vram_does_not_raise() -> None:
    info = query_vram()
    if info is not None:
        assert info.total_mb > 0
        assert info.used_mb >= 0


def test_overlay_debug_hud_visibility(
    qapp: QtWidgets.QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qapp
    monkeypatch.delenv("WLCL_DEBUG_HUD", raising=False)
    monkeypatch.delenv("WLCL_DEBUG_TRACE", raising=False)

    q: queue.Queue[CaptionUpdate] = queue.Queue()
    ov = SubtitleOverlay(
        text_queue=q,
        config={
            "language": "en",
            "debug_hud": False,
            "always_on_top": False,
            "window_width": 800,
            "font_size": 22,
            "font_color": "#FFFFFF",
            "bg_color": "#000000",
            "bg_alpha": 0.5,
            "padding": 16,
        },
    )
    assert ov.debug_hud_label.isHidden()

    PERF.note_asr_infer(infer_ms=120.0, audio_sec=0.5, buffer_sec=1.0)
    ov.apply_config({**ov.config, "debug_hud": True})
    assert not ov.debug_hud_label.isHidden()
    assert "ASR 120ms" in ov.debug_hud_label.text()
    ov.close()
