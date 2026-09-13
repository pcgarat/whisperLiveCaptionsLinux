# Tasks: Fase 2.2 — Traducción EN→ES

Spec: `docs/specs/fase2.2-traduccion-en-es-2026-09-13.md`  
Plan: `tasks/plan.md`

**Estado:** implementación completa (código + unit tests 2026-09-13). Pendiente smoke manual ≥15 min.  
Fase 2.1 cerrada (modo latencia).

---

## Task 1: Config + CaptionUpdate

**Description:** Añadir flags de traducción/idiomas/`show_asr_line` a config (defaults, validación, example); extender `CaptionUpdate` con `translated_text: str | None = None`.

**Acceptance criteria:**
- [x] Defaults: `translation_enabled=false`, `translation_target=es`, `show_asr_line=true`, `installed_languages=["en","es"]`
- [x] Roundtrip save/load restaura flags de traducción
- [x] `CaptionUpdate` acepta `translated_text` opcional sin romper call sites

**Verification:**
- [x] `pytest -q tests/test_config.py`
- [x] Imports/pipeline existentes siguen tipando/compilando

**Dependencies:** None  
**Files:** `src/config.py`, `src/asr/types.py`, `config.example.json`, `tests/test_config.py`  
**Scope:** Medium

---

## Task 2: Translator Null + NLLB CT2

**Description:** Completar `translate.py` con factory; `NullTranslator`; `NllbCt2Translator` (lazy load, EN→ES); tests con fake sin GPU.

**Acceptance criteria:**
- [x] `source_lang == target` o deshabilitado → passthrough
- [x] Factory elige Null vs NLLB según config
- [x] Unit tests no requieren descargar modelo (fake/mock)
- [x] Documentar en docstring/README id del modelo CT2

**Verification:**
- [x] `pytest -q tests/test_translate.py`

**Dependencies:** Task 1  
**Files:** `src/asr/translate.py`, `tests/test_translate.py`, `requirements.txt` (si hace falta pin)  
**Scope:** Medium–Large

---

### Checkpoint A
- [x] `pytest -q` verde sin GPU de traducción
- [x] Passthrough cubierto

---

## Task 3: Pipeline integra translator

**Description:** El pipeline obtiene un `Translator`, traduce solo texto recién confirmado, rellena `translated_text` en `CaptionUpdate` finales; lazy load si el flag está ON.

**Acceptance criteria:**
- [x] Parciales sin llamada a translate
- [x] Finales con traducción ON + `language!=es` → `translated_text` en ES
- [x] Errores de translate no matan el loop ASR

**Verification:**
- [x] Test unitario del helper/wiring con Translator fake
- [x] `pytest -q`

**Dependencies:** Tasks 1–2  
**Files:** `src/asr/pipeline.py`, tests auxiliares  
**Scope:** Medium

---

## Task 4: Overlay + Settings + persistencia

**Description:** Código de idioma clicable (`installed_languages`), toggle traducción, línea ES + línea ASR según flags; Settings `show_asr_line`; app reinicia pipeline si cambian idioma/traducción/profiles de translator; README.

**Acceptance criteria:**
- [x] Toggle e idioma se guardan y restauran entre reinicios
- [x] Layout: traducción ON → línea 1 ES; ASR según `show_asr_line`
- [x] Traducción OFF → una línea ASR como hoy
- [x] Reinicio ASR al cambiar idioma / `translation_enabled` / modelo translator
- [x] README: modelo, VRAM, cómo activar

**Verification:**
- [x] `pytest -q`
- [ ] Manual: ON/OFF, reinicio app, EN→ES smoke ≥15 min

**Dependencies:** Task 3  
**Files:** `src/ui/overlay.py`, `src/ui/settings.py`, `src/app.py`, `README.md`  
**Scope:** Medium–Large

---

### Checkpoint B — Fase 2.2 completa
- [ ] Success criteria del spec (falta smoke manual)
- [x] `pytest -q` verde
- [x] Spec/plan/todo actualizados
