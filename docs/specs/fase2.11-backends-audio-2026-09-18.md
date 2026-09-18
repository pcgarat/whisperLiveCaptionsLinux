Última modificación: 2026-09-18

# Spec: Fase 2.11 — abstracción de backends de audio

**Estado:** aprobado (chat 2026-09-18).
**Intent:** `docs/intent/fase2.11-backends-audio-2026-09-18.md`

## Objective

Que el pipeline y la UI pidan «una fuente de audio» sin saber que detrás hay `pactl` y
`parec`, sin cambiar el comportamiento observable de la app.

## Contrato (`src/audio/backends.py`)

```python
@dataclass(frozen=True)
class AudioSource:
    id: str            # identificador nativo del backend
    label: str         # legible, para la UI
    backend: str       # nombre del backend que la sirve
    is_loopback: bool  # captura lo que suena, no un micrófono
```

- `AudioStream` (Protocol): `buffer`, `running`, `start()`, `stop(timeout)`.
- `AudioBackend` (Protocol): `name`, `is_available()`, `list_sources()`,
  `open_stream(source_id, *, buffer, sample_rate) -> AudioStream`.
- **Contrato de formato:** el stream escribe en el buffer float32 **mono** a `sample_rate`.
  Cómo se consigue es cosa del backend: Pulse se lo delega a `parec`. No hay remuestreador
  compartido hasta que exista un backend que lo necesite (ver intent, alcance acordado).

## Registro (`src/audio/devices.py`)

- `available_backends()` → los que devuelven `is_available()` verdadero.
- `resolve_backend(name=None)` → el pedido, o el primero disponible. Si no hay ninguno,
  `RuntimeError` con mensaje accionable (hoy: instalar `pulseaudio-utils`).
- `list_audio_sources()` → fuentes del backend activo.
- Sin clave de config nueva: con un solo backend, `audio_backend` sería especulativa. La
  clave `audio_monitor` sigue guardando el `id` de la fuente.

## Backend Pulse/PipeWire (`src/audio/pulse.py`)

- `list_sources()`: `pactl list sources short`, prioriza `*.monitor` (comportamiento
  actual) y marca `is_loopback` según ese sufijo.
- `label`: la traducción legible que hoy vive en `src/ui/settings.py`
  (`_friendly_audio_label`) se mueve aquí, porque formatea un identificador de Pulse y no
  tiene nada que hacer en la UI.
- `open_stream()`: devuelve el `SystemAudioCapture` de siempre (`parec`, s16le mono 16 kHz).

## Puntos de uso

- `src/asr/pipeline.py`: `resolve_backend().open_stream(...)`; el atributo pasa a tipar
  `AudioStream`.
- `src/app.py` y `src/ui/settings.py`: `list_audio_sources()`, usando `.label` para
  mostrar y `.id` para guardar.
- Se elimina `list_audio_monitors()`: es API interna con dos llamadas, no merece una capa
  de compatibilidad.

## Always / Ask / Never

- **Always:** comportamiento idéntico al actual (mismo dispositivo por defecto, mismas
  etiquetas, mismos mensajes de error).
- **Ask:** añadir backends (WASAPI, ALSA, JACK, macOS), clave `audio_backend`, remuestreo.
- **Never:** que el pipeline o la UI vuelvan a nombrar `parec`/`pactl`; añadir dependencias
  nativas nuevas en esta fase.

## Verification

- Unit: parseo de `pactl` y etiquetas (movidos), `resolve_backend` sin backends disponibles,
  `list_audio_sources` marcando `is_loopback`, y un backend falso que cumple el Protocol.
- Manual: arrancar, ver el mismo desplegable de dispositivos y transcribir.
