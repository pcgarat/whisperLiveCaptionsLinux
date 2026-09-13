from __future__ import annotations

import json
from pathlib import Path

from src.config import (
    DEFAULTS,
    LATENCY_FACTORY_PRESETS,
    beam_size_for_mode,
    effective_latency_profile,
    load_config,
    reset_latency_profile,
    save_config,
    validate_config,
)


def test_load_missing_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "config.json")
    assert cfg["language"] == DEFAULTS["language"]
    assert cfg["model"] == DEFAULTS["model"]
    assert cfg["latency_mode"] == "stable"
    assert cfg["latency_profiles"]["stable"] == LATENCY_FACTORY_PRESETS["stable"]
    assert cfg["latency_profiles"]["low"] == LATENCY_FACTORY_PRESETS["low"]
    assert cfg["translation_enabled"] is False
    assert cfg["translation_target"] == "es"
    assert cfg["second_line_mode"] == "live_asr"
    assert cfg["installed_languages"] == ["en", "es"]
    assert cfg["translator_model"] == "nllb-200-distilled-ct2"


def test_validate_clamps_ranges() -> None:
    cfg = validate_config(
        {
            "font_size": 999,
            "bg_alpha": 2.5,
            "padding": -3,
            "latency_mode": "nope",
            "latency_profiles": {
                "stable": {
                    "agreement_n": 99,
                    "max_latency_sec": 0.1,
                    "min_chunk_seconds": 0.01,
                }
            },
        }
    )
    assert cfg["font_size"] == 100
    assert cfg["bg_alpha"] == 1.0
    assert cfg["padding"] == 0
    assert cfg["latency_mode"] == "stable"
    assert cfg["latency_profiles"]["stable"]["agreement_n"] == 5
    assert cfg["latency_profiles"]["stable"]["max_latency_sec"] == 0.5
    assert cfg["latency_profiles"]["stable"]["min_chunk_seconds"] == 0.2


def test_migrate_legacy_top_level_into_active_mode() -> None:
    cfg = validate_config(
        {
            "latency_mode": "low",
            "agreement_n": 3,
            "min_chunk_seconds": 1.2,
        }
    )
    assert cfg["latency_profiles"]["low"]["agreement_n"] == 3
    assert abs(cfg["latency_profiles"]["low"]["min_chunk_seconds"] - 1.2) < 1e-9
    assert cfg["latency_profiles"]["stable"] == LATENCY_FACTORY_PRESETS["stable"]
    assert effective_latency_profile(cfg)["agreement_n"] == 3


def test_save_and_load_roundtrip_preserves_profiles(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_config(
        {
            "language": "en",
            "font_size": 40,
            "bg_alpha": 0.33,
            "latency_mode": "low",
            "latency_profiles": {
                "stable": dict(LATENCY_FACTORY_PRESETS["stable"]),
                "low": {"agreement_n": 1, "max_latency_sec": 0.8, "min_chunk_seconds": 0.4},
            },
        },
        path,
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["latency_mode"] == "low"
    assert abs(raw["latency_profiles"]["low"]["max_latency_sec"] - 0.8) < 1e-9
    loaded = load_config(path)
    assert loaded["font_size"] == 40
    assert abs(loaded["bg_alpha"] - 0.33) < 1e-9
    assert loaded["latency_mode"] == "low"
    assert abs(loaded["latency_profiles"]["low"]["min_chunk_seconds"] - 0.4) < 1e-9


def test_save_and_load_roundtrip_preserves_translation_flags(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_config(
        {
            "language": "en",
            "translation_enabled": True,
            "translation_target": "es",
            "second_line_mode": "none",
            "installed_languages": ["en", "es", "fr"],
            "translator_model": "nllb-200-distilled-ct2",
        },
        path,
    )
    loaded = load_config(path)
    assert loaded["translation_enabled"] is True
    assert loaded["translation_target"] == "es"
    assert loaded["second_line_mode"] == "none"
    assert loaded["installed_languages"] == ["en", "es", "fr"]
    assert loaded["translator_model"] == "nllb-200-distilled-ct2"


def test_migrate_legacy_show_asr_line_to_second_line_mode() -> None:
    assert validate_config({"show_asr_line": True})["second_line_mode"] == "live_asr"
    assert validate_config({"show_asr_line": False})["second_line_mode"] == "none"
    migrated = validate_config({"show_asr_line": False, "second_line_mode": "original"})
    assert migrated["second_line_mode"] == "original"
    assert "show_asr_line" not in migrated
    assert validate_config({"second_line_mode": "nope"})["second_line_mode"] == "live_asr"


def test_installed_languages_includes_active_language() -> None:
    cfg = validate_config({"language": "fr", "installed_languages": ["en", "es"]})
    assert cfg["language"] == "fr"
    assert cfg["installed_languages"][0] == "fr"
    assert "en" in cfg["installed_languages"]
    assert "es" in cfg["installed_languages"]


def test_beam_size_for_mode() -> None:
    assert beam_size_for_mode("stable") == 5
    assert beam_size_for_mode("low") == 1


def test_reset_latency_profile_restores_factory() -> None:
    cfg = validate_config(
        {
            "latency_mode": "low",
            "latency_profiles": {
                "low": {"agreement_n": 4, "max_latency_sec": 2.5, "min_chunk_seconds": 1.0},
                "stable": {"agreement_n": 5, "max_latency_sec": 4.0, "min_chunk_seconds": 1.5},
            },
        }
    )
    reset = reset_latency_profile(cfg, "low")
    assert reset["latency_profiles"]["low"] == LATENCY_FACTORY_PRESETS["low"]
    assert reset["latency_profiles"]["stable"]["agreement_n"] == 5
