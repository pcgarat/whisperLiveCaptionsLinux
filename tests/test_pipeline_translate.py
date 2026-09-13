from __future__ import annotations

from src.asr.pipeline import translate_confirmed


class RecordingTranslator:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail = fail

    def translate(self, text: str, source_lang: str, target_lang: str = "es") -> str:
        self.calls.append((text, source_lang, target_lang))
        if self.fail:
            raise RuntimeError("boom")
        return f"ES:{text}"


def test_translate_confirmed_skips_when_disabled() -> None:
    t = RecordingTranslator()
    assert translate_confirmed(
        "hello",
        source_lang="en",
        target_lang="es",
        translation_enabled=False,
        translator=t,
    ) is None
    assert t.calls == []


def test_translate_confirmed_skips_same_language() -> None:
    t = RecordingTranslator()
    assert translate_confirmed(
        "hola",
        source_lang="es",
        target_lang="es",
        translation_enabled=True,
        translator=t,
    ) is None
    assert t.calls == []


def test_translate_confirmed_calls_translator_for_en_es() -> None:
    t = RecordingTranslator()
    out = translate_confirmed(
        "hello world",
        source_lang="en",
        target_lang="es",
        translation_enabled=True,
        translator=t,
    )
    assert out == "ES:hello world"
    assert t.calls == [("hello world", "en", "es")]


def test_translate_confirmed_swallows_errors() -> None:
    t = RecordingTranslator(fail=True)
    out = translate_confirmed(
        "hello",
        source_lang="en",
        target_lang="es",
        translation_enabled=True,
        translator=t,
    )
    assert out is None
    assert len(t.calls) == 1
