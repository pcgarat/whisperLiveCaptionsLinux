from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class LivePerfSnapshot:
    asr_infer_ms: float | None
    asr_audio_sec: float | None
    asr_rtf: float | None
    asr_busy: bool
    buffer_sec: float | None
    out_queue: int
    ts_mono: float


class LivePerfMetrics:
    """Métricas vivas compartidas pipeline ↔ overlay (sin I/O)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._infer_ms: float | None = None
        self._audio_sec: float | None = None
        self._rtf: float | None = None
        self._busy = False
        self._buffer_sec: float | None = None
        self._out_queue = 0
        self._ts_mono = 0.0

    def set_asr_busy(self, busy: bool) -> None:
        with self._lock:
            self._busy = bool(busy)
            self._ts_mono = time.monotonic()

    def note_asr_infer(
        self,
        *,
        infer_ms: float,
        audio_sec: float,
        buffer_sec: float | None = None,
    ) -> None:
        audio = max(0.0, float(audio_sec))
        infer = max(0.0, float(infer_ms))
        rtf = (infer / 1000.0) / audio if audio > 0 else None
        with self._lock:
            self._infer_ms = infer
            self._audio_sec = audio
            self._rtf = rtf
            self._busy = False
            if buffer_sec is not None:
                self._buffer_sec = max(0.0, float(buffer_sec))
            self._ts_mono = time.monotonic()

    def note_buffer_sec(self, buffer_sec: float) -> None:
        with self._lock:
            self._buffer_sec = max(0.0, float(buffer_sec))
            self._ts_mono = time.monotonic()

    def note_out_queue(self, depth: int) -> None:
        with self._lock:
            self._out_queue = max(0, int(depth))
            self._ts_mono = time.monotonic()

    def snapshot(self) -> LivePerfSnapshot:
        with self._lock:
            return LivePerfSnapshot(
                asr_infer_ms=self._infer_ms,
                asr_audio_sec=self._audio_sec,
                asr_rtf=self._rtf,
                asr_busy=self._busy,
                buffer_sec=self._buffer_sec,
                out_queue=self._out_queue,
                ts_mono=self._ts_mono,
            )


PERF = LivePerfMetrics()


def format_perf_chip(
    snap: LivePerfSnapshot,
    *,
    vram_used_mb: float | None = None,
    vram_total_mb: float | None = None,
) -> str:
    if snap.asr_busy:
        asr = "ASR …"
    elif snap.asr_infer_ms is None:
        asr = "ASR —"
    else:
        asr = f"ASR {snap.asr_infer_ms:.0f}ms"
        if snap.asr_rtf is not None:
            asr += f" rtf{snap.asr_rtf:.2f}"

    parts = [asr, f"q{snap.out_queue}"]
    if snap.buffer_sec is not None:
        parts.append(f"buf{snap.buffer_sec:.1f}s")

    if vram_used_mb is not None and vram_total_mb is not None and vram_total_mb > 0:
        parts.append(f"VRAM {vram_used_mb / 1024:.1f}/{vram_total_mb / 1024:.1f}G")
    elif vram_used_mb is not None:
        parts.append(f"VRAM {vram_used_mb / 1024:.1f}G")

    return " · ".join(parts)
