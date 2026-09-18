"""Catálogo de presets generales de fábrica.

Cada entrada son **overrides** sobre la config vigente, no un snapshot completo:
un preset de vídeo fija idioma y bloque de modelos, y hereda del usuario lo que
es suyo (perfiles de latencia, apariencia, geometría de ventanas).

Los valores de modelo salen de mediciones en la máquina objetivo; ver
`docs/specs/fase2.9-presets-video-modelos-2026-09-13.md`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.asr.languages import AVAILABLE_LANGUAGES
from src.asr.translate import TRANSLATOR_MODEL_OPUS_MT

APP_PRESET_DEFAULT = "default"

# Prefijo de los presets pensados para subtitular vídeo de internet.
VIDEO_PRESET_PREFIX = "video-"

# Reconocimiento: large-v3-turbo en int8_float16 iguala a medium en WER con la
# mitad de VRAM (992 MB) y menos latencia. large-v3 no cabe junto al traductor.
VIDEO_ASR: dict[str, Any] = {
    "model": "large-v3-turbo",
    "compute_type": "int8_float16",
    "device": "cuda",
}

# Presentación: una sola línea, ya traducida, sin parciales que parpadeen.
VIDEO_CAPTIONS: dict[str, Any] = {
    "second_line_mode": "none",
    "captions_show_partials": False,
    "captions_allow_rewrite": True,
}

# Traducción: Opus-MT tc-big, un modelo por idioma de origen. Gana a NLLB-1.3B en
# VRAM (~0,3 GB vs ~2,0), latencia (8 ms vs 49 en frases cortas) y sobre todo en
# robustez: NLLB inventa turnos de diálogo en fragmentos de subtítulo.
VIDEO_TRANSLATION: dict[str, Any] = {
    "translation_enabled": True,
    "translation_target": "es",
    "translator_model": TRANSLATOR_MODEL_OPUS_MT,
    "translation_decode_preset": "balanced",
    "translation_sticky_mode": "committed",
}


def video_preset_id(language: str) -> str:
    """`en` → `video-en-es`; el idioma destino se omite si es el propio origen."""
    code = str(language).strip().lower()
    if code == "es":
        return f"{VIDEO_PRESET_PREFIX}es"
    return f"{VIDEO_PRESET_PREFIX}{code}-es"


def app_preset_label(preset_id: str) -> str:
    """Label legible para selectores de preset general.

    `default` → «Predeterminado», `video-en-es` → «Vídeo: Inglés». Un preset de
    usuario no tiene nombre bonito guardado (solo se guarda el id ya slugificado),
    así que se muestra tal cual.
    """
    pid = str(preset_id or "").strip()
    if pid == APP_PRESET_DEFAULT:
        return "Predeterminado"
    if pid.startswith(VIDEO_PRESET_PREFIX):
        rest = pid[len(VIDEO_PRESET_PREFIX) :]
        code = rest[:-3] if rest.endswith("-es") and rest != "es" else rest
        name = AVAILABLE_LANGUAGES.get(code, code.upper())
        return f"Vídeo: {name}"
    return pid


def _video_preset(language: str) -> dict[str, Any]:
    code = str(language).strip().lower()
    # Sin `installed_languages`: el idioma activo se añade solo al normalizar, así
    # que el preset no necesita pisar la lista que el usuario haya elegido.
    overrides: dict[str, Any] = {
        "language": code,
        **deepcopy(VIDEO_ASR),
        **deepcopy(VIDEO_CAPTIONS),
        **deepcopy(VIDEO_TRANSLATION),
    }
    if code == "es":
        # Origen y destino coinciden: transcribir sin cargar el traductor.
        overrides["translation_enabled"] = False
    return overrides


def _build_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {APP_PRESET_DEFAULT: {}}
    for code in AVAILABLE_LANGUAGES:
        catalog[video_preset_id(code)] = _video_preset(code)
    return catalog


# `default` sin overrides = snapshot de la config de fábrica tal cual.
APP_FACTORY_PRESET_OVERRIDES: dict[str, dict[str, Any]] = _build_catalog()
APP_FACTORY_PRESET_IDS = frozenset(APP_FACTORY_PRESET_OVERRIDES)


def is_factory_preset(preset_id: str | None) -> bool:
    return str(preset_id or "").strip() in APP_FACTORY_PRESET_IDS
