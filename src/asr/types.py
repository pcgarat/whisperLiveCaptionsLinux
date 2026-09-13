from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionUpdate:
    text: str
    is_final: bool
    language: str
    ts_mono: float
    translated_text: str | None = None
