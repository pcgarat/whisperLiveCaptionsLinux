# Tasks: Fase 2.7 — Pestaña Apariencia + alineación

Spec: `docs/specs/fase2.7-apariencia-alineacion-2026-09-13.md`  
Plan: `tasks/plan.md`

**Estado:** implementación completa (2026-09-13). Pendiente smoke manual.

---

## Task 1: Config + example

**Acceptance criteria:**
- [x] Default `text_align=center`
- [x] Valores inválidos → `center`
- [x] Clave en `config.example.json`

**Verification:**
- [x] `pytest -q tests/test_config.py`

---

## Task 2: Settings pestaña Apariencia

**Acceptance criteria:**
- [x] Controles de aspecto fuera de General
- [x] Combo Centro / Izquierda + preview alineada
- [x] Persistencia en `result_config`

**Verification:**
- [x] `pytest -q tests/test_settings_ui.py`

---

## Task 3: Overlay + tests

**Acceptance criteria:**
- [x] Labels de caption respetan `text_align` en `apply_config`
- [x] Tests unitarios

**Verification:**
- [x] `make test` (86 passed) + `make lint`
- [ ] Manual: Centro↔Izquierda en overlay al Guardar
