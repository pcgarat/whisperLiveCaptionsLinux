from __future__ import annotations

import shutil
import subprocess

from src.audio.backends import AudioSource, AudioStream
from src.audio.capture import AudioRingBuffer, SystemAudioCapture

BACKEND_NAME = "pulse"

MISSING_PACTL = (
    "No se encontró `pactl`. Instala PulseAudio/PipeWire utils "
    "(paquete `pulseaudio-utils` o equivalente)."
)


def parse_pactl_sources_short(output: str) -> list[str]:
    names: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        names.append(parts[1])

    monitors = [n for n in names if n.endswith(".monitor")]
    if monitors:
        return monitors
    return names


def friendly_pulse_label(device: str) -> str:
    """Etiqueta legible sin perder el id técnico, que va aparte en `AudioSource.id`."""
    name = device.strip()
    if not name:
        return "(sin dispositivo)"
    short = name
    if short.endswith(".monitor"):
        short = short[: -len(".monitor")]
    if short.startswith("bluez_output."):
        mac = short.removeprefix("bluez_output.").rsplit(".", 1)[0].replace("_", ":")
        return f"Bluetooth · {mac}"
    if short.startswith("alsa_output."):
        rest = short.removeprefix("alsa_output.")
        return f"Salida ALSA · {rest}"
    if "." in short:
        kind, rest = short.split(".", 1)
        return f"{kind} · {rest}"
    return short


class PulseBackend:
    """PipeWire o PulseAudio a través de `pactl` y `parec`."""

    name = BACKEND_NAME

    def __init__(self, pactl_bin: str | None = None) -> None:
        self._pactl_bin = pactl_bin

    def _resolve_pactl(self) -> str | None:
        return self._pactl_bin or shutil.which("pactl")

    def is_available(self) -> bool:
        return self._resolve_pactl() is not None

    def list_sources(self) -> list[AudioSource]:
        binary = self._resolve_pactl()
        if not binary:
            raise RuntimeError(MISSING_PACTL)
        try:
            proc = subprocess.run(
                [binary, "list", "sources", "short"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Falló `pactl list sources short`: {exc.stderr.strip()}"
            ) from exc
        return [
            self.describe(name) for name in parse_pactl_sources_short(proc.stdout)
        ]

    def describe(self, source_id: str) -> AudioSource:
        return AudioSource(
            id=source_id,
            label=friendly_pulse_label(source_id),
            backend=self.name,
            is_loopback=source_id.endswith(".monitor"),
        )

    def open_stream(
        self,
        source_id: str,
        *,
        buffer: AudioRingBuffer,
        sample_rate: int = 16000,
    ) -> AudioStream:
        return SystemAudioCapture(
            source_name=source_id, sample_rate=sample_rate, buffer=buffer
        )
