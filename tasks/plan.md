# Plan: Fase 2.8 — Presets generales de aplicación

Spec: `docs/specs/fase2.8-presets-generales-app-2026-09-13.md`  
Intent: `docs/intent/fase2.8-presets-generales-app-2026-09-13.md`  
Rama: `feat/presets-generales-app`

## Enfoque

1. **Config:** `app_preset` / `app_presets` + helpers snapshot/apply/CRUD (sin meta recursiva).
2. **AppController:** aplicar preset al instante con matriz restart/hot-swap + geometría; persistir.
3. **Settings UI:** barra encima de tabs (combo, Guardar, Guardar como…, Borrar).
4. **Tests + README** + smoke manual de geometría/monitor ausente.

## Orden de slices

Config (testeable) → apply en app → UI → docs/README.
