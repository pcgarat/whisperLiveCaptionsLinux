# Plan: Fase 2.4 — Presets de calidad de traducción

Spec: `docs/specs/fase2.4-traduccion-presets-calidad-2026-09-13.md`  
**Estado:** implementación completa (spec aprobado 2026-09-13). Pendiente smoke manual.

## Enfoque

1. **Config:** constantes de fábrica, clamp, `effective_translation_decode`, migración, CRUD usuario. ✅
2. **Motor:** `translate_batch` con knobs; hot-swap decode sin recrear modelo. ✅
3. **UI:** pestañas General / Traducciones; presets + Guardar/Borrar. ✅
4. **Docs/tests.** ✅
