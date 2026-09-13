Última modificación: 2026-09-13

# Intent: Fase 2.4 — Presets de calidad de traducción

Confirmado en entrevista 2026-09-13.

## Framing

- **2.2:** traducción NLLB CT2 EN→ES (hecho).
- **2.3:** instalar idiomas (hecho).
- **2.4 (este intent):** tunear decoding de traducción desde Settings, con presets.

## Intent

- **Outcome:** Pestaña «Traducciones» en Settings con presets de calidad (fábrica + usuario) y knobs de decoding.
- **User:** Solo el autor, afinando calidad vs latencia/VRAM en sesiones reales.
- **Why now:** Las traducciones salen flojas; quiere tunear sin tocar código.
- **Success:** Elegir preset (o Custom) aplica valores al traducir; Custom y presets de usuario persisten al reiniciar; guardar config actual como preset nuevo; borrar presets de usuario (no los de fábrica).
- **Constraint:** Solo decoding (`beam_size`, `length_penalty`, `no_repeat_ngram_size`); sin cambiar modelo, buffer ni contexto; 100 % local; UI alineada con el patrón de latencia (editar → Custom).
- **Out of scope:** Marian/otro modelo, buffer por oración, contexto multi-frase, renombrar presets, cloud.

## UI acordada

1. Settings con pestaña dedicada **Traducciones** (mover aquí lo de traducción que hoy esté en la vista única, p. ej. segunda línea).
2. Selector de preset: fábrica (`Rápido` / `Equilibrado` / `Calidad`) + `Custom` + presets de usuario.
3. Sliders/spins de decoding; al editar fuera de Custom → pasa a Custom.
4. Custom (valores) se mantienen entre reinicios.
5. Acción **Guardar como preset…** (nombre); **Borrar** solo presets de usuario.
6. Presets de fábrica no se borran ni se sobrescriben.

## Siguiente paso

`spec-driven-development` → `docs/specs/fase2.4-traduccion-presets-calidad-2026-09-13.md`
