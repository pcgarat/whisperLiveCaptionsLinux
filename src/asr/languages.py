from __future__ import annotations

from collections.abc import Iterable

# Catálogo de idiomas fuente instalables (ASR + mapa NLLB).
# Orden = orden de presentación en UI.
AVAILABLE_LANGUAGES: dict[str, str] = {
    "en": "Inglés",
    "es": "Español",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
}


def normalize_lang_code(code: str) -> str:
    return str(code).strip().lower()


def language_label(code: str) -> str:
    normalized = normalize_lang_code(code)
    name = AVAILABLE_LANGUAGES.get(normalized, normalized)
    return f"{name} ({normalized})"


def installed_language_codes(raw: Iterable[str] | None) -> list[str]:
    if raw is None:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        code = normalize_lang_code(item)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def pending_languages(installed: Iterable[str] | None) -> list[str]:
    have = set(installed_language_codes(installed))
    return [code for code in AVAILABLE_LANGUAGES if code not in have]


def merge_installed_languages(
    installed: Iterable[str] | None,
    new_codes: Iterable[str],
) -> list[str]:
    out = installed_language_codes(installed)
    seen = set(out)
    catalog_order = list(AVAILABLE_LANGUAGES.keys())
    incoming = installed_language_codes(new_codes)
    # Preferir orden del catálogo para los nuevos; ignorar códigos desconocidos.
    for code in catalog_order:
        if code in incoming and code not in seen:
            out.append(code)
            seen.add(code)
    for code in incoming:
        if code not in seen and code in AVAILABLE_LANGUAGES:
            out.append(code)
            seen.add(code)
    return out
