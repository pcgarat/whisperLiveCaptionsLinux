---
name: run-and-debug-linux
description: Arranca, diagnostica y depura whisperLiveCaptionsLinux en Ubuntu/GNOME (PyQt6, PipeWire, CUDA). Usar al fallar make run, Qt, audio, always-on-top o faster-whisper.
---

# Run & debug (Linux)

## Arranque correcto

```bash
make run          # preferido
# o
./scripts/run.sh
```

Ambos deben: venv, deps, `PYTHONPATH`, libs PyQt6 en `LD_LIBRARY_PATH`, `QT_QPA_PLATFORM=xcb`.

## Checklist de fallos frecuentes

### ImportError Qt / `Qt_6_PRIVATE_API`

Cursor inyecta `/usr/lib` en `LD_LIBRARY_PATH`. Solución: prefijar `site-packages/PyQt6/Qt6/lib` **antes** del path del sistema (ya en Makefile/`run.sh`).

### Overlay no queda siempre encima

En GNOME Wayland puro el hint falla. Mantener **xcb**. Refuerzo opcional: `sudo apt install wmctrl`.

### No hay audio / silencio

```bash
make devices
```

Elegir un `*.monitor` (salida del sistema), no el micrófono. Bluetooth: el monitor del sink activo.

### CUDA / faster-whisper

- Mensaje debe citar drivers NVIDIA + compatibilidad `ctranslate2`.
- Smoke rápido: cargar `tiny` en `cuda`/`float16` antes de culpar al overlay.

### Cuelgues

Causa típica del proyecto viejo: ASR en hilo UI o I/O a disco por chunk. Verificar que captura+ASR siguen en worker y el cierre llama `pipeline.stop()`.

## Verificación

```bash
make test
make lint
```
