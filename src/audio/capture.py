from __future__ import annotations

import subprocess
import threading
import time
from collections import deque

import numpy as np


class AudioRingBuffer:
    def __init__(self, max_seconds: float = 60.0, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.max_samples = int(max_seconds * sample_rate)
        self._lock = threading.Lock()
        self._buf = np.zeros(0, dtype=np.float32)

    def write(self, samples: np.ndarray) -> None:
        if samples.size == 0:
            return
        chunk = np.asarray(samples, dtype=np.float32).reshape(-1)
        with self._lock:
            self._buf = np.concatenate([self._buf, chunk])
            if self._buf.size > self.max_samples:
                self._buf = self._buf[-self.max_samples :]

    def read_all(self) -> np.ndarray:
        with self._lock:
            return self._buf.copy()

    def clear(self) -> None:
        with self._lock:
            self._buf = np.zeros(0, dtype=np.float32)

    def duration_seconds(self) -> float:
        with self._lock:
            return float(self._buf.size) / float(self.sample_rate)


class SystemAudioCapture:
    """Captura un monitor Pulse/PipeWire a 16 kHz mono float32 vía `parec`."""

    def __init__(
        self,
        source_name: str,
        sample_rate: int = 16000,
        buffer: AudioRingBuffer | None = None,
    ) -> None:
        self.source_name = source_name
        self.sample_rate = sample_rate
        self.buffer = buffer or AudioRingBuffer(sample_rate=sample_rate)
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        if not self.source_name:
            raise RuntimeError("No hay dispositivo de audio seleccionado.")

        self._stop.clear()
        self._proc = subprocess.Popen(
            [
                "parec",
                "--device",
                self.source_name,
                "--format=s16le",
                "--channels=1",
                f"--rate={self.sample_rate}",
                "--latency-msec=50",
                "--raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._thread = threading.Thread(
            target=self._read_loop, name="audio-capture", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=timeout)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._proc = None
        self._thread = None

    def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        bytes_per_chunk = int(self.sample_rate * 0.1) * 2  # 100 ms s16le mono
        stdout = self._proc.stdout
        while not self._stop.is_set():
            data = stdout.read(bytes_per_chunk)
            if not data:
                break
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            self.buffer.write(samples)


class ChunkPump:
    """Entrega vistas crecientes del buffer a intervalos mínimos."""

    def __init__(self, buffer: AudioRingBuffer, min_chunk_seconds: float = 0.8) -> None:
        self.buffer = buffer
        self.min_chunk_seconds = min_chunk_seconds
        self._last_emit = 0.0
        self._history: deque[float] = deque(maxlen=8)

    def poll(self) -> np.ndarray | None:
        now = time.monotonic()
        if now - self._last_emit < self.min_chunk_seconds:
            return None
        audio = self.buffer.read_all()
        if audio.size < int(self.buffer.sample_rate * self.min_chunk_seconds):
            return None
        self._last_emit = now
        self._history.append(now)
        return audio
