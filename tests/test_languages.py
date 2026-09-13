from __future__ import annotations

from src.asr.languages import (
    AVAILABLE_LANGUAGES,
    language_label,
    merge_installed_languages,
    pending_languages,
)
from src.asr.translate import NLLB_LANG_CODES


def test_catalog_aligned_with_nllb() -> None:
    assert set(AVAILABLE_LANGUAGES) == set(NLLB_LANG_CODES)
    assert list(AVAILABLE_LANGUAGES)[:2] == ["en", "es"]


def test_language_label() -> None:
    assert language_label("fr") == "Francés (fr)"
    assert language_label(" FR ") == "Francés (fr)"


def test_pending_excludes_installed() -> None:
    pending = pending_languages(["en", "es"])
    assert "en" not in pending
    assert "es" not in pending
    assert "fr" in pending


def test_merge_installed_preserves_order_and_dedupes() -> None:
    merged = merge_installed_languages(["en", "es"], ["fr", "en", "de", "xx"])
    assert merged == ["en", "es", "fr", "de"]
