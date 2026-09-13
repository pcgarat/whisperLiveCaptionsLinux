from __future__ import annotations

import json
from pathlib import Path

from src.config import DEFAULTS, load_config, save_config, validate_config


def test_load_missing_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "config.json")
    assert cfg["language"] == DEFAULTS["language"]
    assert cfg["model"] == DEFAULTS["model"]
    assert cfg["latency_mode"] == "stable"


def test_validate_clamps_ranges() -> None:
    cfg = validate_config(
        {
            "font_size": 999,
            "bg_alpha": 2.5,
            "padding": -3,
            "latency_mode": "nope",
        }
    )
    assert cfg["font_size"] == 100
    assert cfg["bg_alpha"] == 1.0
    assert cfg["padding"] == 0
    assert cfg["latency_mode"] == "stable"


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_config({"language": "en", "font_size": 40, "bg_alpha": 0.33}, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["font_size"] == 40
    loaded = load_config(path)
    assert loaded["font_size"] == 40
    assert abs(loaded["bg_alpha"] - 0.33) < 1e-9
