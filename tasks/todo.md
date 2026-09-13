# Tasks: Fase 2.3 — Instalar idiomas

Spec: `docs/specs/fase2.3-instalar-idiomas-2026-09-13.md`  
Plan: `tasks/plan.md`

**Estado:** implementación completa (2026-09-13). Pendiente smoke manual.

---

## Task 1: Catálogo de idiomas

**Description:** Crear `src/asr/languages.py` con `AVAILABLE_LANGUAGES`, helpers de etiqueta/merge; alinear claves con `NLLB_LANG_CODES`; tests.

**Acceptance criteria:**
- [x] Catálogo con al menos en/es/fr/de/it/pt
- [x] `merge_installed_languages` añade sin duplicar
- [x] Claves del catálogo == claves NLLB

**Verification:**
- [x] `pytest -q tests/test_languages.py`

**Dependencies:** None  
**Files:** `src/asr/languages.py`, `src/asr/translate.py`, `tests/test_languages.py`  
**Scope:** Small

---

## Task 2: Settings UI + docs

**Description:** Combo de idioma instalado; diálogo instalar con checks; refresco del combo; README.

**Acceptance criteria:**
- [x] Selector Settings solo muestra instalados
- [x] Instalar seleccionados los añade y refresca combo
- [x] `result_config()` incluye `installed_languages` actualizado
- [x] README menciona el flujo

**Verification:**
- [x] `pytest -q`
- [ ] Manual: instalar fr → Guardar → overlay muestra FR

**Dependencies:** Task 1  
**Files:** `src/ui/settings.py`, `src/ui/overlay.py`, `README.md`, `tasks/todo.md`  
**Scope:** Medium
