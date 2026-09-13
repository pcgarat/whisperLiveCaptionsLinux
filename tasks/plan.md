# Implementation Plan: Subtítulos en directo Linux — Fase 1

## Overview

App única in-process: captura PipeWire → streaming ASR con `faster-whisper` → overlay PyQt6. Sin WhisperLive server y sin código del proyecto viejo. Objetivo: subtítulos EN estables (~1–3 s), sesión ≥30 min sin cuelgues.

**Spec:** `docs/specs/fase1-subtitulos-directo-2026-09-13.md`  
**Intent:** `docs/intent/subtitulos-directo-2026-09-13.md`

## Architecture Decisions

- **In-process (B):** un proceso; hilos worker para audio/ASR; UI solo cola + señales Qt.
- **`faster-whisper` + política LocalAgreement propia:** texto provisional vs confirmado; evita reimplementar servidor Collabora.
- **Audio en memoria:** ring buffer / chunks float32 16 kHz; cero WAV temporales por chunk.
- **Contrato `CaptionUpdate`:** único puente ASR → UI (`text`, `is_final`, `language`, `ts_mono`).
- **Extensibilidad sin implementar:** stub `Translator`, `latency_mode: stable`, `language` string en config.
- **PyQt6 + modelo default `medium` + parcial discreto + confirmado.**

## Dependency Graph

```
config + CaptionUpdate types
    │
    ├── audio devices / capture
    │       │
    │       └── asr engine + streaming policy
    │               │
    │               └── pipeline worker (capture → ASR → queue)
    │                       │
    │                       └── overlay + settings UI
    │                               │
    │                               └── app entry + run.sh
```

## Task List (vertical slices)

### Phase A: Foundation
- [ ] Task 1: Skeleton del repo (estructura, requirements, config, run.sh)
- [ ] Task 2: Tipos `CaptionUpdate` + load/save config + tests
- [ ] Task 3: Política de streaming (unit-tested, sin GPU)

### Checkpoint: Foundation
- [ ] `pytest -q` verde
- [ ] Estructura y config listos
- [ ] Review humana opcional

### Phase B: Audio + ASR core
- [ ] Task 4: Listado de dispositivos Pulse/PipeWire (mockeable)
- [ ] Task 5: Captura continua a buffer en memoria
- [ ] Task 6: Motor `faster-whisper` + integración streaming

### Checkpoint: Core ASR
- [ ] Captura + transcripción EN en CLI/smoke (sin UI completa)
- [ ] Review humana recomendada (GPU/deps)

### Phase C: UI + producto
- [ ] Task 7: Overlay PyQt6 (parcial/confirmado, drag, always-on-top)
- [ ] Task 8: Diálogo settings + persistencia
- [ ] Task 9: App wiring (pipeline ↔ UI), cierre limpio, README checklist

### Checkpoint: Complete
- [ ] Success criteria del spec cumplidos (incl. smoke ≥30 min manual)
- [ ] Listo para review / uso diario fase 1

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CTranslate2/CUDA mismatch con driver 595 | High | Pin versions; documentar `ctranslate2` compatible; smoke temprano en Task 6 |
| Captura PipeWire frágil (Bluetooth monitor) | Med | Selector de dispositivo; fallback documentado; reutilizar nombres `*.monitor` |
| Política streaming mal afinada (parpadeo/latencia) | Med | Tests unitarios + defaults conservadores; `latency_mode` reservado |
| Bloqueo UI / cuelgues (fallo del proyecto viejo) | High | ASR nunca en hilo Qt; watchdog de cola; shutdown cooperativo |
| VRAM con `medium` + navegador | Low | Default `medium`; permitir `small` en config |

## Open Questions

Ninguna bloqueante tras la aprobación del spec. Si Task 6 falla por CUDA, se pregunta antes de añadir Docker o cambiar de backend.

## Verification (antes de IMPLEMENT)

- [ ] Cada task tiene acceptance + verify
- [ ] Orden por dependencias
- [ ] Ninguna task > ~5 archivos de forma rutinaria
- [ ] Checkpoints entre fases
- [ ] Humano aprueba este plan
