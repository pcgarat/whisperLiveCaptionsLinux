from __future__ import annotations

import shutil
import subprocess


def list_audio_monitors(pactl_bin: str | None = None) -> list[str]:
    """Lista fuentes Pulse/PipeWire; prioriza monitores de salida (`*.monitor`)."""
    binary = pactl_bin or shutil.which("pactl")
    if not binary:
        raise RuntimeError(
            "No se encontró `pactl`. Instala PulseAudio/PipeWire utils "
            "(paquete `pulseaudio-utils` o equivalente)."
        )

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

    return parse_pactl_sources_short(proc.stdout)


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
