# Subtítulos en directo (Linux, local) — Fase 1

App de escritorio: captura el audio del sistema (PipeWire/Pulse), lo transcribe en local con `faster-whisper` y muestra un overlay flotante.

## Requisitos

- Ubuntu 24.04 (u similar)
- Python 3.12
- GPU NVIDIA + drivers
- `pactl` y `parec` (`pulseaudio-utils`)
- PipeWire/PulseAudio

## Arranque

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

La primera ejecución crea `.venv`, instala dependencias y puede descargar el modelo Whisper (`medium` por defecto).

## Uso

1. Reproduce audio en inglés (navegador o reproductor).
2. En ⚙ elige el monitor de salida (`*.monitor`) y deja idioma `en`.
3. Arrastra el overlay; ajusta tipografía/transparencia.
4. ✕ cierra y detiene captura + ASR.

## Tests

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
```

## Checklist manual (success criteria fase 1)

- [ ] Arranca con `./scripts/run.sh` y GPU disponible
- [ ] Idioma `en` manual; subtítulos ~1–3 s con vídeo en inglés
- [ ] Texto confirmado usable (sin parpadeo extremo)
- [ ] Sesión ≥ 30 min sin cuelgue de UI/ASR
- [ ] Cerrar ventana termina limpio
- [ ] Preferencias persisten en `config.json`

## Arquitectura

Una sola app in-process (sin servidor WhisperLive). Ver `docs/specs/fase1-subtitulos-directo-2026-09-13.md`.

## Fuera de fase 1

Traducción a español, multi-idioma real, modo baja-latencia activo, auto-detect, TensorRT.
