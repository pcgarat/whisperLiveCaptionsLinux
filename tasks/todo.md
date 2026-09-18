# Tasks: Fase 2.9 — presets de vídeo por idioma y modelos preinstalados

Spec: `docs/specs/fase2.9-presets-video-modelos-2026-09-13.md`

## Task 1: Medición de modelos en la máquina objetivo

- [x] WER por idioma (en/fr/de/pt) con clips FLEURS: `small`, `medium`,
      `large-v3-turbo` (float16 e int8_float16), `large-v3`
- [x] VRAM y latencia por ventana (2 s / 5 s / 10 s) de cada combinación
- [x] NLLB 600M vs 1.3B: VRAM, latencia y calidad sobre frases reales
- [x] Descartar alternativas (distil-whisper, MADLAD, LLM) con razones
- [x] Re-medir `float16` vs `int8_float16` con repeticiones: se confirma `int8_float16`
- [x] Opus-MT tc-big vs NLLB-1.3B en fragmentos cortos → **cambia la decisión**
- [x] Barrido `beam_size` × `length_penalty` para fijar los perfiles de decode
- [x] Verify: tablas y conclusiones en el spec §2, §3 y §4bis

## Task 1b: Motor de traducción Opus-MT

- [x] `src/asr/opusmt.py`: registro por idioma, descarga del ZIP y conversión CT2
- [x] `MarianCt2Translator` con caché por modelo (fr/it/pt comparten `itc-itc`)
- [x] `sentencepiece` en `requirements.txt` (2,9 MB, sin `torch` ni `transformers`)
- [x] `translator_fingerprint()`: el idioma cuenta solo si el motor elige por idioma
- [x] Verify: `pytest -q tests/test_opusmt.py`

## Task 2: Catálogo de presets de fábrica

- [x] `src/presets.py` con overrides por idioma (no snapshots duplicados)
- [x] Snapshot parcial (`snapshot_app_config(keys=...)`)
- [x] `apply_app_preset` fusiona sobre la config actual
- [x] Siembra de los que falten en `validate_config`
- [x] Borrado rechazado para todos los de fábrica (config y UI)
- [x] Verify: `pytest -q tests/test_video_presets.py tests/test_app_presets.py`

## Task 3: Registro de traductores + UI

- [x] Catálogo `TRANSLATOR_MODEL_IDS` / `_LABELS` en `src/asr/translate.py`
- [x] Alias `nllb-200-distilled-1.3b-ct2`, case-insensitive, repo propio respetado
- [x] Motor `opus-mt-tc-big` por defecto; NLLB queda como salida multilingüe
- [x] Selector «Motor» en Settings → Traducciones
- [x] Verify: `pytest -q tests/test_settings_ui.py tests/test_translate.py`

## Task 4: Precarga de modelos en la instalación

- [x] `scripts/prefetch-models.py` (derivado del catálogo, `--list`, idempotente)
- [x] Descarga del ZIP de Marian + conversión a CT2 int8 en la instalación
- [x] `make prefetch-models`
- [x] `install-user.sh`: copia el script, lo invoca, no aborta si falla la red
- [x] `WLCL_SKIP_MODEL_PREFETCH` para saltarla
- [x] Verify: `--list`, segunda pasada sin descargas, `pytest -q tests/test_packaging_paths.py`

## Task 5: Config de fábrica y docs

- [x] `config.example.json` regenerado, sin `app_presets` duplicados
- [x] README: presets de vídeo, modelos, precarga y nota para configs existentes
- [x] Verify: `make check`

## Task 6: Smoke manual (acceptance)

- [ ] Arrancar, elegir `video-en-es`, reproducir vídeo en inglés → subtítulos en español
- [ ] Cambiar a `video-fr-es` con un vídeo francés sin recolocar el overlay
- [ ] `video-es` transcribe español sin cargar el traductor (VRAM ~1 GB)
- [ ] Comprobar VRAM total con navegador reproduciendo vídeo (< 8 GB)
- [ ] `make install-user` en `HOME` temporal → precarga sin descargas en el 1.er arranque

---

# Tasks: Fase 2.10 — tipografía del overlay

Spec: `docs/specs/fase2.10-tipografia-overlay-2026-09-18.md`

## Task 1: Config `font_family` + `font_weight`

- [x] `FONT_WEIGHT_MODES` / `FONT_WEIGHT_LABELS` y defaults en `src/config.py`
- [x] Normalización en `validate_config` (saneado para QSS, límite de longitud, enum de peso)
- [x] `config.example.json` con los dos knobs
- [x] Verify: `pytest -q tests/test_config.py`

## Task 2: Catálogo de fuentes

- [x] `src/ui/fonts.py`: `CAPTION_FONT_PRESETS`, `available_caption_fonts()`, helpers QSS
- [x] Filtrado: cobertura latina, sin privadas, sin bitmap, sin duplicados
- [x] Verify: `pytest -q tests/test_fonts.py`

## Task 3: UI Apariencia

- [x] Combos «Tipo de letra» (con muestra por ítem) y «Grosor»
- [x] Familia no instalada → ítem «(no instalada)» seleccionado
- [x] Vista previa, `reload_from_config()` y `result_config()`
- [x] Verify: `pytest -q tests/test_settings_ui.py`

## Task 4: Overlay

- [x] `_apply_style()` aplica familia a las tres líneas y peso a traducción + confirmado
- [x] Verify: `pytest -q tests/test_overlay_captions.py`

## Task 5: Docs

- [x] Tabla de config en `docs/developers-guide-*.md`
- [x] Verify: `make check`

## Task 6: Smoke manual (acceptance)

- [ ] Cambiar familia y peso, Guardar → el cartón cambia sin cortar audio ni recargar modelos
- [ ] Guardar un preset general con la tipografía elegida y volver a aplicarlo

---

# Tasks: Fase 2.11 — abstracción de backends de audio

Spec: `docs/specs/fase2.11-backends-audio-2026-09-18.md`

## Task 1: Contrato y registro

- [x] `src/audio/backends.py`: `AudioSource`, `AudioStream`, `AudioBackend`
- [x] `src/audio/devices.py`: registro, `resolve_backend`, `list_audio_sources`,
      `describe_audio_source`
- [x] Verify: `pytest -q tests/test_audio_devices.py`

## Task 2: Backend Pulse/PipeWire

- [x] `src/audio/pulse.py`: parseo de `pactl`, etiquetas legibles, `is_loopback`
- [x] `open_stream()` devuelve el `SystemAudioCapture` de siempre
- [x] Verify: `make devices` lista los monitores reales con etiqueta

## Task 3: Migrar puntos de uso

- [x] `src/asr/pipeline.py` usa `resolve_backend().open_stream(...)`
- [x] `src/app.py` y `src/ui/settings.py` usan `AudioSource` (`.id` / `.label`)
- [x] `_friendly_audio_label` y `list_audio_monitors` eliminados de la UI
- [x] Verify: `make check` + combo de audio con la config real

## Task 4: Smoke manual (acceptance)

- [ ] Arrancar, cambiar de dispositivo en Settings y transcribir con el nuevo
- [ ] Desconectar el dispositivo guardado y comprobar que sigue en la lista sin romper
