# Plan: Fase 2.9 — presets de vídeo por idioma y modelos preinstalados

Spec: `docs/specs/fase2.9-presets-video-modelos-2026-09-13.md`
Intent: `docs/intent/fase2.9-presets-video-modelos-2026-09-13.md`

## Enfoque

1. **Medir antes de elegir**: WER y latencia de los candidatos en la propia RTX 4060,
   no benchmarks de terceros con otra GPU.
2. **Catálogo en código** (`src/presets.py`), no seis snapshots duplicados en
   `config.example.json`.
3. **Siembra en la validación**: los presets de fábrica que falten se rellenan solos,
   así una config de una versión anterior gana los nuevos sin perder nada.
4. **Precarga derivada del catálogo**, para que no haya una lista de modelos paralela.

## Orden de slices

Investigación/medición → catálogo + siembra → registro de traductores + UI →
precarga e instalador → tests → docs.

## Crítica / mejoras conscientes

- **Presets parciales.** Un preset general era un snapshot de toda la config, así que
  cambiar de idioma movía el overlay de sitio. Se añade snapshot parcial y
  `apply_app_preset` pasa a fusionar sobre la config actual. Para snapshots completos el
  resultado no cambia, así que los presets de usuario existentes siguen igual.
- **`int8_float16` por defecto en Whisper.** Contraintuitivo (suena a recortar calidad)
  pero medido sale mejor en los tres ejes a la vez: mismo WER que `medium`, la mitad de
  VRAM y menos latencia. La cuantización paga porque el cuello es la memoria, no el
  cómputo.
- **`large-v3` descartado aunque sea «el mejor».** 3962 MB de VRAM no caben con el
  traductor cargado en una GPU de 8 GB que además mueve el escritorio.
- **Opus-MT rechazado primero y adoptado después: la primera conclusión estaba mal.**
  Se descartó por «no hay CT2 para X→es y convertir exige `transformers` + `torch`».
  Las dos premisas eran falsas: CTranslate2 trae `OpusMTConverter`, que convierte desde
  el ZIP de Marian con numpy y pyyaml, y `tc-big-itc-itc` cubre fr/it/pt con un solo
  modelo. Verificado convirtiendo los tres en 88 s sin `torch` en el venv.
- **El modelo grande no gana.** NLLB-1.3B parecía la elección de calidad, pero alucina
  en fragmentos cortos (`sì` → «¿Qué?»), que es el régimen dominante de un subtítulo.
  Opus-MT tc-big ocupa 1/7 de la VRAM, responde 6× más rápido, puntúa por encima en
  FLORES-200 en los cinco pares y tiene mejor licencia. La lección: medir en el
  **régimen real** (fragmentos cortos sin puntuación), no en frases de benchmark.
- **`translator_model` pasa de modelo a motor.** Con Opus-MT el modelo depende del
  idioma, así que la identidad del traductor se encapsula en `translator_fingerprint()`
  en vez de dejar que el pipeline recomponga la tupla con el alias hardcodeado.
- **Registro declarativo** (`OPUS_MT_REGISTRY`) en vez de `if/elif` por idioma: añadir
  un idioma es una fila. La caché se indexa por modelo, no por idioma, porque fr/it/pt
  comparten directorio.
- **`length_penalty` 0.7 en los tres perfiles de decode** (antes 1.0/1.0/1.1): medido,
  con 1.0 el decoder rellena los fragmentos cortos en los dos motores. Entra sin tocar
  el clamp ni el slider, así que no hay coste de UI.
- Alternativa rechazada: presets por idioma *y* por perfil de calidad (ligero/pesado).
  Serían 12 presets para un beneficio que ya cubre el selector de motor.
- Alternativa rechazada: publicar los CT2 ya convertidos en un repo HF propio (685 MB de
  descarga en vez de 2,5 GB). Ahorra ancho de banda al usuario pero añade un artefacto
  que mantener y una dependencia de un repo nuestro; convertir en la instalación es
  reproducible y no depende de nadie.
