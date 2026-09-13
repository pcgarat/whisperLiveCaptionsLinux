from __future__ import annotations

import queue
import threading
import time
from typing import Any

from src.asr.engine import WhisperEngine
from src.asr.streaming import LocalAgreementStreamer
from src.asr.types import CaptionUpdate
from src.audio.capture import AudioRingBuffer, ChunkPump, SystemAudioCapture


class AsrPipeline:
    def __init__(
        self,
        config: dict[str, Any],
        out_queue: queue.Queue[CaptionUpdate],
    ) -> None:
        self.config = config
        self.out_queue = out_queue
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: SystemAudioCapture | None = None
        self._engine: WhisperEngine | None = None
        self._streamer = LocalAgreementStreamer(agreement_n=int(config.get("agreement_n", 2)))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        source = str(self.config.get("audio_monitor") or "")
        if not source:
            raise RuntimeError("Selecciona un dispositivo de audio (monitor) en configuración.")

        buffer = AudioRingBuffer(max_seconds=float(self.config.get("buffer_trimming_sec", 15.0)) + 5.0)
        self._capture = SystemAudioCapture(source_name=source, buffer=buffer)
        self._engine = WhisperEngine(
            model_size=str(self.config.get("model", "medium")),
            device=str(self.config.get("device", "cuda")),
            compute_type=str(self.config.get("compute_type", "float16")),
            language=str(self.config.get("language", "en")),
            use_vad=bool(self.config.get("use_vad", True)),
            beam_size=1 if self.config.get("latency_mode") == "low" else 5,
        )
        self._engine.load()
        self._capture.start()

        self._stop.clear()
        self._streamer.reset()
        self._thread = threading.Thread(target=self._loop, name="asr-pipeline", daemon=True)
        self._thread.start()

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
        pump = ChunkPump(
            self._capture.buffer,
            min_chunk_seconds=float(self.config.get("min_chunk_seconds", 0.8)),
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
                self.out_queue.put(
                    CaptionUpdate(
                        text=result.committed,
                        is_final=True,
                        language=language,
                        ts_mono=now,
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
