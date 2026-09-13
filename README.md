# Subtítulos en directo (Linux, local)

App de escritorio: captura el audio del sistema (PipeWire/Pulse), lo transcribe en local con `faster-whisper` y muestra un overlay flotante. Opcionalmente traduce a español con NLLB (CTranslate2), 100 % local.

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

Cambiar modo, profiles, modelo, dispositivo o idioma ASR **reinicia el pipeline**.
El toggle de traducción hace **hot-swap** del traductor (no recarga Whisper).

### Presets generales (fase 2.8)

En Settings, barra **Preset general** (encima de las pestañas):

- **Guardar como…** crea un snapshot de *toda* la config (captura, latencia, traducción, apariencia, geometría de overlay y Settings).
- **Guardar** sobrescribe el preset activo con el estado actual.
- **Borrar** elimina el preset (con confirmación); no revierte la config viva.
- Cambiar el selector **aplica al instante** (reinicia ASR solo si hace falta).
- Sin presets de fábrica: solo los que guardes tú.
### Traducción EN→ES (fase 2.2 + 2.4)

- En el overlay: clic en el código de idioma (`EN`/`ES`/…) para cambiar entre `installed_languages`.
- En Settings → pestaña **Traducciones**: segunda línea, modo sticky (normal / solo confirmados / +parciales) y presets de calidad de decoding (`Rápido` / `Equilibrado` / `Calidad` / `Custom` + presets propios).
- Botón **ES** (toggle): activa/desactiva traducción. Persiste en `config.json`.
- Con traducción ON: línea 1 = español (solo texto ASR **confirmado**); línea 2 según **Segunda línea**: ASR en vivo, idioma original, o nada.
- Con idioma `es` o toggle OFF: no se traduce (passthrough).
- Cambiar preset/knobs de decoding y Guardar hace **hot-swap** (no reinicia Whisper).
- Modelo: `JustFrederik/nllb-200-distilled-600M-ct2-int8` (alias config `nllb-200-distilled-ct2`).
  - Primera activación descarga ~600 MB a la caché de Hugging Face.
  - VRAM: Whisper medium + NLLB int8; si CUDA falla al cargar, reintenta en CPU.
  - Tokenizer con `tokenizers` (sin `transformers`).
- Licencia del modelo NLLB: CC-BY-NC-4.0 (uso no comercial).

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

### Fase 2.2
- [ ] Toggle ES y cambio de idioma persisten tras reiniciar la app
- [ ] EN + traducción ON: línea ES con confirmados; ASR según Settings
- [ ] Traducción OFF: una línea ASR como antes
- [ ] Idioma `es`: sin traducción real
- [ ] Smoke EN→ES ≥ 15 min sin cuelgue de UI

### Fase 2.3
- [ ] Settings → Instalar nuevos… añade idiomas al combo y, tras Guardar, al menú del overlay

## Arquitectura

Una sola app in-process (sin servidor WhisperLive). Specs en `docs/specs/`.

## Fuera de alcance actual

Auto-detect de idioma, cloud, diarización, TensorRT, calidad garantizada de pares distintos de EN→ES.
