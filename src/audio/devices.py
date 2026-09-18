from __future__ import annotations

from src.audio.backends import AudioBackend, AudioSource
from src.audio.pulse import MISSING_PACTL, PulseBackend

# Orden de preferencia. Añadir un backend es añadir una fila (y, entonces sí,
# una clave `audio_backend` en config para poder forzarlo).
_REGISTRY: tuple[AudioBackend, ...] = (PulseBackend(),)


def registered_backends() -> tuple[AudioBackend, ...]:
    return _REGISTRY


def available_backends() -> list[AudioBackend]:
    return [backend for backend in _REGISTRY if backend.is_available()]


def resolve_backend(name: str | None = None) -> AudioBackend:
    """Backend pedido por nombre, o el primero disponible."""
    wanted = str(name or "").strip().lower()
    if wanted:
        for backend in _REGISTRY:
            if backend.name == wanted:
                return backend
        raise RuntimeError(f"Backend de audio desconocido: {wanted}")
    usable = available_backends()
    if not usable:
        raise RuntimeError(MISSING_PACTL)
    return usable[0]


def list_audio_sources(backend: AudioBackend | None = None) -> list[AudioSource]:
    return (backend or resolve_backend()).list_sources()


def describe_audio_source(
    source_id: str, backend: AudioBackend | None = None
) -> AudioSource:
    """Etiqueta un id persistido aunque su dispositivo ya no esté."""
    return (backend or resolve_backend()).describe(source_id)
