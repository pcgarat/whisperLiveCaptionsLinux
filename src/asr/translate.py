from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Alias de config → repo Hugging Face (CT2 int8, ~600M).
# Tokenizer vía `tokenizers` (sin transformers). Modelo: NLLB-200 distilled.
NLLB_CT2_MODEL_ID = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
TRANSLATOR_MODEL_ALIASES: dict[str, str] = {
    "nllb-200-distilled-ct2": NLLB_CT2_MODEL_ID,
    NLLB_CT2_MODEL_ID: NLLB_CT2_MODEL_ID,
}

# Códigos ISO → etiquetas NLLB-200. Claves alineadas con AVAILABLE_LANGUAGES.
NLLB_LANG_CODES: dict[str, str] = {
    "en": "eng_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
}


class Translator(Protocol):
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "es",
        decode: dict[str, float | int] | None = None,
    ) -> str: ...


class NullTranslator:
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "es",
        decode: dict[str, float | int] | None = None,
    ) -> str:
        return text


class NllbCt2Translator:
    """Traductor NLLB-200 distilled (CTranslate2 int8).

    Modelo por defecto: ``JustFrederik/nllb-200-distilled-600M-ct2-int8``
    (alias de config: ``nllb-200-distilled-ct2``). Lazy-load vía huggingface_hub.
    """

    def __init__(
        self,
        model_id: str = NLLB_CT2_MODEL_ID,
        device: str = "cuda",
        compute_type: str = "int8",
    ) -> None:
        self.model_id = resolve_translator_model_id(model_id)
        self.device = device
        self.compute_type = compute_type
        self._translator: Any = None
        self._tokenizer: Any = None
        self._model_path: Path | None = None

    @property
    def is_loaded(self) -> bool:
        return self._translator is not None and self._tokenizer is not None

    def load(self) -> None:
        if self.is_loaded:
            return
        import ctranslate2
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        logger.info("Cargando traductor NLLB CT2: %s (%s)", self.model_id, self.device)
        self._model_path = Path(snapshot_download(repo_id=self.model_id))
        self._tokenizer = Tokenizer.from_file(str(self._model_path / "tokenizer.json"))
        try:
            self._translator = ctranslate2.Translator(
                str(self._model_path),
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception:
            if self.device != "cpu":
                logger.warning(
                    "Fallo al cargar NLLB en %s; reintentando en CPU",
                    self.device,
                    exc_info=True,
                )
                self.device = "cpu"
                self._translator = ctranslate2.Translator(
                    str(self._model_path),
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str = "es",
        decode: dict[str, float | int] | None = None,
    ) -> str:
        cleaned = text.strip()
        if not cleaned:
            return text
        src = (source_lang or "").strip().lower()
        tgt = (target_lang or "es").strip().lower() or "es"
        if src == tgt:
            return text

        src_code = NLLB_LANG_CODES.get(src)
        tgt_code = NLLB_LANG_CODES.get(tgt)
        if src_code is None or tgt_code is None:
            logger.warning("Par de idiomas no soportado por NLLB map: %s→%s", src, tgt)
            return text

        self.load()
        assert self._translator is not None and self._tokenizer is not None

        params = decode or {}
        beam_size = int(params.get("beam_size", 4))
        length_penalty = float(params.get("length_penalty", 1.0))
        ngram = int(params.get("no_repeat_ngram_size", 3))

        source_tokens = self._encode(cleaned, src_code)
        batch_kwargs: dict[str, Any] = {
            "target_prefix": [[tgt_code]],
            "beam_size": beam_size,
            "length_penalty": length_penalty,
            "max_decoding_length": 256,
        }
        if ngram > 0:
            batch_kwargs["no_repeat_ngram_size"] = ngram

        results = self._translator.translate_batch([source_tokens], **batch_kwargs)
        hyp = results[0].hypotheses[0] if results and results[0].hypotheses else []
        return self._decode(hyp, tgt_code)

    def _encode(self, text: str, src_code: str) -> list[str]:
        enc = self._tokenizer.encode(text, add_special_tokens=False)
        return [src_code, *enc.tokens, "</s>"]

    def _decode(self, tokens: list[str], tgt_code: str) -> str:
        skip = {tgt_code, "</s>", "<s>", "<pad>", "<unk>"}
        ids: list[int] = []
        for tok in tokens:
            if tok in skip:
                continue
            tid = self._tokenizer.token_to_id(tok)
            if tid is not None:
                ids.append(tid)
        return self._tokenizer.decode(ids).strip()


def resolve_translator_model_id(model: str | None) -> str:
    key = (model or "nllb-200-distilled-ct2").strip() or "nllb-200-distilled-ct2"
    return TRANSLATOR_MODEL_ALIASES.get(key, key)


def create_translator(config: dict[str, Any]) -> Translator:
    """Factory: Null si traducción OFF; NLLB CT2 si ON."""
    if not bool(config.get("translation_enabled", False)):
        return NullTranslator()
    return NllbCt2Translator(
        model_id=str(config.get("translator_model") or "nllb-200-distilled-ct2"),
        device=str(config.get("device") or "cuda"),
        compute_type="int8",
    )
