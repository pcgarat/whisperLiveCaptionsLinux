from __future__ import annotations

import queue

from src.asr.pipeline import AsrPipeline, translate_confirmed
from src.asr.translate import NullTranslator
from src.config import TRANSLATION_FACTORY_PRESETS, validate_config


class RecordingTranslator:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, str, dict[str, float | int] | None]] = []
        self.fail = fail

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "es",
        decode: dict[str, float | int] | None = None,
    ) -> str:
        self.calls.append((text, source_lang, target_lang, decode))
        if self.fail:
            raise RuntimeError("boom")
        return f"ES:{text}"


def test_translate_confirmed_skips_when_disabled() -> None:
    t = RecordingTranslator()
    assert (
        translate_confirmed(
            "hello",
            source_lang="en",
            target_lang="es",
            translation_enabled=False,
            translator=t,
        )
        is None
    )
    assert t.calls == []


def test_translate_confirmed_skips_same_language() -> None:
    t = RecordingTranslator()
    assert (
        translate_confirmed(
            "hola",
            source_lang="es",
            target_lang="es",
            translation_enabled=True,
            translator=t,
        )
        is None
    )
    assert t.calls == []


def test_translate_confirmed_calls_translator_for_en_es() -> None:
    t = RecordingTranslator()
    decode = {"beam_size": 6, "length_penalty": 1.1, "no_repeat_ngram_size": 3}
    out = translate_confirmed(
        "hello world",
        source_lang="en",
        target_lang="es",
        translation_enabled=True,
        translator=t,
        decode=decode,
    )
    assert out == "ES:hello world"
    assert t.calls == [("hello world", "en", "es", decode)]


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


def test_apply_translation_settings_hot_swaps_without_start() -> None:
    cfg = validate_config(
        {
            "translation_enabled": False,
            "translation_target": "es",
            "translator_model": "nllb-200-distilled-ct2",
            "device": "cpu",
            "language": "en",
            "latency_mode": "stable",
        }
    )
    pipeline = AsrPipeline(cfg, queue.Queue(), translator=NullTranslator())
    assert isinstance(pipeline.translation_snapshot()[2], NullTranslator)

    cfg["translation_enabled"] = True
    pipeline.apply_translation_settings(cfg)
    enabled, target, translator, decode = pipeline.translation_snapshot()
    assert enabled is True
    assert target == "es"
    assert type(translator).__name__ == "NllbCt2Translator"
    assert not getattr(translator, "is_loaded", True)
    assert decode == TRANSLATION_FACTORY_PRESETS["balanced"]

    cfg["translation_enabled"] = False
    pipeline.apply_translation_settings(cfg)
    enabled, _, translator, _ = pipeline.translation_snapshot()
    assert enabled is False
    assert isinstance(translator, NullTranslator)


def test_apply_translation_settings_decode_only_keeps_translator() -> None:
    cfg = validate_config(
        {
            "translation_enabled": True,
            "translator_model": "nllb-200-distilled-ct2",
            "device": "cpu",
            "translation_decode_preset": "balanced",
        }
    )
    pipeline = AsrPipeline(cfg, queue.Queue())
    pipeline.apply_translation_settings(cfg)
    _, _, first, _ = pipeline.translation_snapshot()

    cfg["translation_decode_preset"] = "quality"
    pipeline.apply_translation_settings(cfg)
    _, _, second, decode = pipeline.translation_snapshot()
    assert second is first
    assert decode == TRANSLATION_FACTORY_PRESETS["quality"]
