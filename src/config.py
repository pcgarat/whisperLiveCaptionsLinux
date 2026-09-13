from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

LATENCY_FACTORY_PRESETS: dict[str, dict[str, float | int]] = {
    "stable": {"agreement_n": 2, "max_latency_sec": 3.0, "min_chunk_seconds": 0.8},
    "low": {"agreement_n": 1, "max_latency_sec": 1.0, "min_chunk_seconds": 0.35},
}

DEFAULTS: dict[str, Any] = {
    "language": "en",
    "model": "medium",
    "compute_type": "float16",
    "device": "cuda",
    "audio_monitor": "",
    "buffer_trimming_sec": 15.0,
    "use_vad": True,
    "latency_mode": "stable",
    "latency_profiles": deepcopy(LATENCY_FACTORY_PRESETS),
    "always_on_top": True,
    "font_size": 28,
    "font_color": "#ffffff",
    "bg_color": "#000000",
    "bg_alpha": 0.55,
    "padding": 24,
    "window_pos": None,
    "window_width": 900,
}

CONFIG_NAME = "config.json"


def default_config_path(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / CONFIG_NAME


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _clamp_profile(raw: dict[str, Any] | None, factory: dict[str, float | int]) -> dict[str, float | int]:
    src = factory if not isinstance(raw, dict) else {**factory, **raw}
    return {
        "agreement_n": int(_clamp(int(src["agreement_n"]), 1, 5)),
        "max_latency_sec": float(_clamp(float(src["max_latency_sec"]), 0.5, 5.0)),
        "min_chunk_seconds": float(_clamp(float(src["min_chunk_seconds"]), 0.2, 5.0)),
    }


def _migrate_latency_profiles(data: dict[str, Any], mode: str) -> dict[str, dict[str, float | int]]:
    profiles_in = data.get("latency_profiles")
    profiles: dict[str, dict[str, float | int]] = {
        name: deepcopy(preset) for name, preset in LATENCY_FACTORY_PRESETS.items()
    }

    if isinstance(profiles_in, dict):
        for name, factory in LATENCY_FACTORY_PRESETS.items():
            profiles[name] = _clamp_profile(profiles_in.get(name), factory)
        return profiles

    # Config fase 1: knobs top-level alimentan el modo activo; el otro modo queda de fábrica.
    legacy: dict[str, Any] = {}
    if "agreement_n" in data:
        legacy["agreement_n"] = data["agreement_n"]
    if "min_chunk_seconds" in data:
        legacy["min_chunk_seconds"] = data["min_chunk_seconds"]
    if "max_latency_sec" in data:
        legacy["max_latency_sec"] = data["max_latency_sec"]
    if legacy:
        profiles[mode] = _clamp_profile({**LATENCY_FACTORY_PRESETS[mode], **legacy}, LATENCY_FACTORY_PRESETS[mode])
    return profiles


def effective_latency_profile(cfg: dict[str, Any]) -> dict[str, float | int]:
    mode = str(cfg.get("latency_mode", "stable"))
    if mode not in LATENCY_FACTORY_PRESETS:
        mode = "stable"
    profiles = cfg.get("latency_profiles") or LATENCY_FACTORY_PRESETS
    raw = profiles.get(mode) if isinstance(profiles, dict) else None
    return _clamp_profile(raw if isinstance(raw, dict) else None, LATENCY_FACTORY_PRESETS[mode])


def reset_latency_profile(cfg: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    out = deepcopy(cfg)
    active = mode or str(out.get("latency_mode", "stable"))
    if active not in LATENCY_FACTORY_PRESETS:
        active = "stable"
    profiles = out.get("latency_profiles")
    if not isinstance(profiles, dict):
        profiles = deepcopy(LATENCY_FACTORY_PRESETS)
    else:
        profiles = deepcopy(profiles)
    profiles[active] = deepcopy(LATENCY_FACTORY_PRESETS[active])
    out["latency_profiles"] = profiles
    out["latency_mode"] = active
    return validate_config(out)


def beam_size_for_mode(mode: str) -> int:
    return 1 if mode == "low" else 5


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    raw = dict(data)
    cfg = deepcopy(DEFAULTS)
    cfg.update(raw)

    cfg["font_size"] = int(_clamp(int(cfg["font_size"]), 10, 100))
    cfg["bg_alpha"] = float(_clamp(float(cfg["bg_alpha"]), 0.05, 1.0))
    cfg["padding"] = int(_clamp(int(cfg["padding"]), 0, 100))
    cfg["window_width"] = int(_clamp(int(cfg["window_width"]), 300, 2400))
    cfg["buffer_trimming_sec"] = float(_clamp(float(cfg["buffer_trimming_sec"]), 5.0, 60.0))
    cfg["language"] = str(cfg["language"]).strip().lower() or "en"
    cfg["model"] = str(cfg["model"]).strip() or "medium"
    cfg["latency_mode"] = str(cfg.get("latency_mode", "stable"))
    if cfg["latency_mode"] not in LATENCY_FACTORY_PRESETS:
        cfg["latency_mode"] = "stable"
    cfg["use_vad"] = bool(cfg["use_vad"])
    cfg["always_on_top"] = bool(cfg.get("always_on_top", True))
    cfg["audio_monitor"] = str(cfg.get("audio_monitor") or "")

    cfg["latency_profiles"] = _migrate_latency_profiles(raw, cfg["latency_mode"])

    # Espejo derivado para lecturas legacy / depuración; la fuente de verdad es el profile.
    profile = effective_latency_profile(cfg)
    cfg["agreement_n"] = int(profile["agreement_n"])
    cfg["max_latency_sec"] = float(profile["max_latency_sec"])
    cfg["min_chunk_seconds"] = float(profile["min_chunk_seconds"])

    pos = cfg.get("window_pos")
    if pos is not None:
        if (
            not isinstance(pos, (list, tuple))
            or len(pos) != 2
            or not all(isinstance(v, (int, float)) for v in pos)
        ):
            cfg["window_pos"] = None
        else:
            cfg["window_pos"] = [int(pos[0]), int(pos[1])]

    return cfg


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or default_config_path()
    if not config_path.exists():
        return validate_config({})
    with config_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        return validate_config({})
    return validate_config(raw)


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    validated = validate_config(cfg)
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(validated, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return config_path
