# Tasks: Fase 2.8 — Presets generales de aplicación

Spec: `docs/specs/fase2.8-presets-generales-app-2026-09-13.md`  
Plan: `tasks/plan.md`  
Rama: `feat/presets-generales-app`

**Estado:** implementación completa (2026-09-13). Pendiente smoke manual.

---

## Task 1: Config — modelo + helpers

**Acceptance criteria:**
- [x] Defaults `app_preset=null`, `app_presets={}` en `DEFAULTS` / `validate_config` / `config.example.json`
- [x] `snapshot_app_config` excluye meta; `apply_app_preset` conserva `app_presets`
- [x] CRUD: guardar (overwrite), guardar como (slug + colisión), borrar
- [x] Snapshot incluye geometría y el resto de keys de estado

**Verification:**
- [x] `pytest -q tests/test_config.py tests/test_app_presets.py`

---

## Task 2: AppController — apply al instante

**Acceptance criteria:**
- [x] Cambiar preset aplica config + persiste sin esperar Guardar del diálogo
- [x] Matriz ASR-restart / latency hot-swap / translation hot-swap / overlay UI
- [x] Geometría overlay + Settings restaurada (clamp pantallas)
- [x] Monitor inexistente: conservar actual + aviso; resto se aplica
- [x] “(ninguno)” solo limpia `app_preset`, no revierte estado

**Verification:**
- [x] Tests unitarios del merge/apply (`tests/test_app_presets.py`)
- [ ] Smoke manual con `make run`

---

## Task 3: Settings UI — barra de presets

**Acceptance criteria:**
- [x] Combo + Guardar + Guardar como… + Borrar encima del `QTabWidget`
- [x] Guardar disabled sin activo; Borrar con confirmación
- [x] Guardar como pide nombre, crea y selecciona
- [x] Cambiar combo dispara apply inmediato (callback a controller)

**Verification:**
- [x] `pytest -q tests/test_settings_ui.py`
- [ ] Manual: crear 2 presets, alternar, reiniciar app

---

## Task 4: README + cierre

**Acceptance criteria:**
- [x] README menciona presets generales (Guardar / Guardar como / Borrar, apply al instante)
- [x] `make test` / lint verdes (114 passed, ruff OK)

**Verification:**
- [x] `pytest -q` + `ruff check src tests`
