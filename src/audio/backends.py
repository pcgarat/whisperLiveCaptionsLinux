from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.audio.capture import AudioRingBuffer


@dataclass(frozen=True)
class AudioSource:
    """Fuente de audio ofrecida por un backend.

    `id` es el identificador nativo (lo que se persiste en config); `label` es lo
    único que debería llegar a la UI.
    """

    id: str
    label: str
    backend: str
    is_loopback: bool


@runtime_checkable
class AudioStream(Protocol):
    """Captura en curso que alimenta un `AudioRingBuffer`."""

    buffer: AudioRingBuffer

    @property
    def running(self) -> bool: ...

    def start(self) -> None: ...

    def stop(self, timeout: float = 2.0) -> None: ...


@runtime_checkable
class AudioBackend(Protocol):
    """Origen del audio del sistema.

    Contrato de formato: `open_stream` escribe en el buffer float32 **mono** a
    `sample_rate`. Conseguirlo es cosa del backend (Pulse se lo delega a `parec`);
    no hay remuestreador compartido hasta que algún backend lo necesite.
    """

    name: str

    def is_available(self) -> bool: ...

    def list_sources(self) -> list[AudioSource]: ...

    def describe(self, source_id: str) -> AudioSource:
        """Describe un id guardado aunque ya no esté conectado."""
        ...

    def open_stream(
        self,
        source_id: str,
        *,
        buffer: AudioRingBuffer,
        sample_rate: int = 16000,
    ) -> AudioStream: ...
