from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Catálogo de traductores. Dos motores con procedencias distintas:
#   - Opus-MT (Marian): ZIP de CSC convertido a CT2 en la instalación, un modelo
#     por idioma de origen. Ver `src/asr/opusmt.py`.
#   - NLLB-200 distilled: repo CT2 ya hecho en Hugging Face, un solo modelo
#     multilingüe. Tokenizer vía `tokenizers` (sin transformers).
NLLB_600M_CT2_MODEL_ID = "JustFrederik/nllb-200-distilled-600M-ct2-int8"
NLLB_1_3B_CT2_MODEL_ID = "OpenNMT/nllb-200-distilled-1.3B-ct2-int8"

TRANSLATOR_MODEL_OPUS_MT = "opus-mt-tc-big"
TRANSLATOR_MODEL_600M = "nllb-200-distilled-ct2"
TRANSLATOR_MODEL_1_3B = "nllb-200-distilled-1.3b-ct2"

# Opus-MT por defecto: medido en RTX 4060 gana a NLLB en las tres dimensiones que
# importan aquí (VRAM ~300 MB vs ~2 GB, 8 ms vs 49 ms por frase) y no alucina en
# fragmentos cortos. NLLB se mantiene para idiomas sin `tc-big` hacia español.
DEFAULT_TRANSLATOR_MODEL = TRANSLATOR_MODEL_OPUS_MT

NLLB_MODEL_IDS: dict[str, str] = {
    TRANSLATOR_MODEL_600M: NLLB_600M_CT2_MODEL_ID,
    TRANSLATOR_MODEL_1_3B: NLLB_1_3B_CT2_MODEL_ID,
}

# Orden de aparición en el selector de Settings.
TRANSLATOR_MODEL_IDS: dict[str, str] = {
    TRANSLATOR_MODEL_OPUS_MT: TRANSLATOR_MODEL_OPUS_MT,
    **NLLB_MODEL_IDS,
}
TRANSLATOR_MODEL_LABELS: dict[str, str] = {
    TRANSLATOR_MODEL_OPUS_MT: "Opus-MT tc-big — recomendado (~0,3 GB VRAM)",
    TRANSLATOR_MODEL_600M: "NLLB 600M — multilingüe (~1,1 GB VRAM)",
    TRANSLATOR_MODEL_1_3B: "NLLB 1.3B — multilingüe (~2,0 GB VRAM)",
}

# Compat: nombre previo del único modelo soportado.
NLLB_CT2_MODEL_ID = NLLB_600M_CT2_MODEL_ID

# Se aceptan también los repo IDs directos, para poder apuntar a una conversión propia.
TRANSLATOR_MODEL_ALIASES: dict[str, str] = {
    **TRANSLATOR_MODEL_IDS,
    **{repo: repo for repo in NLLB_MODEL_IDS.values()},
}


def is_opus_mt_model(model: str | None) -> bool:
    key = (model or DEFAULT_TRANSLATOR_MODEL).strip() or DEFAULT_TRANSLATOR_MODEL
    return key.lower() == TRANSLATOR_MODEL_OPUS_MT

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

    Ya no es el motor por defecto: alucina en fragmentos cortos de subtítulo. Se
    mantiene como salida para idiomas que no tengan un Opus-MT `tc-big` hacia
    español, donde sus 200 idiomas siguen siendo la única opción local.
    """

    _CPU_FALLBACK_NOTICE = (
        "Traducción en CPU (CUDA no disponible). Puede ir más lenta."
    )

    def __init__(
        self,
        model_id: str = NLLB_600M_CT2_MODEL_ID,
        device: str = "cuda",
        compute_type: str = "int8",
    ) -> None:
        self.model_id = resolve_translator_model_id(model_id)
        self.device = device
        self.compute_type = compute_type
        self.cpu_fallback = False
        self._cpu_fallback_notice_pending = False
        self._translator: Any = None
        self._tokenizer: Any = None
        self._model_path: Path | None = None

    @property
    def is_loaded(self) -> bool:
        return self._translator is not None and self._tokenizer is not None

    def take_cpu_fallback_notice(self) -> str | None:
        """Devuelve el aviso una sola vez si hubo fallback CUDA→CPU."""
        if not self._cpu_fallback_notice_pending:
            return None
        self._cpu_fallback_notice_pending = False
        return self._CPU_FALLBACK_NOTICE

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
                self.cpu_fallback = True
                self._cpu_fallback_notice_pending = True
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
    key = (model or DEFAULT_TRANSLATOR_MODEL).strip() or DEFAULT_TRANSLATOR_MODEL
    if key in TRANSLATOR_MODEL_ALIASES:
        return TRANSLATOR_MODEL_ALIASES[key]
    # Los alias van en minúsculas; los repo IDs conservan mayúsculas.
    return TRANSLATOR_MODEL_ALIASES.get(key.lower(), key)


def translator_fingerprint(config: dict[str, Any]) -> tuple[bool, str, str, str]:
    """Identidad del traductor: si cambia, hay que recrearlo.

    Opus-MT elige el modelo según el idioma de origen, así que ahí el idioma forma
    parte de la identidad; NLLB es un solo modelo multilingüe y recargarlo al
    cambiar de idioma serían 1,4 GB de trabajo inútil.
    """
    model = str(config.get("translator_model") or DEFAULT_TRANSLATOR_MODEL)
    language = str(config.get("language") or "en") if is_opus_mt_model(model) else ""
    return (
        bool(config.get("translation_enabled", False)),
        model,
        str(config.get("device") or "cuda"),
        language,
    )


def create_translator(config: dict[str, Any]) -> Translator:
    """Factory: Null si traducción OFF; si no, el motor que pida `translator_model`."""
    if not bool(config.get("translation_enabled", False)):
        return NullTranslator()
    model = str(config.get("translator_model") or DEFAULT_TRANSLATOR_MODEL)
    device = str(config.get("device") or "cuda")
    if is_opus_mt_model(model):
        from src.asr.opusmt import MarianCt2Translator

        return MarianCt2Translator(
            source_lang=str(config.get("language") or "en"),
            device=device,
            compute_type="int8_float16",
        )
    return NllbCt2Translator(model_id=model, device=device, compute_type="int8")
