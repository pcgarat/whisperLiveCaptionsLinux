from __future__ import annotations

from typing import Any

from src.asr.translate import (
    NLLB_CT2_MODEL_ID,
    NllbCt2Translator,
    NullTranslator,
    create_translator,
    resolve_translator_model_id,
)


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict[str, float | int] | None]] = []

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "es",
        decode: dict[str, float | int] | None = None,
    ) -> str:
        self.calls.append((text, source_lang, target_lang, decode))
        if source_lang == target_lang:
            return text
        return f"[{target_lang}]{text}"


def test_null_translator_passthrough() -> None:
    t = NullTranslator()
    assert t.translate("hello", "en", "es") == "hello"
    assert t.translate("hola", "es", "es") == "hola"


def test_resolve_model_alias() -> None:
    assert resolve_translator_model_id("nllb-200-distilled-ct2") == NLLB_CT2_MODEL_ID
    assert resolve_translator_model_id(NLLB_CT2_MODEL_ID) == NLLB_CT2_MODEL_ID


def test_factory_disabled_returns_null() -> None:
    t = create_translator({"translation_enabled": False, "device": "cuda"})
    assert isinstance(t, NullTranslator)


def test_factory_enabled_returns_nllb() -> None:
    t = create_translator(
        {
            "translation_enabled": True,
            "translator_model": "nllb-200-distilled-ct2",
            "device": "cpu",
        }
    )
    assert isinstance(t, NllbCt2Translator)
    assert t.model_id == NLLB_CT2_MODEL_ID
    assert not t.is_loaded


def test_nllb_passthrough_same_language_without_load() -> None:
    t = NllbCt2Translator(device="cpu")
    assert t.translate("hola mundo", "es", "es") == "hola mundo"
    assert not t.is_loaded


def test_nllb_translate_uses_injected_backend(monkeypatch: Any) -> None:
    t = NllbCt2Translator(device="cpu")

    class _Tok:
        def encode(self, text: str, add_special_tokens: bool = True) -> Any:
            class Enc:
                tokens = ["▁Hello", "▁world"]

            return Enc()

        def token_to_id(self, token: str) -> int | None:
            return {"▁Hola": 1, "▁mundo": 2}.get(token)

        def decode(self, ids: list[int]) -> str:
            rev = {1: "Hola", 2: "mundo"}
            return " ".join(rev[i] for i in ids)

    class _Result:
        hypotheses = [["spa_Latn", "▁Hola", "▁mundo"]]

    class _Ct2:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def translate_batch(
            self, sources: list[list[str]], **kwargs: Any
        ) -> list[_Result]:
            self.kwargs = kwargs
            assert sources[0][0] == "eng_Latn"
            assert sources[0][-1] == "</s>"
            assert kwargs["target_prefix"] == [["spa_Latn"]]
            return [_Result()]

    backend = _Ct2()
    t._tokenizer = _Tok()
    t._translator = backend
    decode = {"beam_size": 6, "length_penalty": 1.1, "no_repeat_ngram_size": 3}
    assert t.translate("Hello world", "en", "es", decode=decode) == "Hola mundo"
    assert t.is_loaded
    assert backend.kwargs is not None
    assert backend.kwargs["beam_size"] == 6
    assert abs(backend.kwargs["length_penalty"] - 1.1) < 1e-9
    assert backend.kwargs["no_repeat_ngram_size"] == 3


def test_nllb_translate_omits_ngram_when_zero() -> None:
    t = NllbCt2Translator(device="cpu")

    class _Tok:
        def encode(self, text: str, add_special_tokens: bool = True) -> Any:
            class Enc:
                tokens = ["▁Hi"]

            return Enc()

        def token_to_id(self, token: str) -> int | None:
            return 1

        def decode(self, ids: list[int]) -> str:
            return "Hola"

    class _Result:
        hypotheses = [["spa_Latn", "▁Hola"]]

    class _Ct2:
        def translate_batch(
            self, sources: list[list[str]], **kwargs: Any
        ) -> list[_Result]:
            assert "no_repeat_ngram_size" not in kwargs
            assert kwargs["beam_size"] == 2
            return [_Result()]

    t._tokenizer = _Tok()
    t._translator = _Ct2()
    assert (
        t.translate(
            "Hi",
            "en",
            "es",
            decode={"beam_size": 2, "length_penalty": 1.0, "no_repeat_ngram_size": 0},
        )
        == "Hola"
    )


def test_nllb_cuda_fallback_sets_notice(monkeypatch: Any) -> None:
    t = NllbCt2Translator(device="cuda")
    calls: list[str] = []

    class _Tok:
        @staticmethod
        def from_file(_path: str) -> Any:
            return object()

    class _Ct2Translator:
        def __init__(self, _path: str, device: str, compute_type: str) -> None:
            calls.append(device)
            if device == "cuda":
                raise RuntimeError("no cuda")

    monkeypatch.setattr(
        "huggingface_hub.snapshot_download", lambda **_kwargs: "/tmp/fake-nllb"
    )
    monkeypatch.setattr("tokenizers.Tokenizer", _Tok)
    monkeypatch.setattr("ctranslate2.Translator", _Ct2Translator)

    t.load()
    assert t.device == "cpu"
    assert t.cpu_fallback is True
    assert calls == ["cuda", "cpu"]
    notice = t.take_cpu_fallback_notice()
    assert notice is not None
    assert "CPU" in notice
    assert t.take_cpu_fallback_notice() is None


def test_fake_translator_contract() -> None:
    fake = FakeTranslator()
    assert fake.translate("hi", "en", "es") == "[es]hi"
    assert fake.translate("hola", "es", "es") == "hola"
    assert len(fake.calls) == 2
