from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.asr.opusmt import (
    DE_ES,
    EN_ES,
    ITC_ES,
    OPUS_MT_REGISTRY,
    REQUIRED_FILES,
    SLA_ES,
    ZLE_ES,
    MarianCt2Translator,
    convert_model,
    is_model_ready,
    model_dir,
    required_models,
    resolve_models_dir,
)
from src.asr.translate import (
    TRANSLATOR_MODEL_1_3B,
    TRANSLATOR_MODEL_OPUS_MT,
    NllbCt2Translator,
    create_translator,
    is_opus_mt_model,
    translator_fingerprint,
)


class _Spm:
    """SentencePieceProcessor de mentira: parte por espacios."""

    def encode(self, text: str, out_type: type = str) -> list[str]:
        return [f"\u2581{w}" for w in text.split()]

    def decode(self, tokens: list[str]) -> str:
        return " ".join(t.lstrip("\u2581") for t in tokens)


class _Result:
    def __init__(self, hypotheses: list[list[str]]) -> None:
        self.hypotheses = hypotheses


class _Backend:
    def __init__(self, hypothesis: list[str] | None = None) -> None:
        self.sources: list[list[str]] | None = None
        self.kwargs: dict[str, Any] = {}
        self._hyp = hypothesis if hypothesis is not None else ["\u2581Hola", "\u2581mundo"]

    def translate_batch(self, sources: list[list[str]], **kwargs: Any) -> list[_Result]:
        self.sources = sources
        self.kwargs = kwargs
        return [_Result([self._hyp])]


def _wired(lang: str, backend: _Backend) -> MarianCt2Translator:
    t = MarianCt2Translator(source_lang=lang, device="cpu")
    model = OPUS_MT_REGISTRY[lang]
    t._loaded[model.name] = (backend, _Spm(), _Spm())
    return t


def test_registry_shares_one_model_for_romance_languages() -> None:
    assert OPUS_MT_REGISTRY["en"] is EN_ES
    assert OPUS_MT_REGISTRY["de"] is DE_ES
    # fr/it/pt salen del mismo directorio: no hay bilingüe tc-big hacia español.
    assert OPUS_MT_REGISTRY["fr"] is OPUS_MT_REGISTRY["it"] is OPUS_MT_REGISTRY["pt"]
    assert OPUS_MT_REGISTRY["fr"] is ITC_ES
    # Solo el multilingüe con varios destinos lleva token; metérselo a un
    # bilingüe (o a un modelo con destino único) degrada la traducción.
    assert ITC_ES.target_token == ">>spa<<"
    assert EN_ES.target_token is None and DE_ES.target_token is None
    assert "es" not in OPUS_MT_REGISTRY


def test_registry_shares_one_model_for_slavic_languages() -> None:
    assert OPUS_MT_REGISTRY["ru"] is ZLE_ES
    # cs/pl salen del mismo directorio: no hay bilingüe ni familia zlw tc-big.
    assert OPUS_MT_REGISTRY["cs"] is OPUS_MT_REGISTRY["pl"] is SLA_ES
    # zle-spa y sla-spa solo traducen a español (destino único): sin token.
    assert ZLE_ES.target_token is None and SLA_ES.target_token is None


def test_required_models_dedupes() -> None:
    assert required_models(["fr", "it", "pt"]) == [ITC_ES]
    assert required_models(["en", "fr", "de", "it", "pt"]) == [EN_ES, ITC_ES, DE_ES]
    assert required_models(["cs", "pl"]) == [SLA_ES]
    # Idiomas sin modelo (o vacíos) no rompen ni cuelan entradas.
    assert required_models(["es", "", "ja"]) == []
    assert required_models() == [EN_ES, DE_ES, ITC_ES, ZLE_ES, SLA_ES]


def test_models_dir_honours_env(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path / "modelos"))
    assert resolve_models_dir() == (tmp_path / "modelos").resolve()
    assert model_dir(EN_ES).name == EN_ES.name

    monkeypatch.delenv("WLCL_MODELS_DIR")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "datos"))
    assert resolve_models_dir() == (
        tmp_path / "datos" / "whisper-live-captions" / "opus-mt"
    ).resolve()


def test_model_ready_requires_sentencepiece_files(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """El conversor no copia los .spm; sin ellos el directorio es inservible."""
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    target = tmp_path / EN_ES.name
    target.mkdir()
    assert not is_model_ready(EN_ES)
    for name in REQUIRED_FILES:
        (target / name).write_text("x")
    assert is_model_ready(EN_ES)


def test_convert_is_noop_when_already_present(monkeypatch: Any, tmp_path: Path) -> None:
    """Idempotencia: reinstalar no vuelve a bajar 2,5 GB de ZIP."""
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    target = tmp_path / EN_ES.name
    target.mkdir()
    for name in REQUIRED_FILES:
        (target / name).write_text("x")

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("no debería descargar nada")

    monkeypatch.setattr("src.asr.opusmt.urlopen", _boom)
    assert convert_model(EN_ES) == target


def test_zip_urls_point_at_the_2022_models() -> None:
    """Los `*-bible-big-*` de 2024 arrastran artefactos de subtítulos: no usarlos."""
    for model in (EN_ES, DE_ES, ITC_ES, ZLE_ES, SLA_ES):
        assert model.url.startswith("https://object.pouta.csc.fi/Tatoeba-MT-models/")
        assert "opusTCv20210807" in model.url
        assert "bible" not in model.url


def test_factory_returns_marian_for_opus_mt_alias() -> None:
    t = create_translator(
        {
            "translation_enabled": True,
            "translator_model": TRANSLATOR_MODEL_OPUS_MT,
            "language": "fr",
            "device": "cpu",
        }
    )
    assert isinstance(t, MarianCt2Translator)
    assert t.source_lang == "fr"
    assert not t.is_loaded


def test_factory_still_returns_nllb_when_asked() -> None:
    t = create_translator(
        {
            "translation_enabled": True,
            "translator_model": TRANSLATOR_MODEL_1_3B,
            "language": "fr",
            "device": "cpu",
        }
    )
    assert isinstance(t, NllbCt2Translator)


def test_is_opus_mt_model_defaults_and_case() -> None:
    assert is_opus_mt_model(None) is True
    assert is_opus_mt_model("") is True
    assert is_opus_mt_model("Opus-MT-TC-Big") is True
    assert is_opus_mt_model(TRANSLATOR_MODEL_1_3B) is False


def test_fingerprint_includes_language_only_for_opus_mt() -> None:
    """Con Opus-MT el idioma elige el modelo; con NLLB recargar sería trabajo tonto."""
    base = {"translation_enabled": True, "device": "cuda"}
    opus_en = translator_fingerprint(
        {**base, "translator_model": TRANSLATOR_MODEL_OPUS_MT, "language": "en"}
    )
    opus_de = translator_fingerprint(
        {**base, "translator_model": TRANSLATOR_MODEL_OPUS_MT, "language": "de"}
    )
    assert opus_en != opus_de

    nllb_en = translator_fingerprint(
        {**base, "translator_model": TRANSLATOR_MODEL_1_3B, "language": "en"}
    )
    nllb_de = translator_fingerprint(
        {**base, "translator_model": TRANSLATOR_MODEL_1_3B, "language": "de"}
    )
    assert nllb_en == nllb_de


def test_passthrough_cases_do_not_touch_the_backend() -> None:
    backend = _Backend()
    t = _wired("en", backend)
    assert t.translate("hola", "es", "es") == "hola"
    assert t.translate("   ", "en", "es") == "   "
    # Opus-MT solo va hacia español; otro destino se deja tal cual.
    assert t.translate("hello", "en", "fr") == "hello"
    # Idioma sin modelo en el registro.
    assert t.translate("konnichiwa", "ja", "es") == "konnichiwa"
    assert backend.sources is None


def test_bilingual_model_gets_no_target_token() -> None:
    backend = _Backend()
    t = _wired("en", backend)
    assert t.translate("Hello world", "en", "es") == "Hola mundo"
    assert backend.sources == [["\u2581Hello", "\u2581world"]]
    # `add_source_eos` del config.json ya añade `</s>`; duplicarlo empeora la salida.
    assert "</s>" not in backend.sources[0]


def test_multilingual_model_gets_target_token() -> None:
    backend = _Backend()
    t = _wired("it", backend)
    t.translate("non lo so", "it", "es")
    assert backend.sources is not None
    assert backend.sources[0][0] == ">>spa<<"


def test_slavic_family_model_gets_no_target_token() -> None:
    """zle-es/sla-es solo traducen a español: destino único, sin token."""
    backend = _Backend()
    t = _wired("pl", backend)
    t.translate("nie wiem", "pl", "es")
    assert backend.sources is not None
    assert backend.sources[0][0] != ">>spa<<"


def test_decode_params_and_subtitle_defaults() -> None:
    backend = _Backend()
    t = _wired("en", backend)
    t.translate(
        "hi",
        "en",
        "es",
        decode={"beam_size": 4, "length_penalty": 0.7, "no_repeat_ngram_size": 3},
    )
    assert backend.kwargs["beam_size"] == 4
    assert abs(float(backend.kwargs["length_penalty"]) - 0.7) < 1e-9
    assert backend.kwargs["no_repeat_ngram_size"] == 3
    # Techo duro: una alucinación no debe consumir cientos de milisegundos.
    assert backend.kwargs["max_decoding_length"] == 96
    assert backend.kwargs["replace_unknowns"] is True

    # Sin decode explícito manda el ajuste medido para subtítulos.
    t.translate("hi", "en", "es")
    assert backend.kwargs["beam_size"] == 2
    assert abs(float(backend.kwargs["length_penalty"]) - 0.4) < 1e-9


def test_ngram_zero_is_omitted() -> None:
    backend = _Backend()
    t = _wired("en", backend)
    t.translate("hi", "en", "es", decode={"no_repeat_ngram_size": 0})
    assert "no_repeat_ngram_size" not in backend.kwargs


def test_empty_hypotheses_returns_source() -> None:
    t = _wired("en", _Backend(hypothesis=[]))
    assert t.translate("hello", "en", "es") == ""


def test_shared_model_is_loaded_once(monkeypatch: Any, tmp_path: Path) -> None:
    """fr/it/pt comparten directorio: la caché va por modelo, no por idioma."""
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    loads: list[str] = []

    class _Ct2Translator:
        def __init__(self, path: str, device: str, compute_type: str) -> None:
            loads.append(path)

    monkeypatch.setattr("src.asr.opusmt.convert_model", lambda m: model_dir(m))
    monkeypatch.setattr("ctranslate2.Translator", _Ct2Translator)
    monkeypatch.setattr(
        "sentencepiece.SentencePieceProcessor", lambda model_file: _Spm()
    )

    t = MarianCt2Translator(source_lang="fr", device="cpu")
    t._ensure(OPUS_MT_REGISTRY["fr"])
    t._ensure(OPUS_MT_REGISTRY["it"])
    t._ensure(OPUS_MT_REGISTRY["pt"])
    assert len(loads) == 1
    assert len(t._loaded) == 1


def test_slavic_shared_model_is_loaded_once(monkeypatch: Any, tmp_path: Path) -> None:
    """cs/pl comparten `tc-big-sla-es`: la caché va por modelo, no por idioma."""
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    loads: list[str] = []

    class _Ct2Translator:
        def __init__(self, path: str, device: str, compute_type: str) -> None:
            loads.append(path)

    monkeypatch.setattr("src.asr.opusmt.convert_model", lambda m: model_dir(m))
    monkeypatch.setattr("ctranslate2.Translator", _Ct2Translator)
    monkeypatch.setattr(
        "sentencepiece.SentencePieceProcessor", lambda model_file: _Spm()
    )

    t = MarianCt2Translator(source_lang="cs", device="cpu")
    t._ensure(OPUS_MT_REGISTRY["cs"])
    t._ensure(OPUS_MT_REGISTRY["pl"])
    assert len(loads) == 1
    assert len(t._loaded) == 1


def test_cuda_fallback_sets_notice(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    devices: list[str] = []

    class _Ct2Translator:
        def __init__(self, path: str, device: str, compute_type: str) -> None:
            devices.append(device)
            if device == "cuda":
                raise RuntimeError("no cuda")

    monkeypatch.setattr("src.asr.opusmt.convert_model", lambda m: model_dir(m))
    monkeypatch.setattr("ctranslate2.Translator", _Ct2Translator)
    monkeypatch.setattr(
        "sentencepiece.SentencePieceProcessor", lambda model_file: _Spm()
    )

    t = MarianCt2Translator(source_lang="en", device="cuda")
    t.load()
    assert devices == ["cuda", "cpu"]
    assert t.device == "cpu" and t.cpu_fallback is True
    notice = t.take_cpu_fallback_notice()
    assert notice is not None and "CPU" in notice
    assert t.take_cpu_fallback_notice() is None


def test_load_without_model_for_language_is_quiet(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Español no tiene modelo Opus-MT y no debe reventar al precargar."""
    monkeypatch.setenv("WLCL_MODELS_DIR", str(tmp_path))
    t = MarianCt2Translator(source_lang="es", device="cpu")
    t.load()
    assert not t.is_loaded


@pytest.mark.parametrize("lang", sorted(OPUS_MT_REGISTRY))
def test_every_registered_language_has_a_zip(lang: str) -> None:
    model = OPUS_MT_REGISTRY[lang]
    assert model.zip_path.endswith(".zip")
    assert model.name.startswith("tc-big-")
