# Subtítulos en directo (Linux, local)

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
3. Elige modo de latencia: **stable** (~1–3 s, más estable) o **low** (~0.5–1 s, más parpadeo).
4. Ajusta confianza / latencia máxima si hace falta; **Restablecer modo** vuelve a los presets de fábrica.
5. Arrastra el overlay; ajusta tipografía/transparencia.
6. ✕ cierra y detiene captura + ASR.

Cambiar modo, profiles, modelo, dispositivo o idioma **reinicia el pipeline ASR** al Guardar.

## Tests

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
```

## Checklist manual

### Fase 1
- [ ] Arranca con `./scripts/run.sh` y GPU disponible
- [ ] Idioma `en` manual; subtítulos ~1–3 s con vídeo en inglés
- [ ] Texto confirmado usable (sin parpadeo extremo)
- [ ] Sesión ≥ 30 min sin cuelgue de UI/ASR
- [ ] Cerrar ventana termina limpio
- [ ] Preferencias persisten en `config.json`

### Fase 2.1
- [ ] Modo `low` se siente más inmediato que `stable`
- [ ] Overrides por modo sobreviven reinicio de la app
- [ ] Restablecer vuelve a fábrica del modo activo

## Arquitectura

Una sola app in-process (sin servidor WhisperLive). Specs en `docs/specs/`.

## Fuera de alcance actual

Traducción a español / multi-idioma (fase **2.2**), auto-detect, TensorRT.
