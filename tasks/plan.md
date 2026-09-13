# Implementation Plan: Fase 2.1 — Modo baja latencia

## Overview

Activar `latency_mode` de verdad (`stable` | `low`) con profiles por modo (`agreement_n`, `max_latency_sec`, `min_chunk_seconds`), force-commit por techo de latencia, UI de settings (selector, sliders + tooltips, Restablecer) y migración de configs fase 1. Sin traducción (2.2).

**Spec:** `docs/specs/fase2.1-baja-latencia-2026-09-13.md`  
**Intent:** `docs/intent/fase2.1-baja-latencia-2026-09-13.md`

## Architecture Decisions

- **Profiles por modo:** `latency_profiles.{stable|low}` es la fuente de verdad; el pipeline lee el profile efectivo del `latency_mode` activo.
- **Factory presets inmutables en código** (`LATENCY_FACTORY_PRESETS`) para Restablecer y defaults.
- **Migración suave:** configs fase 1 sin `latency_profiles` se rellenan; knobs top-level legacy alimentan el modo activo.
- **Force-commit por tiempo** en el streamer/pipeline: red de seguridad además de LocalAgreement.
- **`min_chunk` solo vía profile** (opción A): se quita el spinbox global de chunk para no duplicar fuentes.
- **`beam_size`:** 5 en `stable`, 1 en `low`.
- **Aplicar cambios:** guardar config + reiniciar pipeline (patrón actual de la app).

## Dependency Graph

```
LATENCY_FACTORY_PRESETS + validate/migrate config
    │
    ├── effective profile helpers
    │
    ├── LocalAgreementStreamer + max_latency force-commit
    │       │
    │       └── AsrPipeline (profile knobs + beam_size)
    │
    └── SettingsDialog (modo, sliders, tooltips, Restablecer)
            │
            └── app wiring + config.example + nota README
```

## Task List (vertical slices)

### Phase A: Config + streamer
- Task 1: Profiles, migración, validación, `config.example.json`
- Task 2: Force-commit por `max_latency_sec` + `agreement_n` dinámico (tests)

### Checkpoint A
- `pytest` config + streaming verde
- Config fase 1 migra sin romper arranque

### Phase B: Pipeline + UI
- Task 3: Pipeline usa profile efectivo + `beam_size` formalizado
- Task 4: Settings (modo, sliders, tooltips, Restablecer) + wiring app

### Checkpoint B — Fase 2.1 completa
- Success criteria del spec (manual `stable` vs `low`)
- `pytest -q` verde

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Force-commit prematuro ilegible | Med | Defaults conservadores en `stable`; tests de techo; tooltip claro |
| Drift config legacy vs profiles | Med | Una sola fuente (`latency_profiles`); migración en `validate_config` |
| `min_chunk=0.35` + GPU lenta → cola ASR | Med | Smoke manual en `low`; documentar subir confianza / volver a `stable` |
| UI confusa al quitar spinbox chunk | Low | Nota en settings: el chunk lo fija el modo / Restablecer |

## Open Questions

Ninguna bloqueante tras la aprobación del spec.

## Verification (antes de IMPLEMENT)

- [x] Cada task tiene acceptance + verify en `tasks/todo.md`
- [x] Orden por dependencias
- [x] Tasks acotadas (~≤5 archivos)
- [x] Checkpoints entre fases
- [x] Humano aprueba este plan
