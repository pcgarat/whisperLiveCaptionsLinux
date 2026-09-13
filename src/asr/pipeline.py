from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

from src.asr.engine import WhisperEngine
from src.asr.streaming import LocalAgreementStreamer
from src.asr.translate import Translator, create_translator
from src.asr.types import CaptionUpdate
from src.audio.capture import AudioRingBuffer, ChunkPump, SystemAudioCapture
from src.config import beam_size_for_mode, effective_latency_profile

logger = logging.getLogger(__name__)


def translate_confirmed(
    text: str,
    *,
    source_lang: str,
    target_lang: str,
    translation_enabled: bool,
    translator: Translator,
) -> str | None:
    """Traduce solo texto confirmado. Devuelve None si no aplica o falla."""
    if not translation_enabled:
        return None
    src = (source_lang or "").strip().lower()
    tgt = (target_lang or "es").strip().lower() or "es"
    if not text.strip() or src == tgt:
        return None
    try:
        out = translator.translate(text, src, tgt)
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
        profile = effective_latency_profile(config)
        self._streamer = LocalAgreementStreamer(
            agreement_n=int(profile["agreement_n"]),
            max_latency_sec=float(profile["max_latency_sec"]),
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        source = str(self.config.get("audio_monitor") or "")
        if not source:
            raise RuntimeError("Selecciona un dispositivo de audio (monitor) en configuración.")

        profile = effective_latency_profile(self.config)
        mode = str(self.config.get("latency_mode", "stable"))
        buffer = AudioRingBuffer(max_seconds=float(self.config.get("buffer_trimming_sec", 15.0)) + 5.0)
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
        self._thread = threading.Thread(target=self._loop, name="asr-pipeline", daemon=True)
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
            logger.exception("No se pudo precargar el traductor; se intentará en el primer final")

    def apply_translation_settings(self, config: dict[str, Any]) -> None:
        """Hot-swap del Translator sin reiniciar captura/Whisper."""
        with self._tx_lock:
            for key in (
                "translation_enabled",
                "translation_target",
                "translator_model",
                "device",
                "language",
            ):
                if key in config:
                    self.config[key] = config[key]
            self._translator = create_translator(self.config)
            translator = self._translator
            enabled = bool(self.config.get("translation_enabled", False))
        if enabled:
            threading.Thread(
                target=self._preload_translator_instance,
                args=(translator,),
                name="tx-preload",
                daemon=True,
            ).start()

    def translation_snapshot(self) -> tuple[bool, str, Translator]:
        with self._tx_lock:
            enabled = bool(self.config.get("translation_enabled", False))
            target = str(self.config.get("translation_target") or "es")
            return enabled, target, self._translator

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._capture is not None:
            self._capture.stop(timeout=timeout)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        self._capture = None

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
                translation_enabled, target_lang, translator = self.translation_snapshot()
                translated = translate_confirmed(
                    result.committed,
                    source_lang=language,
                    target_lang=target_lang,
                    translation_enabled=translation_enabled,
                    translator=translator,
                )
                self.out_queue.put(
                    CaptionUpdate(
                        text=result.committed,
                        is_final=True,
                        language=language,
                        ts_mono=now,
                        translated_text=translated,
                    )
                )
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
                keep_samples = int(self._capture.buffer.sample_rate * min(8.0, trim_sec / 2))
                if keep.size > keep_samples:
                    self._capture.buffer.clear()
                    self._capture.buffer.write(keep[-keep_samples:])
                    self._streamer.reset()
