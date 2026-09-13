# Tasks: Fase 2.4 — Presets de calidad de traducción

Spec: `docs/specs/fase2.4-traduccion-presets-calidad-2026-09-13.md`  
Plan: `tasks/plan.md`

**Estado:** implementación completa (2026-09-13). Pendiente smoke manual.

---

## Task 1: Config decode presets

**Acceptance criteria:**
- [x] Default `balanced` en config nueva
- [x] Fábrica se re-sincroniza al validar
- [x] Custom y perfiles usuario persisten; ids fábrica no borrables
- [x] Clamps según spec

**Verification:**
- [x] `pytest -q tests/test_config.py`

---

## Task 2: Aplicar decode en NLLB + pipeline

**Acceptance criteria:**
- [x] `translate` usa decode params
- [x] Cambio de preset sin reiniciar Whisper
- [x] `no_repeat_ngram_size=0` no activa filtro

**Verification:**
- [x] `pytest -q tests/test_translate.py tests/test_pipeline_translate.py`

---

## Task 3: Pestaña Traducciones en Settings

**Acceptance criteria:**
- [x] Dos pestañas: General / Traducciones
- [x] Editar spin → preset `custom`
- [x] Guardar como preset y borrar usuario
- [x] Fábrica no borrable

**Verification:**
- [x] `make test` (48 passed) + `make lint`
- [ ] Manual: crear preset, reiniciar app, sigue seleccionado; comparar Rápido vs Calidad
