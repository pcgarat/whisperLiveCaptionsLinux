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

## Instalación en el menú (Fase A)

Instala una copia en `~/.local` con icono en Actividades / menú de aplicaciones (sin `sudo`):

```bash
make install-user
```

- Lanzador: `~/.local/bin/whisper-live-captions`
- Menú: *Whisper Live Captions*
- Config: `~/.config/whisper-live-captions/config.json` (independiente del `config.json` del repo)

```bash
make uninstall-user                 # quita app/icono; conserva config
make uninstall-user PURGE_CONFIG=1  # también borra la config XDG
```

`make run` en el clon del repo sigue usando el `config.json` del directorio de trabajo (modo desarrollo).

La instalación **descarga los modelos de los presets de fábrica** para que el primer
arranque no se quede bajando pesos: Whisper `large-v3-turbo` (1,6 GB) y los tres
traductores Opus-MT. Estos últimos se bajan como ZIP de Marian (2,5 GB) y se convierten
a CT2 int8 en el sitio, lo que tarda ~90 s y deja solo 685 MB en disco.

```bash
make prefetch-models                       # descargar/convertir a mano
./scripts/prefetch-models.py --list        # ver qué bajaría, sin descargar
WLCL_SKIP_MODEL_PREFETCH=1 make install-user   # instalar sin descargar
```

Si falla la descarga (sin red, por ejemplo) la instalación **no se aborta**: avisa y la
app bajará cada modelo la primera vez que lo use. Volver a ejecutarlo con los modelos
ya presentes no descarga nada.

**Fase B (planificada):** paquete `.deb` system-wide (`/opt` + `/usr/share/applications`). Ver `docs/specs/packaging-install-desktop-2026-09-13.md`.

## Uso

1. Reproduce audio en inglés (navegador o reproductor).
2. En ⚙ elige el monitor de salida (`*.monitor`) y deja idioma `en`.
3. Elige modo de latencia: **stable** (~1–3 s, más estable) o **low** (~0.5–1 s, más parpadeo).
4. Ajusta confianza / latencia máxima si hace falta; **Restablecer modo** vuelve a los presets de fábrica.
5. Arrastra el overlay; ajusta tipografía/transparencia.
6. ✕ cierra y detiene captura + ASR.

Cambiar modo, profiles, modelo, dispositivo o idioma ASR **reinicia el pipeline**.
El toggle de traducción hace **hot-swap** del traductor (no recarga Whisper).

### Presets de vídeo por idioma (fase 2.9)

Para subtitular vídeo de internet hay un preset por idioma, todos con salida en español:

| Preset | Audio del vídeo | Traduce |
| --- | --- | --- |
| `video-en-es` | inglés | → español |
| `video-fr-es` | francés | → español |
| `video-de-es` | alemán | → español |
| `video-it-es` | italiano | → español |
| `video-pt-es` | portugués | → español |
| `video-es` | español | no (solo transcribe) |

Elige el del idioma del vídeo en Settings → **Preset general** y listo. Estos presets
solo fijan **idioma y modelos**: conservan tu posición del overlay, tipografía, modo de
latencia y dispositivo de audio, así que puedes cambiar de idioma sin recolocar nada.

Los modelos que usan (ver `docs/specs/fase2.9-presets-video-modelos-2026-09-13.md` para
las mediciones en RTX 4060):

- Reconocimiento: `large-v3-turbo` en `int8_float16` → 992 MB de VRAM, mismo acierto que
  `medium` con la mitad de memoria y menos latencia.
- Traducción: **Opus-MT tc-big** (CT2 int8), un modelo dedicado por idioma → ~300 MB de
  VRAM y 8 ms por frase. Elegido sobre NLLB-200 porque NLLB inventa texto en los
  fragmentos cortos (`sì` → «¿Qué?», `yeah` → «- ¿Qué?»), que son la mayoría de un
  subtítulo, y además puntúa por debajo en FLORES-200 en los cinco pares.
- Total ~1,3 GB de VRAM, que deja de sobra en una GPU de 8 GB con el navegador
  reproduciendo. Los tres traductores caben cargados a la vez.

Si quisieras un idioma sin modelo Opus-MT, en Settings → Traducciones → **Motor** tienes
NLLB-200 (200 idiomas). En General puedes cambiar **Precisión GPU**.

### Presets generales (fase 2.8)

En Settings, barra **Preset general** (encima de las pestañas):

- Vienen de fábrica `default` y los seis `video-*`. Ninguno se puede borrar; si
  sobrescribes uno con **Guardar**, tus valores se respetan.
- `default` es la config de referencia del producto y es un snapshot **completo**:
  aplicarlo restaura también apariencia y geometría.
- **Guardar como…** crea snapshots de *toda* la config (captura, latencia, traducción,
  apariencia, geometría).
- **Guardar** sobrescribe el preset activo con el estado actual.
- **Borrar** elimina el preset (con confirmación); no revierte la config viva.
- Cambiar el selector **aplica al instante** (reinicia ASR solo si hace falta).

> Si ya tenías un `config.json` de una versión anterior, tus ajustes no se tocan: los
> presets `video-*` aparecen añadidos, pero tu config sigue con el modelo que tuvieras
> hasta que elijas uno.
### Traducción EN→ES (fase 2.2 + 2.4)

- En el overlay: clic en el código de idioma (`EN`/`ES`/…) para cambiar entre `installed_languages`.
- En Settings → pestaña **Traducciones**: segunda línea, modo sticky (normal / solo confirmados / +parciales) y presets de calidad de decoding (`Rápido` / `Equilibrado` / `Calidad` / `Custom` + presets propios).
- Botón **ES** (toggle): activa/desactiva traducción. Persiste en `config.json`.
- Con traducción ON: línea 1 = español (solo texto ASR **confirmado**); línea 2 según **Segunda línea**: ASR en vivo, idioma original, o nada.
- Con idioma `es` o toggle OFF: no se traduce (passthrough).
- Cambiar preset/knobs de decoding y Guardar hace **hot-swap** (no reinicia Whisper).
- Motores disponibles (Settings → Traducciones → **Motor**):
  - `opus-mt-tc-big` (por defecto): un modelo Marian dedicado por idioma de origen.
    `tc-big-en-es` (234 MB), `tc-big-de-es` (236 MB) y `tc-big-itc-itc` (215 MB, cubre
    fr/it/pt con el token `>>spa<<`). ~300 MB de VRAM, 8 ms por frase, CC-BY-4.0.
  - `nllb-200-distilled-ct2` → `JustFrederik/nllb-200-distilled-600M-ct2-int8` (~647 MB).
  - `nllb-200-distilled-1.3b-ct2` → `OpenNMT/nllb-200-distilled-1.3B-ct2-int8` (~1,4 GB).
  - También acepta un repo CT2 propio escrito tal cual en `translator_model`.
  - Si CUDA falla al cargar, reintenta en CPU (en ambos motores).
  - Tokenizer: `sentencepiece` para Opus-MT, `tokenizers` para NLLB. **Sin
    `transformers` ni `torch`** en ninguno de los dos.
- Los Opus-MT no vienen de Hugging Face: se bajan como ZIP de Marian del Object Storage
  de CSC y se convierten a CT2 int8 con `OpusMTConverter` durante la instalación (~90 s).
  Quedan en `$XDG_DATA_HOME/whisper-live-captions/opus-mt` (override con
  `WLCL_MODELS_DIR`).
- Licencias: Opus-MT CC-BY-4.0; NLLB CC-BY-**NC**-4.0 (uso no comercial).

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

### Fase 2.9
- [ ] `video-en-es` con vídeo en inglés → subtítulos en español sin tocar nada más
- [ ] Cambiar a `video-fr-es` no mueve ni redimensiona el overlay
- [ ] `video-es` transcribe español sin cargar el traductor
- [ ] VRAM total < 8 GB con el navegador reproduciendo vídeo (`nvidia-smi`)
- [ ] Tras `make install-user`, el primer arranque no descarga modelos

## Arquitectura

Una sola app in-process (sin servidor WhisperLive). Specs en `docs/specs/`.

## Fuera de alcance actual

Auto-detect de idioma, cloud, diarización, TensorRT, calidad garantizada de pares distintos de EN→ES.
