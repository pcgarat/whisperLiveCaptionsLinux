Última modificación: 2026-09-13

# Spec: Subtítulos en directo Linux — Fase 1

**Estado:** aprobado (2026-09-13).  
**Intent:** `docs/intent/subtitulos-directo-2026-09-13.md`  
**Arquitectura acordada:** B — una sola app in-process (sin servidor WhisperLive).

## Objective

App de escritorio Linux, 100 % local, que muestra subtítulos en directo del audio del sistema en una ventana flotante. Proyecto **nuevo**: no se reutiliza el código de `live_translate_subtitles` (solo se toma como referencia visual del overlay).

**Usuario:** solo el autor, viendo vídeo/navegador.

**Fase 1 (este spec):**
- Transcripción en inglés con idioma elegido a mano (`en`).
- Sin traducción.
- Sin auto-detección de idioma.
- Texto estable con ~1–3 s de retraso por defecto.
- Debe aguantar un capítulo/vídeo entero sin cuelgues.

**Fuera de fase 1 (extensiones previstas, no implementar aún):**
- Multi-idioma + traducción a español.
- Modo baja-latencia configurable.
- Diarización, cloud, multi-usuario, extensiones de navegador, TensorRT.

## Tech Stack

| Pieza | Elección |
|-------|----------|
| Lenguaje | Python 3.12 |
| UI | PyQt6 (overlay frameless, always-on-top, translúcido) |
| ASR | `faster-whisper` (CTranslate2) en CUDA |
| Streaming | Política tipo LocalAgreement (provisional vs confirmado), inspirada en ufal/whisper_streaming — **código propio o módulo mínimo**, no dependencia del servidor Collabora |
| VAD | Silero VAD (opcional pero recomendado) vía torch/torchaudio o API de faster-whisper |
| Audio | PipeWire/Pulse (`*.monitor`), captura PCM 16 kHz mono **en memoria** |
| Config | JSON local (`config.json`) |
| Empaquetado fase 1 | venv + script de arranque (sin Docker) |

**Modelo por defecto:** `medium` en GPU (configurable: `small` / `medium` / `large-v3-turbo`).  
**Compute type:** `float16` en CUDA; fallback CPU solo documentado, no es objetivo de éxito.

## Commands

```bash
# Crear entorno e instalar
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# Arrancar app
./scripts/run.sh
# o: python -m src.app

# Tests
pytest -q

# Lint (cuando exista config)
ruff check src tests
```

Dependencias de sistema esperadas: `ffmpeg` (si hace falta para listar/resample), drivers NVIDIA + librerías CTranslate2/CUDA compatibles, PipeWire.

## Project Structure

```
whisperLiveCaptionsLinux/
├── docs/
│   ├── intent/                 # Intent confirmado
│   └── specs/                  # Este spec y siguientes
├── scripts/
│   └── run.sh                  # Activa venv y lanza la app
├── src/
│   ├── app.py                  # Entry point
│   ├── audio/
│   │   ├── devices.py          # Listar monitores Pulse/PipeWire
│   │   └── capture.py          # Captura continua → chunks en memoria
│   ├── asr/
│   │   ├── engine.py           # Wrapper faster-whisper
│   │   └── streaming.py        # Buffer + commit de texto estable
│   ├── ui/
│   │   ├── overlay.py          # Ventana de subtítulos
│   │   └── settings.py         # Diálogo de configuración
│   └── config.py               # Load/save config.json
├── tests/
│   ├── test_streaming.py
│   ├── test_config.py
│   └── test_audio_devices.py   # Mocks; sin GPU obligatoria
├── config.example.json
├── requirements.txt
└── README.md
```

## Code Style

- Módulos pequeños, una responsabilidad.
- Sin comentarios obvios; solo si la complejidad lo exige.
- Hilos: captura y ASR fuera del hilo UI; UI solo vía cola + `QTimer`/señales Qt.
- Nunca bloquear el event loop de Qt con inferencia.
- Config y rutas con pathlib; sin secretos en el repo.

Ejemplo de contrato entre ASR y UI:

```python
@dataclass(frozen=True)
class CaptionUpdate:
    text: str
    is_final: bool          # True = confirmado (estable)
    language: str           # Código elegido por el usuario
    ts_mono: float          # time.monotonic() al emitir
```

La UI muestra `is_final=False` de forma visualmente distinta (opcional en fase 1: mismo estilo) y reemplaza líneas al confirmar.

## Testing Strategy

| Nivel | Qué | Dónde |
|-------|-----|--------|
| Unit | Política de streaming (commit de prefijos), load/save config | `tests/test_streaming.py`, `tests/test_config.py` |
| Unit | Parsing/listado de dispositivos con salida `pactl` mockeada | `tests/test_audio_devices.py` |
| Manual | Capítulo EN ~20–40 min: sin cuelgue, subtítulos legibles, UI usable | Checklist en README / docs |
| No en CI fase 1 | Inferencia GPU end-to-end (requiere hardware) | Documentar pasos manuales |

Framework: `pytest`. Sin umbral de coverage rígido en fase 1; lo crítico es la política de streaming y que el hilo UI no haga ASR.

## Boundaries

**Always:**
- Mantener ASR/captura fuera del hilo UI.
- Audio en memoria (no WAV temporales por chunk como el proyecto viejo).
- Idioma solo el que elige el usuario.
- Actualizar este spec si cambia el alcance.
- Tests unitarios de streaming/config en verde antes de dar por cerrada una tarea de lógica.

**Ask first:**
- Añadir dependencias pesadas (torch full, transformers, Marian, Docker).
- Cambiar a arquitectura servidor (WhisperLive).
- Traducción o multi-idioma antes de cerrar fase 1.
- Cambiar toolkit UI (p. ej. GTK).

**Never:**
- Reutilizar el código de `live_translate_subtitles` (solo look & feel).
- Commitear tokens/secretos.
- Auto-detect de idioma en fase 1.
- Llamadas a APIs cloud para ASR/traducción.

## Success Criteria

Fase 1 se considera hecha cuando:

1. `./scripts/run.sh` arranca el overlay en Ubuntu 24.04 con GPU NVIDIA disponible.
2. El usuario elige monitor de audio y idioma `en` (sin auto-detect).
3. Con un vídeo en inglés en el navegador/reproductor, aparecen subtítulos en el overlay con latencia percibida típica **1–3 s**.
4. El texto **confirmado** no “parpadea” de forma inusable (la política de commit funciona).
5. Una sesión continua de **≥ 30 min** no cuelga la UI ni el proceso ASR (smoke manual).
6. Cerrar la ventana termina captura + ASR de forma limpia.
7. Preferencias visuales (fuente, colores, alpha, padding, posición) y dispositivo de audio se persisten en `config.json`.
8. `pytest -q` pasa en CI/local sin GPU.
9. No hay dependencia de WhisperLive server ni del repo viejo.

## Extensibilidad (no implementar en fase 1)

Diseñar interfaces, no features:

- `Translator` protocol vacío / stub para futuro ES.
- Flag de config reservado `latency_mode: stable | low` (solo `stable` activo).
- `language` en config ya como string libre (fase 1 valida/usa `en`).

## Open Questions

Resueltas al aprobar el spec (2026-09-13):

1. UI toolkit → **PyQt6**
2. Modelo default → **`medium`**
3. Texto en overlay → **parcial + confirmado** (parcial más discreto)

---

**Siguiente:** PLAN / TASKS en `tasks/plan.md` y `tasks/todo.md`.
