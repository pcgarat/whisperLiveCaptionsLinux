Última modificación: 2026-09-13

# Flujo del traductor (ASR → NLLB)

Documento de referencia del pipeline in-process: captura → Whisper → LocalAgreement → overlay, y traducción async.

Código clave: `src/asr/pipeline.py`, `src/asr/engine.py`, `src/asr/streaming.py`, `src/asr/translate.py`, `src/config.py`.

---

## 1. Flujo principal

```mermaid
flowchart TD
    subgraph UI["Hilo UI (PyQt6)"]
        Overlay["Overlay<br/>CaptionUpdate queue"]
        Settings["Settings<br/>config.json"]
    end

    subgraph Audio["Captura"]
        Monitor["PipeWire/Pulse<br/>*.monitor"]
        Ring["AudioRingBuffer<br/>PCM 16 kHz mono"]
        Pump["ChunkPump<br/>min_chunk_seconds"]
    end

    subgraph ASR["Hilo asr-pipeline"]
        Whisper["WhisperEngine<br/>faster-whisper CUDA"]
        Streamer["LocalAgreementStreamer<br/>agreement_n + max_latency_sec"]
        EmitFinal["_emit_committed<br/>is_final=true + seq++"]
        EmitPartial["parcial<br/>is_final=false"]
    end

    subgraph TX["Hilo tx-worker"]
        Coalesce["Coalescing<br/>salta jobs obsoletos"]
        Plan["plan off | sticky checkpoints"]
        Gate{"translation_enabled<br/>y source ≠ target?"}
        NLLB["NllbCt2Translator<br/>translate_batch"]
        EmitTx["CaptionUpdate<br/>translated_text + seq"]
    end

    Settings -->|arranca / reinicia ASR| Whisper
    Settings -->|hot-swap decode/flags/sticky| Gate
    Monitor --> Ring --> Pump --> Whisper
    Whisper -->|hipótesis| Streamer
    Streamer -->|newly_committed| EmitFinal
    Streamer -->|partial| EmitPartial
    EmitFinal --> Overlay
    EmitPartial --> Overlay
    EmitFinal -->|si aplica| Coalesce --> Plan --> Gate
    EmitPartial -->|solo sticky=partials| Coalesce
    Gate -->|sí| NLLB --> EmitTx --> Overlay
    Gate -->|no / error| Overlay
```

### Reglas de diseño (importantes)

| Regla | Comportamiento |
| --- | --- |
| Default (`sticky=off`) | Solo confirmados; parciales no se traducen. |
| Sticky `committed` | Solo confirmados; reutiliza checkpoints (no re-traduce prefijos ya enviados a NLLB). |
| Sticky `partials` | Como committed + traduce el display de la hipótesis. |
| ASR no espera a NLLB | El texto origen se emite al instante; la ES llega después con `seq` vigente. |
| Passthrough | Si `language == translation_target` (p. ej. `es→es`), no se traduce. |
| Delta / sticky | Off: extensión → delta append. Sticky: ES completo con `append=false`. |
| Coalescing | Salta a lo último por `gen` monotónico (incluye parciales con mismo `seq`). |
| Fallo NLLB | Se loguea y se muestra solo ASR; no se tumba el overlay. |

---

## 2. Decisión: ¿se traduce este texto?

```mermaid
flowchart TD
    A[Confirmado o parcial si sticky=partials] --> B{translation_enabled?}
    B -->|no| Z[NullTranslator / no job]
    B -->|sí| C{source_lang == target_lang?}
    C -->|sí| Z
    C -->|no| D{texto vacío?}
    D -->|sí| Z
    D -->|no| E[Encolar _TxJob]
    E --> F[tx-worker]
    F --> G{¿hay job más nuevo pendiente?}
    G -->|sí| H[Saltar a lo último]
    H --> F
    G -->|no| I{sticky?}
    I -->|no| J[plan_off: delta o entero]
    I -->|sí| K[plan_sticky: checkpoint prefijo]
    J --> L[NLLB si hace falta]
    K --> L
    L --> M[Emitir translated_text]
```

Config: `translation_sticky_mode` = `off` | `committed` | `partials` (Settings → Traducciones).

---

## 3. Parámetros de transcripción (ASR)

Fuente: `WhisperEngine` + perfil de latencia (`effective_latency_profile`). Cambiar idioma/modelo/audio/latencia **reinicia** el pipeline.

### 3.1 Modelo y audio

| Parámetro | Config | Default | Qué hace |
| --- | --- | --- | --- |
| `language` | idioma fuente manual | `en` | Forzado en Whisper (`task=transcribe`). **Sin auto-detect.** |
| `model` | tamaño Whisper | `medium` | `small` / `medium` / `large-v3-turbo` / `large-v3` |
| `device` | backend | `cuda` | Dispositivo CTranslate2/faster-whisper |
| `compute_type` | cuantización ASR | `float16` | Precisión del motor Whisper |
| `audio_monitor` | fuente PipeWire/Pulse | `""` | Dispositivo `*.monitor` a capturar |
| `use_vad` | filtro VAD | `true` | `vad_filter` en `transcribe()` |
| `buffer_trimming_sec` | recorte ring buffer | `15.0` | Si el buffer crece de más, conserva cola ~8 s y resetea streamer |

Fijos en código (no expuestos en UI): `condition_on_previous_text=True`, `without_timestamps=True`, `task="transcribe"` (Whisper **no** usa `task=translate`; la traducción a ES es NLLB aparte).

### 3.2 Latencia / streaming (`latency_mode`)

El modo elige el perfil; los knobs editables viven en `latency_profiles[mode]`.

| Modo | `agreement_n` | `max_latency_sec` | `min_chunk_seconds` | `beam_size` Whisper |
| --- | ---: | ---: | ---: | ---: |
| `stable` | 2 | 3.0 | 0.8 | **5** |
| `low` | 1 | 1.0 | 0.35 | **1** |

| Parámetro | Rango | Efecto |
| --- | --- | --- |
| `agreement_n` (UI: Confianza) | 1–5 | Cuántas hipótesis consecutivas deben coincidir en un prefijo antes de confirmar. ↑ = más estable y lento. |
| `max_latency_sec` (UI: Techo) | 0.5–5.0 s | Si el parcial no se confirma a tiempo, se fuerza commit. ↓ = menos retraso, más riesgo prematuro. |
| `min_chunk_seconds` | fijo por modo | Intervalo mínimo entre polls de audio hacia Whisper. |
| `beam_size` (ASR) | derivado del modo | No es el beam de NLLB. `low→1`, `stable→5`. |

---

## 4. Parámetros de traducción (NLLB)

Motor: `NllbCt2Translator` (CTranslate2 int8). Alias por defecto: `nllb-200-distilled-ct2` → Hugging Face `JustFrederik/nllb-200-distilled-600M-ct2-int8`.

Hot-swap: cambiar enable/target/sticky/preset/profiles **no** reinicia ASR; solo recrea el `Translator` si cambian enable, modelo o device.

### 4.1 Flags y motor

| Parámetro | Default | Qué hace |
| --- | --- | --- |
| `translation_enabled` | `false` | OFF → `NullTranslator` (passthrough). ON → carga NLLB lazy/preload. |
| `translation_target` | `es` | Idioma destino ISO (`en`, `es`, `fr`, `de`, `it`, `pt`). |
| `translation_sticky_mode` | `off` | `off` / `committed` / `partials` (ver §1). |
| `translator_model` | `nllb-200-distilled-ct2` | Repo/alias del modelo CT2. |
| `device` | mismo que ASR | `cuda` con fallback a CPU int8 si falla la carga. |
| `compute_type` (NLLB) | `int8` fijo en factory | Independiente del `compute_type` de Whisper. |
| `second_line_mode` | `live_asr` | Solo UI: `live_asr` / `original` / `none`. |

### 4.2 Decoding (presets de calidad)

Valores efectivos vía `effective_translation_decode(config)` según `translation_decode_preset` + `translation_profiles`.

| Preset | `beam_size` | `length_penalty` | `no_repeat_ngram_size` | Uso típico |
| --- | ---: | ---: | ---: | --- |
| `fast` | 2 | 1.0 | 0 | Menos latencia / CPU |
| `balanced` | 4 | 1.0 | 3 | Default recomendado |
| `quality` | 6 | 1.1 | 3 | Mejor calidad, más lento |
| `custom` / usuario | editable | editable | editable | Perfil persistente o presets guardados |

Fijo en decode: `max_decoding_length=256`.

---

## 5. Contrato hacia el overlay

```text
CaptionUpdate
  text              → ASR (parcial o confirmado)
  is_final          → False = parcial; True = confirmado
  language          → idioma fuente configurado
  translated_text   → ES (u otro target) en updates de traducción (también parciales si sticky=partials)
  seq               → id monotónico por confirmación; traducciones viejas se descartan
  translation_append→ True si la ES es un delta a concatenar (modo off)
```

Con traducción ON: línea 1 = traducción; línea 2 según `second_line_mode`.

---

## 6. Mapa rápido config → componente

```mermaid
flowchart TB
    CFG["config.json"]

    CFG --> L["language, model, device,<br/>compute_type, use_vad,<br/>audio_monitor"]
    CFG --> LM["latency_mode + latency_profiles"]
    CFG --> TXF["translation_enabled,<br/>translation_target,<br/>translation_sticky_mode,<br/>translator_model"]
    CFG --> TXD["translation_decode_preset<br/>+ translation_profiles"]
    CFG --> UI2["second_line_mode"]

    L --> Engine["WhisperEngine"]
    LM --> Stream["LocalAgreement + ChunkPump"]
    LM --> Engine
    TXF --> Factory["create_translator()"]
    TXD --> Decode["decode kwargs NLLB"]
    Factory --> Worker["tx-worker"]
    Decode --> Worker
    UI2 --> Overlay["Overlay layout"]
```
