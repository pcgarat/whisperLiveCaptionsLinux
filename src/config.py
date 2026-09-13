from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "language": "en",
    "model": "medium",
    "compute_type": "float16",
    "device": "cuda",
    "audio_monitor": "",
    "min_chunk_seconds": 0.8,
    "agreement_n": 2,
    "buffer_trimming_sec": 15.0,
    "use_vad": True,
    "latency_mode": "stable",
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


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    cfg = deepcopy(DEFAULTS)
    cfg.update(data)

    cfg["font_size"] = int(_clamp(int(cfg["font_size"]), 10, 100))
    cfg["bg_alpha"] = float(_clamp(float(cfg["bg_alpha"]), 0.05, 1.0))
    cfg["padding"] = int(_clamp(int(cfg["padding"]), 0, 100))
    cfg["window_width"] = int(_clamp(int(cfg["window_width"]), 300, 2400))
    cfg["min_chunk_seconds"] = float(_clamp(float(cfg["min_chunk_seconds"]), 0.2, 5.0))
    cfg["agreement_n"] = int(_clamp(int(cfg["agreement_n"]), 1, 5))
    cfg["buffer_trimming_sec"] = float(_clamp(float(cfg["buffer_trimming_sec"]), 5.0, 60.0))
    cfg["language"] = str(cfg["language"]).strip().lower() or "en"
    cfg["model"] = str(cfg["model"]).strip() or "medium"
    cfg["latency_mode"] = str(cfg.get("latency_mode", "stable"))
    if cfg["latency_mode"] not in {"stable", "low"}:
        cfg["latency_mode"] = "stable"
    cfg["use_vad"] = bool(cfg["use_vad"])
    cfg["always_on_top"] = bool(cfg.get("always_on_top", True))
    cfg["audio_monitor"] = str(cfg.get("audio_monitor") or "")

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
