from __future__ import annotations

import queue
import threading

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


def test_emit_committed_translates_delta_and_appends_flag() -> None:
    q: queue.Queue = queue.Queue()
    t = RecordingTranslator()
    cfg = validate_config(
        {
            "translation_enabled": True,
            "language": "en",
            "translation_target": "es",
            "device": "cpu",
        }
    )
    pipeline = AsrPipeline(cfg, q, translator=t)
    pipeline._emit_committed("Hello", language="en", now=1.0)
    pipeline.flush_translations()
    pipeline._emit_committed("Hello world", language="en", now=2.0)
    pipeline.flush_translations()

    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue.Empty:
            break

    # ASR + TX por cada commit (worker al día, sin coalesce)
    assert [i.seq for i in items] == [1, 1, 2, 2]
    assert items[0].translated_text is None
    assert items[1].translated_text == "ES:Hello"
    assert items[1].translation_append is False
    assert items[2].text == "Hello world"
    assert items[2].translated_text is None
    assert items[3].translated_text == "ES:world"
    assert items[3].translation_append is True
    assert t.calls[0][0] == "Hello"
    assert t.calls[1][0] == "world"
    pipeline.stop()


def test_emit_committed_shorten_still_emits_and_allows_growth() -> None:
    """Un acortamiento del streamer no debe bloquear commits posteriores."""
    q: queue.Queue = queue.Queue()
    t = RecordingTranslator()
    cfg = validate_config(
        {
            "translation_enabled": True,
            "language": "en",
            "translation_target": "es",
            "device": "cpu",
        }
    )
    pipeline = AsrPipeline(cfg, q, translator=t)
    pipeline._emit_committed("Hello world today", language="en", now=1.0)
    pipeline.flush_translations()
    while not q.empty():
        q.get_nowait()
    t.calls.clear()

    pipeline._emit_committed("Hello world", language="en", now=2.0)
    pipeline.flush_translations()
    pipeline._emit_committed("Hello world again", language="en", now=3.0)
    pipeline.flush_translations()

    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue.Empty:
            break

    asr = [i for i in items if i.translated_text is None]
    assert [i.text for i in asr] == ["Hello world", "Hello world again"]
    assert any(i.translated_text == "ES:Hello world" for i in items)
    assert any(i.translated_text == "ES:again" for i in items)
    pipeline.stop()


def test_tx_worker_coalesces_to_latest_span() -> None:
    """Con backlog: emite lo ya traducido y luego el delta hasta lo último."""
    q: queue.Queue = queue.Queue()
    gate = threading.Event()
    release = threading.Event()

    class BlockingTranslator(RecordingTranslator):
        def translate(
            self,
            text: str,
            source_lang: str,
            target_lang: str = "es",
            decode: dict[str, float | int] | None = None,
        ) -> str:
            gate.set()
            release.wait(timeout=2.0)
            return super().translate(text, source_lang, target_lang, decode)

    t = BlockingTranslator()
    cfg = validate_config(
        {
            "translation_enabled": True,
            "language": "en",
            "translation_target": "es",
            "device": "cpu",
        }
    )
    pipeline = AsrPipeline(cfg, q, translator=t)
    pipeline._emit_committed("Hello", language="en", now=1.0)
    assert gate.wait(timeout=2.0)

    pipeline._emit_committed("Hello world", language="en", now=2.0)
    pipeline._emit_committed("Hello world today", language="en", now=3.0)
    release.set()
    pipeline.flush_translations()

    tx_items = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if item.translated_text is not None:
            tx_items.append(item)

    assert len(tx_items) >= 2
    assert tx_items[0].translated_text == "ES:Hello"
    assert tx_items[0].translation_append is False
    assert tx_items[-1].seq == 3
    assert tx_items[-1].translated_text == "ES:world today"
    assert tx_items[-1].translation_append is True
    pipeline.stop()


def test_tx_worker_does_not_starve_under_continuous_newer() -> None:
    """Si siempre hay un commit más nuevo al acabar el decode, igual debe emitir."""
    q: queue.Queue = queue.Queue()
    started = threading.Event()
    release = threading.Event()
    translate_count = 0
    lock = threading.Lock()

    class BlockingTranslator(RecordingTranslator):
        def translate(
            self,
            text: str,
            source_lang: str,
            target_lang: str = "es",
            decode: dict[str, float | int] | None = None,
        ) -> str:
            nonlocal translate_count
            with lock:
                translate_count += 1
                n = translate_count
            if n == 1:
                started.set()
                release.wait(timeout=2.0)
            return super().translate(text, source_lang, target_lang, decode)

    t = BlockingTranslator()
    cfg = validate_config(
        {
            "translation_enabled": True,
            "language": "en",
            "translation_target": "es",
            "device": "cpu",
        }
    )
    pipeline = AsrPipeline(cfg, q, translator=t)
    pipeline._emit_committed("One", language="en", now=1.0)
    assert started.wait(timeout=2.0)
    pipeline._emit_committed("One two", language="en", now=2.0)
    pipeline._emit_committed("One two three", language="en", now=3.0)
    pipeline._emit_committed("One two three four", language="en", now=4.0)
    release.set()
    pipeline.flush_translations()

    tx_items = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        if item.translated_text is not None:
            tx_items.append(item)

    assert tx_items, "starvation: no llegó ninguna traducción"
    assert any("four" in (i.translated_text or "") or i.seq == 4 for i in tx_items)
    pipeline.stop()
