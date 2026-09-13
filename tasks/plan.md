# Implementation Plan: Fase 2.2 — Traducción EN→ES

## Overview

Traducción local EN→ES sobre texto ASR confirmado, con toggle + idioma clicable en el overlay, línea ASR opcional en Settings, y persistencia completa en `config.json`. Sin cloud ni auto-detect.

**Estado:** implementación completa (código + unit tests 2026-09-13). Pendiente smoke manual ≥15 min.  
**Spec:** `docs/specs/fase2.2-traduccion-en-es-2026-09-13.md`  
**Intent:** `docs/intent/fase2.2-traduccion-en-es-2026-09-13.md`

## Architecture Decisions

- **Protocol `Translator`:** `NullTranslator` + `NllbCt2Translator`; el pipeline solo conoce el protocol.
- **Solo `is_final`:** se traduce texto confirmado; parciales no pasan por NLLB.
- **`CaptionUpdate.translated_text`:** opcional; la UI actualiza línea ES solo cuando viene informado.
- **Lazy load:** cargar NLLB al activar traducción o al start si `translation_enabled` ya era true.
- **Persistencia:** `translation_enabled`, `language`, `installed_languages`, `show_asr_line`, `translation_target`, `translator_model` en config como el resto.
- **Reinicio ASR:** cambios de idioma / traducción / modelo de translator disparan reinicio de pipeline (mismo patrón que latencia).
- **Deps:** `ctranslate2` (ya vía faster-whisper) + tokenizer NLLB (`transformers` o sentencepiece documentado); pin y documentar tamaño/VRAM en README. Tests unitarios con Translator fake (sin GPU).

## Dependency Graph

```
config flags + CaptionUpdate.translated_text
    │
    ├── Translator protocol (Null + NLLB CT2 + factory)
    │       │
    │       └── AsrPipeline traduce solo finales
    │
    └── Overlay (lang menu, toggle ES, línea 1/2)
            │
            └── Settings show_asr_line + app restart keys + README
```

## Task List (vertical slices)

### Phase A: Contrato + motor
- Task 1: Config + `CaptionUpdate.translated_text` + tests
- Task 2: `Translator` factory (Null + NLLB CT2) + tests con fake/mocks

### Checkpoint A
- [x] `pytest` verde sin GPU de traducción
- [x] Passthrough `es` / toggle OFF cubierto

### Phase B: Pipeline + UI
- Task 3: Pipeline integra translator (lazy, solo finales)
- Task 4: Overlay + Settings + wiring persistencia/reinicio + README

### Checkpoint B — Fase 2.2 completa
- [ ] Smoke manual EN→ES ≥15 min
- [ ] Persistencia entre reinicios verificada
- [x] `pytest -q` verde

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VRAM Whisper medium + NLLB | High | CT2 int8; lazy load; documentar fallback CPU; Ask si hay que pasar a Marian EN→ES |
| 1ª activación lenta | Med | Mensaje/estado “cargando traducción…” opcional; no bloquear UI |
| Dep `transformers` pesada | Med | Solo tokenizer si es posible; pin versión; no Marian multi |
| Traducir demasiado tarde vs línea ASR | Low | Esperado (solo finales); `show_asr_line` para comparar |

## Open Questions

Ninguna bloqueante tras la aprobación del spec.

## Verification (antes de IMPLEMENT)

- [x] Cada task tiene acceptance + verify en `tasks/todo.md`
- [x] Orden por dependencias
- [x] Tasks acotadas
- [x] Checkpoints
- [x] Humano aprueba este plan (2026-09-13 — implementación aplazada a petición del usuario)
