from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionUpdate:
    text: str
    is_final: bool
    language: str
    ts_mono: float
    translated_text: str | None = None
    # Monotonic id por confirmación; la UI ignora traducción si ya hay un seq mayor.
    seq: int = 0
    # Si True, `translated_text` es un delta a concatenar (no sustituye la línea ES).
    translation_append: bool = False
