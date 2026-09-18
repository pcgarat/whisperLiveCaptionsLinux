"""Traductor Opus-MT (Marian) sobre CTranslate2.

Por qué Marian y no NLLB: en fragmentos cortos de subtítulo NLLB-200 alucina de
forma sistemática (`sì` → «¿Qué?», `espera` → «¿Qué quieres decir?»), que es el
régimen dominante al subtitular. Los `tc-big` de 2022 salen limpios, ocupan ~300
MB de VRAM en vez de ~2 GB y responden en 8 ms en vez de 49. Medidas y fuentes en
`docs/specs/fase2.9-presets-video-modelos-2026-09-13.md`.

Los modelos no vienen de Hugging Face: se descargan como ZIP de Marian del Object
Storage de CSC y se convierten a CT2 int8 con `ct2-opus-mt-converter`, que solo
necesita numpy y pyyaml (nada de torch ni transformers). La conversión ocurre en
la instalación; en tiempo de ejecución solo se carga lo ya convertido.
"""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

logger = logging.getLogger(__name__)

APP_ID = "whisper-live-captions"
ENV_MODELS_DIR = "WLCL_MODELS_DIR"

MARIAN_ZIP_BASE = "https://object.pouta.csc.fi/Tatoeba-MT-models"


@dataclass(frozen=True)
class OpusMtModel:
    """Un directorio CT2 y cómo obtenerlo."""

    name: str
    zip_path: str
    # Token de idioma destino que exigen los modelos multilingües (p. ej. itc-itc).
    # Los bilingües no lo llevan: metérselo degrada la salida.
    target_token: str | None = None

    @property
    def url(self) -> str:
        return f"{MARIAN_ZIP_BASE}/{self.zip_path}"


# Versiones `opusTCv20210807` a propósito: los `*-bible-big-*` de 2024 puntúan algo
# mejor en FLORES pero arrastran artefactos de subtítulos de diálogo («Thank you
# very much.» → «Muchas gracias por tu comentario.»).
EN_ES = OpusMtModel(
    name="tc-big-en-es",
    zip_path="eng-spa/opusTCv20210807+bt_transformer-big_2022-03-13.zip",
)
DE_ES = OpusMtModel(
    name="tc-big-de-es",
    zip_path="deu-spa/opusTCv20210807_transformer-big_2022-07-26.zip",
)
# No existe bilingüe tc-big para fr/it/pt→es; el modelo de familia itálica cubre
# los tres con un solo directorio y mejor calidad que los bilingües base de 2020.
ITC_ES = OpusMtModel(
    name="tc-big-itc-itc",
    zip_path="itc-itc/opusTCv20210807_transformer-big_2022-08-10.zip",
    target_token=">>spa<<",
)
# Eslavo oriental (be/rue/ru/uk→es): mejor BLEU en ruso (52,1) que el modelo
# eslavo general de abajo (50,6), y no hay bilingüe tc-big rus-spa.
ZLE_ES = OpusMtModel(
    name="tc-big-zle-es",
    zip_path="zle-spa/opusTCv20210807_transformer-big_2022-06-24.zip",
)
# No existe bilingüe tc-big ni familia eslava occidental (zlw) hacia español; el
# único tc-big que cubre checo y polaco es el eslavo general, que también sirve
# ruso pero con algo menos de BLEU que ZLE_ES.
SLA_ES = OpusMtModel(
    name="tc-big-sla-es",
    zip_path="sla-spa/opusTCv20210807_transformer-big_2022-09-15.zip",
)

# Registro declarativo: añadir un idioma es añadir una fila. fr/it/pt comparten
# directorio, así que la caché se indexa por nombre de modelo y no por idioma.
OPUS_MT_REGISTRY: dict[str, OpusMtModel] = {
    "en": EN_ES,
    "de": DE_ES,
    "fr": ITC_ES,
    "it": ITC_ES,
    "pt": ITC_ES,
    "ru": ZLE_ES,
    "cs": SLA_ES,
    "pl": SLA_ES,
}

REQUIRED_FILES = ("model.bin", "config.json", "source.spm", "target.spm")


def resolve_models_dir() -> Path:
    """Raíz de los modelos convertidos (`WLCL_MODELS_DIR` o XDG data)."""
    raw = str(os.environ.get(ENV_MODELS_DIR, "") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    xdg = str(os.environ.get("XDG_DATA_HOME", "") or "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / APP_ID / "opus-mt").resolve()


def model_dir(model: OpusMtModel) -> Path:
    return resolve_models_dir() / model.name


def is_model_ready(model: OpusMtModel) -> bool:
    target = model_dir(model)
    return all((target / name).exists() for name in REQUIRED_FILES)


def required_models(languages: list[str] | None = None) -> list[OpusMtModel]:
    """Modelos distintos que hacen falta para esos idiomas de origen."""
    codes = languages if languages is not None else list(OPUS_MT_REGISTRY)
    out: list[OpusMtModel] = []
    for code in codes:
        model = OPUS_MT_REGISTRY.get(str(code).strip().lower())
        if model is not None and model not in out:
            out.append(model)
    return out


def convert_model(model: OpusMtModel, *, quantization: str = "int8") -> Path:
    """Descarga el ZIP de Marian y lo convierte a CT2. Idempotente."""
    target = model_dir(model)
    if is_model_ready(model):
        return target

    from ctranslate2.converters import OpusMTConverter

    target.parent.mkdir(parents=True, exist_ok=True)
    work = target.parent / f".{model.name}.work"
    if work.exists():
        shutil.rmtree(work)
    raw = work / "marian"
    raw.mkdir(parents=True)

    archive = work / "model.zip"
    logger.info("Descargando %s", model.url)
    with urlopen(model.url) as response, archive.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(raw)
    archive.unlink()

    out = work / "ct2"
    logger.info("Convirtiendo %s a CT2 %s", model.name, quantization)
    OpusMTConverter(str(raw)).convert(str(out), quantization=quantization)
    # El conversor no copia los sentencepiece, y sin ellos el modelo es inservible.
    for spm in ("source.spm", "target.spm"):
        shutil.copyfile(raw / spm, out / spm)

    if target.exists():
        shutil.rmtree(target)
    out.rename(target)
    shutil.rmtree(work, ignore_errors=True)
    return target


class MarianCt2Translator:
    """Opus-MT en CT2, con un modelo por idioma de origen y carga diferida.

    Mantiene cargados los modelos que se hayan usado (a ~200-300 MB cada uno caben
    de sobra junto a Whisper), indexados por nombre de modelo para que los idiomas
    de una misma familia (fr/it/pt, cs/pl) compartan una sola copia cargada.
    """

    _CPU_FALLBACK_NOTICE = "Traducción en CPU (CUDA no disponible). Puede ir más lenta."

    def __init__(
        self,
        source_lang: str = "en",
        device: str = "cuda",
        compute_type: str = "int8_float16",
    ) -> None:
        self.source_lang = str(source_lang or "en").strip().lower()
        self.device = device
        self.compute_type = compute_type
        self.cpu_fallback = False
        self._cpu_fallback_notice_pending = False
        self._loaded: dict[str, tuple[Any, Any, Any]] = {}

    @property
    def is_loaded(self) -> bool:
        return bool(self._loaded)

    def take_cpu_fallback_notice(self) -> str | None:
        if not self._cpu_fallback_notice_pending:
            return None
        self._cpu_fallback_notice_pending = False
        return self._CPU_FALLBACK_NOTICE

    def load(self) -> None:
        """Precarga el modelo del idioma activo (lo llama el pipeline al arrancar)."""
        model = OPUS_MT_REGISTRY.get(self.source_lang)
        if model is not None:
            self._ensure(model)

    def _ensure(self, model: OpusMtModel) -> tuple[Any, Any, Any]:
        cached = self._loaded.get(model.name)
        if cached is not None:
            return cached

        import ctranslate2
        import sentencepiece as spm

        path = convert_model(model)
        logger.info("Cargando traductor Opus-MT %s (%s)", model.name, self.device)
        try:
            translator = ctranslate2.Translator(
                str(path), device=self.device, compute_type=self.compute_type
            )
        except Exception:
            if self.device == "cpu":
                raise
            logger.warning(
                "Fallo al cargar Opus-MT en %s; reintentando en CPU",
                self.device,
                exc_info=True,
            )
            self.device = "cpu"
            self.cpu_fallback = True
            self._cpu_fallback_notice_pending = True
            translator = ctranslate2.Translator(
                str(path), device="cpu", compute_type="int8"
            )

        source = spm.SentencePieceProcessor(model_file=str(path / "source.spm"))
        target = spm.SentencePieceProcessor(model_file=str(path / "target.spm"))
        entry = (translator, source, target)
        self._loaded[model.name] = entry
        return entry

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
        if tgt != "es":
            logger.warning("Opus-MT solo traduce a español; pedido %s→%s", src, tgt)
            return text

        model = OPUS_MT_REGISTRY.get(src)
        if model is None:
            logger.warning("Sin modelo Opus-MT para %s→es", src)
            return text

        translator, source, target = self._ensure(model)
        params = decode or {}
        tokens = source.encode(cleaned, out_type=str)
        if model.target_token:
            tokens = [model.target_token, *tokens]

        # El config.json del conversor lleva `add_source_eos`, así que CT2 añade
        # `</s>` solo; hacerlo aquí también empeora la traducción.
        kwargs: dict[str, Any] = {
            "beam_size": int(params.get("beam_size", 2)),
            "length_penalty": float(params.get("length_penalty", 0.4)),
            "max_decoding_length": int(params.get("max_decoding_length", 96)),
            "replace_unknowns": True,
        }
        ngram = int(params.get("no_repeat_ngram_size", 3))
        if ngram > 0:
            kwargs["no_repeat_ngram_size"] = ngram

        results = translator.translate_batch([tokens], **kwargs)
        hypotheses = results[0].hypotheses if results else []
        if not hypotheses:
            return text
        return target.decode(hypotheses[0]).strip()
