from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

LATENCY_FACTORY_PRESETS: dict[str, dict[str, float | int]] = {
    "stable": {"agreement_n": 2, "max_latency_sec": 3.0, "min_chunk_seconds": 0.8},
    "low": {"agreement_n": 1, "max_latency_sec": 1.0, "min_chunk_seconds": 0.35},
}

# Decoding NLLB (fábrica). `custom` no es fábrica: perfil editable persistente.
TRANSLATION_FACTORY_PRESETS: dict[str, dict[str, float | int]] = {
    "fast": {"beam_size": 2, "length_penalty": 1.0, "no_repeat_ngram_size": 0},
    "balanced": {"beam_size": 4, "length_penalty": 1.0, "no_repeat_ngram_size": 3},
    "quality": {"beam_size": 6, "length_penalty": 1.1, "no_repeat_ngram_size": 3},
}
TRANSLATION_FACTORY_PRESET_IDS = frozenset(TRANSLATION_FACTORY_PRESETS)
TRANSLATION_RESERVED_PRESET_IDS = TRANSLATION_FACTORY_PRESET_IDS | {"custom"}
TRANSLATION_PRESET_LABELS: dict[str, str] = {
    "fast": "Rápido",
    "balanced": "Equilibrado",
    "quality": "Calidad",
    "custom": "Custom",
}

# Con traducción ON: qué mostrar como segunda línea (nunca más de 2 líneas de caption).
SECOND_LINE_MODES = ("live_asr", "original", "none")

# Alineación horizontal del texto en el overlay.
TEXT_ALIGN_MODES = ("center", "left")
TEXT_ALIGN_LABELS: dict[str, str] = {
    "center": "Centro",
    "left": "Izquierda",
}

# Sticky: reutilizar tramos ya traducidos; partials también traduce la hipótesis.
TRANSLATION_STICKY_MODES = ("off", "committed", "partials")
TRANSLATION_STICKY_LABELS: dict[str, str] = {
    "off": "Normal (como ahora)",
    "committed": "Sticky (solo confirmados)",
    "partials": "Sticky + parciales",
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
    "installed_languages": ["en", "es"],
    "translation_enabled": False,
    "translation_target": "es",
    "translation_sticky_mode": "off",
    "second_line_mode": "live_asr",
    "captions_show_partials": True,
    "captions_allow_rewrite": True,
    "translator_model": "nllb-200-distilled-ct2",
    "translation_decode_preset": "balanced",
    "translation_profiles": {
        **deepcopy(TRANSLATION_FACTORY_PRESETS),
        "custom": deepcopy(TRANSLATION_FACTORY_PRESETS["balanced"]),
    },
    "always_on_top": True,
    "font_size": 28,
    "font_color": "#ffffff",
    "bg_color": "#000000",
    "bg_alpha": 0.55,
    "padding": 24,
    "text_align": "center",
    "window_pos": None,
    "window_width": 900,
    "window_height": None,
    "settings_window_pos": None,
    "settings_window_width": 560,
    "settings_window_height": 720,
}

CONFIG_NAME = "config.json"


def default_config_path(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    return base / CONFIG_NAME


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _clamp_profile(
    raw: dict[str, Any] | None, factory: dict[str, float | int]
) -> dict[str, float | int]:
    src = factory if not isinstance(raw, dict) else {**factory, **raw}
    return {
        "agreement_n": int(_clamp(int(src["agreement_n"]), 1, 5)),
        "max_latency_sec": float(_clamp(float(src["max_latency_sec"]), 0.5, 5.0)),
        "min_chunk_seconds": float(_clamp(float(src["min_chunk_seconds"]), 0.2, 5.0)),
    }


def _migrate_latency_profiles(
    data: dict[str, Any], mode: str
) -> dict[str, dict[str, float | int]]:
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
        profiles[mode] = _clamp_profile(
            {**LATENCY_FACTORY_PRESETS[mode], **legacy}, LATENCY_FACTORY_PRESETS[mode]
        )
    return profiles


def effective_latency_profile(cfg: dict[str, Any]) -> dict[str, float | int]:
    mode = str(cfg.get("latency_mode", "stable"))
    if mode not in LATENCY_FACTORY_PRESETS:
        mode = "stable"
    profiles = cfg.get("latency_profiles") or LATENCY_FACTORY_PRESETS
    raw = profiles.get(mode) if isinstance(profiles, dict) else None
    return _clamp_profile(
        raw if isinstance(raw, dict) else None, LATENCY_FACTORY_PRESETS[mode]
    )


def reset_latency_profile(
    cfg: dict[str, Any], mode: str | None = None
) -> dict[str, Any]:
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


def _clamp_translation_decode(
    raw: dict[str, Any] | None,
    fallback: dict[str, float | int],
) -> dict[str, float | int]:
    src = fallback if not isinstance(raw, dict) else {**fallback, **raw}
    return {
        "beam_size": int(_clamp(int(src["beam_size"]), 1, 8)),
        "length_penalty": float(_clamp(float(src["length_penalty"]), 0.6, 1.5)),
        "no_repeat_ngram_size": int(_clamp(int(src["no_repeat_ngram_size"]), 0, 5)),
    }


def _migrate_translation_profiles(
    data: dict[str, Any],
) -> dict[str, dict[str, float | int]]:
    balanced = TRANSLATION_FACTORY_PRESETS["balanced"]
    profiles: dict[str, dict[str, float | int]] = {
        name: deepcopy(preset) for name, preset in TRANSLATION_FACTORY_PRESETS.items()
    }
    profiles["custom"] = deepcopy(balanced)

    profiles_in = data.get("translation_profiles")
    if not isinstance(profiles_in, dict):
        return profiles

    custom_raw = profiles_in.get("custom")
    profiles["custom"] = _clamp_translation_decode(
        custom_raw if isinstance(custom_raw, dict) else None,
        balanced,
    )

    for name, raw in profiles_in.items():
        key = str(name).strip().lower()
        if not key or key in TRANSLATION_RESERVED_PRESET_IDS:
            continue
        if not isinstance(raw, dict):
            continue
        profiles[key] = _clamp_translation_decode(raw, balanced)
    return profiles


def _normalize_translation_decode_preset(
    raw: Any, profiles: dict[str, dict[str, float | int]]
) -> str:
    preset = str(raw or "balanced").strip().lower() or "balanced"
    if preset in profiles:
        return preset
    return "balanced"


def effective_translation_decode(cfg: dict[str, Any]) -> dict[str, float | int]:
    profiles = cfg.get("translation_profiles")
    if not isinstance(profiles, dict):
        profiles = DEFAULTS["translation_profiles"]
    preset = _normalize_translation_decode_preset(
        cfg.get("translation_decode_preset"), profiles
    )
    if preset in TRANSLATION_FACTORY_PRESETS:
        return deepcopy(TRANSLATION_FACTORY_PRESETS[preset])
    raw = profiles.get(preset)
    fallback = TRANSLATION_FACTORY_PRESETS["balanced"]
    return _clamp_translation_decode(raw if isinstance(raw, dict) else None, fallback)


def slugify_translation_preset_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif ch in (" ", "-", "_"):
            if out and not prev_dash:
                out.append("-")
                prev_dash = True
    slug = "".join(out).strip("-_")
    return slug


def add_translation_user_preset(
    cfg: dict[str, Any],
    name: str,
    decode: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Añade o actualiza un preset de usuario y lo deja activo. Raises ValueError si el nombre no vale."""
    slug = slugify_translation_preset_name(name)
    if not slug:
        raise ValueError("Nombre de preset vacío o inválido")
    if slug in TRANSLATION_RESERVED_PRESET_IDS:
        raise ValueError(f"El nombre «{slug}» está reservado")

    out = deepcopy(cfg)
    profiles = _migrate_translation_profiles(out)
    values = _clamp_translation_decode(
        decode if isinstance(decode, dict) else effective_translation_decode(out),
        TRANSLATION_FACTORY_PRESETS["balanced"],
    )
    profiles[slug] = values
    out["translation_profiles"] = profiles
    out["translation_decode_preset"] = slug
    return validate_config(out)


def delete_translation_user_preset(
    cfg: dict[str, Any], preset_id: str
) -> dict[str, Any]:
    """Borra un preset de usuario. Si era el activo, pasa a custom con snapshot actual."""
    key = str(preset_id or "").strip().lower()
    if not key or key in TRANSLATION_RESERVED_PRESET_IDS:
        raise ValueError("No se puede borrar un preset de fábrica o Custom")

    out = deepcopy(cfg)
    profiles = _migrate_translation_profiles(out)
    if key not in profiles:
        raise ValueError(f"Preset desconocido: {key}")

    snapshot = effective_translation_decode(
        {**out, "translation_profiles": profiles, "translation_decode_preset": key}
    )
    del profiles[key]
    profiles["custom"] = snapshot
    out["translation_profiles"] = profiles
    if str(out.get("translation_decode_preset", "")).strip().lower() == key:
        out["translation_decode_preset"] = "custom"
    return validate_config(out)


def translation_user_preset_ids(cfg: dict[str, Any]) -> list[str]:
    profiles = cfg.get("translation_profiles")
    if not isinstance(profiles, dict):
        return []
    return sorted(
        key
        for key in profiles
        if str(key).strip().lower() not in TRANSLATION_RESERVED_PRESET_IDS
    )


def _normalize_installed_languages(raw: Any, language: str) -> list[str]:
    if isinstance(raw, list):
        langs = [str(item).strip().lower() for item in raw if str(item).strip()]
    else:
        langs = list(DEFAULTS["installed_languages"])
    # Mantener orden de aparición; language activo siempre disponible en el menú.
    seen: set[str] = set()
    out: list[str] = []
    for code in langs:
        if code not in seen:
            seen.add(code)
            out.append(code)
    if language and language not in seen:
        out.insert(0, language)
    if not out:
        out = ["en", "es"]
    return out


def _normalize_translation_sticky_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower() or "off"
    if mode not in TRANSLATION_STICKY_MODES:
        return "off"
    return mode


def _normalize_second_line_mode(raw: dict[str, Any]) -> str:
    if "second_line_mode" in raw:
        mode = str(raw.get("second_line_mode") or "").strip().lower()
    elif "show_asr_line" in raw:
        # Legacy bool: True → ASR en vivo; False → sin segunda línea.
        mode = "live_asr" if bool(raw.get("show_asr_line")) else "none"
    else:
        mode = str(DEFAULTS["second_line_mode"])
    if mode not in SECOND_LINE_MODES:
        return str(DEFAULTS["second_line_mode"])
    return mode


def _normalize_window_pos(raw: Any) -> list[int] | None:
    if raw is None:
        return None
    if (
        not isinstance(raw, (list, tuple))
        or len(raw) != 2
        or not all(isinstance(v, (int, float)) for v in raw)
    ):
        return None
    return [int(raw[0]), int(raw[1])]


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    raw = dict(data)
    cfg = deepcopy(DEFAULTS)
    cfg.update(raw)

    cfg["font_size"] = int(_clamp(int(cfg["font_size"]), 10, 100))
    cfg["bg_alpha"] = float(_clamp(float(cfg["bg_alpha"]), 0.05, 1.0))
    cfg["padding"] = int(_clamp(int(cfg["padding"]), 0, 100))
    align = str(cfg.get("text_align") or "").strip().lower()
    cfg["text_align"] = align if align in TEXT_ALIGN_MODES else "center"
    cfg["window_width"] = int(_clamp(int(cfg["window_width"]), 300, 2400))
    height = cfg.get("window_height")
    if height is None:
        cfg["window_height"] = None
    else:
        cfg["window_height"] = int(_clamp(int(height), 120, 1600))
    cfg["settings_window_width"] = int(
        _clamp(int(cfg.get("settings_window_width", 560)), 520, 2000)
    )
    settings_h = cfg.get("settings_window_height")
    if settings_h is None:
        cfg["settings_window_height"] = int(DEFAULTS["settings_window_height"])
    else:
        cfg["settings_window_height"] = int(_clamp(int(settings_h), 640, 1600))
    cfg["buffer_trimming_sec"] = float(
        _clamp(float(cfg["buffer_trimming_sec"]), 5.0, 60.0)
    )
    cfg["language"] = str(cfg["language"]).strip().lower() or "en"
    cfg["model"] = str(cfg["model"]).strip() or "medium"
    cfg["latency_mode"] = str(cfg.get("latency_mode", "stable"))
    if cfg["latency_mode"] not in LATENCY_FACTORY_PRESETS:
        cfg["latency_mode"] = "stable"
    cfg["use_vad"] = bool(cfg["use_vad"])
    cfg["always_on_top"] = bool(cfg.get("always_on_top", True))
    cfg["audio_monitor"] = str(cfg.get("audio_monitor") or "")
    cfg["translation_enabled"] = bool(cfg.get("translation_enabled", False))
    cfg["translation_sticky_mode"] = _normalize_translation_sticky_mode(
        cfg.get("translation_sticky_mode")
    )
    cfg["second_line_mode"] = _normalize_second_line_mode(raw)
    cfg.pop("show_asr_line", None)
    cfg["captions_show_partials"] = bool(cfg.get("captions_show_partials", True))
    cfg["captions_allow_rewrite"] = bool(cfg.get("captions_allow_rewrite", True))
    cfg["translation_target"] = (
        str(cfg.get("translation_target") or "es").strip().lower() or "es"
    )
    cfg["translator_model"] = (
        str(cfg.get("translator_model") or "nllb-200-distilled-ct2").strip()
        or "nllb-200-distilled-ct2"
    )
    cfg["installed_languages"] = _normalize_installed_languages(
        cfg.get("installed_languages"),
        cfg["language"],
    )

    cfg["latency_profiles"] = _migrate_latency_profiles(raw, cfg["latency_mode"])
    cfg["translation_profiles"] = _migrate_translation_profiles(raw)
    cfg["translation_decode_preset"] = _normalize_translation_decode_preset(
        cfg.get("translation_decode_preset"),
        cfg["translation_profiles"],
    )

    # Espejo derivado para lecturas legacy / depuración; la fuente de verdad es el profile.
    profile = effective_latency_profile(cfg)
    cfg["agreement_n"] = int(profile["agreement_n"])
    cfg["max_latency_sec"] = float(profile["max_latency_sec"])
    cfg["min_chunk_seconds"] = float(profile["min_chunk_seconds"])

    cfg["window_pos"] = _normalize_window_pos(cfg.get("window_pos"))
    cfg["settings_window_pos"] = _normalize_window_pos(cfg.get("settings_window_pos"))

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
