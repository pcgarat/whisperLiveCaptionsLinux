from __future__ import annotations

from typing import Protocol


class Translator(Protocol):
    """Extensión futura: traducir texto confirmado al español."""

    def translate(self, text: str, source_lang: str, target_lang: str = "es") -> str: ...


class NullTranslator:
    def translate(self, text: str, source_lang: str, target_lang: str = "es") -> str:
        return text
