from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

from src.asr.engine import WhisperEngine
from src.asr.streaming import LocalAgreementStreamer
from src.asr.translate import Translator, create_translator
from src.asr.types import CaptionUpdate
from src.audio.capture import AudioRingBuffer, ChunkPump, SystemAudioCapture
from src.config import (
    beam_size_for_mode,
    effective_latency_profile,
    effective_translation_decode,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TxJob:
    seq: int
    committed: str
    language: str


def translate_confirmed(
    text: str,
    *,
    source_lang: str,
    target_lang: str,
    translation_enabled: bool,
    translator: Translator,
    decode: dict[str, float | int] | None = None,
) -> str | None:
    """Traduce solo texto confirmado. Devuelve None si no aplica o falla."""
    if not translation_enabled:
        return None
    src = (source_lang or "").strip().lower()
    tgt = (target_lang or "es").strip().lower() or "es"
    if not text.strip() or src == tgt:
        return None
    try:
        out = translator.translate(text, src, tgt, decode=decode)
    except Exception:
        logger.exception("Error de traducción; se muestra solo ASR")
        return None
    return out if out is not None else None


class AsrPipeline:
    def __init__(
        self,
        config: dict[str, Any],
        out_queue: queue.Queue[CaptionUpdate],
        translator: Translator | None = None,
    ) -> None:
        self.config = config
        self.out_queue = out_queue
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: SystemAudioCapture | None = None
        self._engine: WhisperEngine | None = None
        self._tx_lock = threading.Lock()
        self._translator: Translator = (
            translator if translator is not None else create_translator(config)
        )
        self._tx_fingerprint = (
            bool(config.get("translation_enabled", False)),
            str(config.get("translator_model") or "nllb-200-distilled-ct2"),
            str(config.get("device") or "cuda"),
        )
        profile = effective_latency_profile(config)
        self._streamer = LocalAgreementStreamer(
            agreement_n=int(profile["agreement_n"]),
            max_latency_sec=float(profile["max_latency_sec"]),
        )
        self._caption_seq = 0
        self._last_committed = ""
        self._tx_stop = threading.Event()
        self._tx_thread: threading.Thread | None = None
        self._tx_pending_lock = threading.Lock()
        self._tx_pending_cv = threading.Condition(self._tx_pending_lock)
        self._tx_pending: _TxJob | None = None
        self._tx_busy = False
        self._last_tx_committed = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        source = str(self.config.get("audio_monitor") or "")
        if not source:
            raise RuntimeError(
                "Selecciona un dispositivo de audio (monitor) en configuración."
            )

        profile = effective_latency_profile(self.config)
        mode = str(self.config.get("latency_mode", "stable"))
        buffer = AudioRingBuffer(
            max_seconds=float(self.config.get("buffer_trimming_sec", 15.0)) + 5.0
        )
        self._capture = SystemAudioCapture(source_name=source, buffer=buffer)
        self._engine = WhisperEngine(
            model_size=str(self.config.get("model", "medium")),
            device=str(self.config.get("device", "cuda")),
            compute_type=str(self.config.get("compute_type", "float16")),
            language=str(self.config.get("language", "en")),
            use_vad=bool(self.config.get("use_vad", True)),
            beam_size=beam_size_for_mode(mode),
        )
        self._engine.load()
        self._preload_translator()
        self._capture.start()

        self._stop.clear()
        self._streamer = LocalAgreementStreamer(
            agreement_n=int(profile["agreement_n"]),
            max_latency_sec=float(profile["max_latency_sec"]),
        )
        self._caption_seq = 0
        self._last_committed = ""
        with self._tx_pending_lock:
            self._last_tx_committed = ""
            self._tx_pending = None
        self._ensure_tx_worker()
        self._thread = threading.Thread(
            target=self._loop, name="asr-pipeline", daemon=True
        )
        self._thread.start()

    def _preload_translator(self) -> None:
        with self._tx_lock:
            enabled = bool(self.config.get("translation_enabled", False))
            translator = self._translator
        if not enabled:
            return
        self._preload_translator_instance(translator)

    def _preload_translator_instance(self, translator: Translator) -> None:
        load = getattr(translator, "load", None)
        if not callable(load):
            return
        try:
            load()
        except Exception:
            logger.exception(
                "No se pudo precargar el traductor; se intentará en el primer final"
            )

    def apply_translation_settings(self, config: dict[str, Any]) -> None:
        """Hot-swap de flags/decode; recrea Translator solo si cambia motor/enable."""
        fingerprint = (
            bool(config.get("translation_enabled", False)),
            str(config.get("translator_model") or "nllb-200-distilled-ct2"),
            str(config.get("device") or "cuda"),
        )
        with self._tx_lock:
            for key in (
                "translation_enabled",
                "translation_target",
                "translator_model",
                "device",
                "language",
                "translation_decode_preset",
                "translation_profiles",
            ):
                if key in config:
                    self.config[key] = config[key]
            need_recreate = fingerprint != self._tx_fingerprint
            if need_recreate:
                self._translator = create_translator(self.config)
                self._tx_fingerprint = fingerprint
            translator = self._translator
            enabled = bool(self.config.get("translation_enabled", False))
        if need_recreate and enabled:
            threading.Thread(
                target=self._preload_translator_instance,
                args=(translator,),
                name="tx-preload",
                daemon=True,
            ).start()

    def translation_snapshot(
        self,
    ) -> tuple[bool, str, Translator, dict[str, float | int]]:
        with self._tx_lock:
            enabled = bool(self.config.get("translation_enabled", False))
            target = str(self.config.get("translation_target") or "es")
            decode = effective_translation_decode(self.config)
            return enabled, target, self._translator, decode

    def _ensure_tx_worker(self) -> None:
        if self._tx_thread is not None and self._tx_thread.is_alive():
            return
        self._tx_stop.clear()
        self._tx_thread = threading.Thread(
            target=self._tx_loop, name="tx-worker", daemon=True
        )
        self._tx_thread.start()

    def _stop_tx_worker(self, timeout: float = 3.0) -> None:
        self._tx_stop.set()
        with self._tx_pending_cv:
            self._tx_pending = None
            self._tx_pending_cv.notify_all()
        if self._tx_thread is not None:
            self._tx_thread.join(timeout=timeout)
        self._tx_thread = None

    def _schedule_translation(self, job: _TxJob) -> None:
        self._ensure_tx_worker()
        with self._tx_pending_cv:
            self._tx_pending = job
            self._tx_pending_cv.notify()

    def flush_translations(self, timeout: float = 2.0) -> None:
        """Espera a que el worker vacíe el pendiente (tests / apagado ordenado)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._tx_pending_lock:
                idle = self._tx_pending is None and not self._tx_busy
            if idle:
                return
            time.sleep(0.01)
        raise TimeoutError("timeout esperando traducciones pendientes")

    def _tx_loop(self) -> None:
        while not self._tx_stop.is_set():
            with self._tx_pending_cv:
                while self._tx_pending is None and not self._tx_stop.is_set():
                    self._tx_pending_cv.wait(timeout=0.2)
                if self._tx_stop.is_set():
                    return
                job = self._tx_pending
                self._tx_pending = None
                self._tx_busy = True

            assert job is not None
            try:
                self._process_tx_job(job)
            finally:
                with self._tx_pending_lock:
                    self._tx_busy = False
                    self._tx_pending_cv.notify_all()

    def _process_tx_job(self, job: _TxJob) -> None:
        while not self._tx_stop.is_set():
            with self._tx_pending_lock:
                newer = self._tx_pending
                if newer is not None and newer.seq > job.seq:
                    # Antes de traducir: saltar a lo último (ahorra decode obsoleto).
                    job = newer
                    self._tx_pending = None
                    continue
                base = self._last_tx_committed

            if base and job.committed.startswith(base) and job.committed != base:
                to_translate = job.committed[len(base) :].strip()
                append = True
            else:
                to_translate = job.committed
                append = False

            if not to_translate:
                with self._tx_pending_lock:
                    self._last_tx_committed = job.committed
                    newer = self._tx_pending
                    if newer is not None and newer.seq > job.seq:
                        job = newer
                        self._tx_pending = None
                        continue
                return

            translation_enabled, target_lang, translator, decode = (
                self.translation_snapshot()
            )
            translated = translate_confirmed(
                to_translate,
                source_lang=job.language,
                target_lang=target_lang,
                translation_enabled=translation_enabled,
                translator=translator,
                decode=decode,
            )

            # Importante: SIEMPRE emitir y avanzar la base aunque haya arrived
            # un job más nuevo durante el decode. Si descartamos el resultado,
            # con habla continua + NLLB lento el worker entra en starvation y
            # la línea ES nunca se actualiza (el ASR sí).
            payload: CaptionUpdate | None = None
            continue_with: _TxJob | None = None
            with self._tx_pending_lock:
                if translated is not None:
                    # Si el ASR ya avanzó pero este committed sigue siendo prefijo,
                    # etiquetar con el seq actual para que el overlay no la tire.
                    emit_seq = job.seq
                    if self._last_committed.startswith(job.committed):
                        emit_seq = max(emit_seq, self._caption_seq)
                    payload = CaptionUpdate(
                        text=job.committed,
                        is_final=True,
                        language=job.language,
                        ts_mono=time.monotonic(),
                        translated_text=translated,
                        seq=emit_seq,
                        translation_append=append,
                    )
                self._last_tx_committed = job.committed
                newer = self._tx_pending
                if newer is not None and newer.seq > job.seq:
                    continue_with = newer
                    self._tx_pending = None

            if payload is not None:
                self.out_queue.put(payload)

            if continue_with is not None:
                job = continue_with
                continue
            return

    def _emit_committed(self, committed: str, *, language: str, now: float) -> None:
        """Emite confirmado al instante; encola traducción async con coalescing.

        Nunca se traga el ASR: un acortamiento del streamer se trata como
        corrección in-place (replace), no como descarte. Descartar rewinds
        desincronizaba `_last_committed` del streamer y bloqueaba commits
        posteriores (síntoma: mucha habla sin salir al overlay).
        """
        prev = self._last_committed
        is_extension = bool(prev) and committed.startswith(prev) and committed != prev
        if is_extension:
            delta = committed[len(prev) :].strip()
            if not delta:
                self._last_committed = committed
                return

        self._caption_seq += 1
        seq = self._caption_seq
        self._last_committed = committed

        self.out_queue.put(
            CaptionUpdate(
                text=committed,
                is_final=True,
                language=language,
                ts_mono=now,
                seq=seq,
                translation_append=is_extension,
            )
        )

        translation_enabled, target_lang, _, _ = self.translation_snapshot()
        src = language.strip().lower()
        tgt = (target_lang or "es").strip().lower() or "es"
        if not translation_enabled or src == tgt or not committed.strip():
            return

        self._schedule_translation(
            _TxJob(seq=seq, committed=committed, language=language)
        )

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._capture is not None:
            self._capture.stop(timeout=timeout)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        self._capture = None
        self._stop_tx_worker(timeout=timeout)

    def _loop(self) -> None:
        assert self._capture is not None and self._engine is not None
        profile = effective_latency_profile(self.config)
        pump = ChunkPump(
            self._capture.buffer,
            min_chunk_seconds=float(profile["min_chunk_seconds"]),
        )
        language = str(self.config.get("language", "en"))
        trim_sec = float(self.config.get("buffer_trimming_sec", 15.0))

        while not self._stop.is_set():
            audio = pump.poll()
            if audio is None:
                time.sleep(0.05)
                continue

            try:
                hypothesis = self._engine.transcribe(audio)
            except Exception as exc:
                self.out_queue.put(
                    CaptionUpdate(
                        text=f"[ASR error] {exc}",
                        is_final=True,
                        language=language,
                        ts_mono=time.monotonic(),
                    )
                )
                time.sleep(0.5)
                continue

            if not hypothesis:
                continue

            result = self._streamer.push(hypothesis)
            now = time.monotonic()
            if result.newly_committed:
                self._emit_committed(result.committed, language=language, now=now)
            if result.partial:
                display = (result.committed + " " + result.partial).strip()
                self.out_queue.put(
                    CaptionUpdate(
                        text=display,
                        is_final=False,
                        language=language,
                        ts_mono=now,
                    )
                )

            if self._capture.buffer.duration_seconds() > trim_sec and result.committed:
                # Conserva cola del buffer para no crecer sin límite en sesiones largas.
                keep = self._capture.buffer.read_all()
                keep_samples = int(
                    self._capture.buffer.sample_rate * min(8.0, trim_sec / 2)
                )
                if keep.size > keep_samples:
                    self._capture.buffer.clear()
                    self._capture.buffer.write(keep[-keep_samples:])
                    self._streamer.reset()
                    self._last_committed = ""
                    with self._tx_pending_lock:
                        self._last_tx_committed = ""
                        self._tx_pending = None
