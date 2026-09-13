# Tasks: Fase 2.5 — Modos sticky de traducción

Spec: `docs/specs/fase2.5-traduccion-sticky-modos-2026-09-13.md`  
Plan: `tasks/plan.md`

**Estado:** implementación completa (2026-09-13). Pendiente smoke manual.

---

## Task 1: Config sticky mode

**Acceptance criteria:**
- [x] Default `off`
- [x] Valores inválidos → `off`
- [x] Clave en `config.example.json`

**Verification:**
- [x] `pytest -q tests/test_config.py`

---

## Task 2: Pipeline sticky + parciales

**Acceptance criteria:**
- [x] `off` conserva delta/append actual
- [x] `committed` reutiliza checkpoints en rewrite de cola
- [x] `partials` traduce display parcial con sticky
- [x] Hot-swap resetea checkpoints

**Verification:**
- [x] `pytest -q tests/test_pipeline_translate.py`

---

## Task 3: Overlay + Settings

**Acceptance criteria:**
- [x] Overlay aplica `translated_text` en parciales si seq vigente
- [x] Combo en pestaña Traducciones; persiste al Guardar
- [x] `translation_sticky_mode` en hot-swap de app

**Verification:**
- [x] `pytest -q tests/test_overlay_captions.py`
- [x] `make test` (64 passed) + `make lint`
- [ ] Manual: sticky committed vs partials con habla real ≥5 min
