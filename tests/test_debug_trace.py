from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.debug.trace import SessionTracer, config_snapshot, diff_config


def test_config_snapshot_keeps_tuning_knobs_only() -> None:
    snap = config_snapshot(
        {
            "language": "en",
            "latency_mode": "low",
            "font_size": 40,
            "window_pos": [1, 2],
            "translation_enabled": True,
        }
    )
    assert snap["language"] == "en"
    assert snap["latency_mode"] == "low"
    assert snap["translation_enabled"] is True
    assert "font_size" not in snap
    assert "window_pos" not in snap


def test_diff_config_reports_from_to() -> None:
    changes = diff_config(
        {"latency_mode": "stable", "translation_enabled": False},
        {"latency_mode": "low", "translation_enabled": False},
    )
    assert changes == {
        "latency_mode": {"from": "stable", "to": "low"},
    }


def test_session_tracer_flush_writes_summary(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    tracer = SessionTracer(
        path,
        {"language": "en", "latency_mode": "stable", "font_size": 99},
        wall_start=datetime(2026, 9, 13, tzinfo=timezone.utc),
        mono_start=100.0,
    )
    tracer.asr_infer(audio_sec=1.0, infer_ms=250.0, hyp_len=5, hyp_preview="hello")
    tracer.commit(seq=1, text="hello", is_extension=False, ts_mono=100.2)
    tracer.tx_schedule(seq=1, gen=1, is_partial=False, chars=5)
    tracer.tx_schedule(
        seq=1, gen=2, is_partial=False, chars=8, coalesced_prev_gen=1
    )
    tracer.tx_done(
        seq=1,
        gen=2,
        decode_ms=40.0,
        chars_in=8,
        chars_out=10,
        is_partial=False,
        ts_mono=100.5,
    )
    assert tracer.note_config(
        {"language": "en", "latency_mode": "low", "font_size": 99},
        reason="settings",
        applied="asr_restart",
    )
    assert not tracer.note_config(
        {"language": "en", "latency_mode": "low", "font_size": 12},
        reason="save",
    )

    written = tracer.flush()
    assert written == path
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["config"]["latency_mode"] == "stable"
    assert doc["config_final"]["latency_mode"] == "low"
    assert "font_size" not in doc["config"]
    assert doc["summary"]["commits"] == 1
    assert doc["summary"]["coalesce_skips"] == 1
    assert doc["summary"]["config_changes"] == 1
    assert doc["summary"]["asr_infer"]["count"] == 1
    assert doc["summary"]["tx_lag"]["count"] == 1
    assert doc["summary"]["tx_lag"]["p50_ms"] == 300.0
    types = [e["type"] for e in doc["events"]]
    assert "asr_infer" in types
    assert "commit" in types
    assert "tx_coalesce_skip" in types
    assert "tx_done" in types
    assert "config_change" in types
    change = next(e for e in doc["events"] if e["type"] == "config_change")
    assert change["keys"] == ["latency_mode"]
    assert change["changes"]["latency_mode"] == {"from": "stable", "to": "low"}
    assert change["applied"] == "asr_restart"
