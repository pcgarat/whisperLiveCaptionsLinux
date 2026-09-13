Última modificación: 2026-09-13

# Intent: Fase 2.2 — Traducción EN→ES

Confirmado en entrevista 2026-09-13.

## Framing

- **2.1:** modo baja latencia (hecho).
- **2.2 (este intent):** traducción local a español + chrome de idioma/toggle.
- Más idiomas fuente reales: después; la UI/config se prepara.

## Intent

- **Outcome:** Traducción local **EN→ES** con toggle en el overlay; idioma fuente clicable entre idiomas instalados; línea ASR opcional.
- **User:** Solo el autor, vídeos EN → leer ES.
- **Why now:** Latencia ya controlada; el siguiente dolor es entender el contenido en español sin cloud.
- **Success:** EN→ES usable ≥15 min; fuente `es` o traducción OFF → passthrough; tests unitarios verdes.
- **Constraint:** 100 % local; ASR/traducción fuera del hilo UI; idioma fuente **manual**; no reutilizar Marian multi-modelo del proyecto viejo.
- **Out of scope:** Otros pares como criterio de éxito, auto-detect, cloud, diarización, Whisper `task=translate` como “traducir a ES”.

## UI acordada

1. Código de idioma fuente clicable → elige entre idiomas **instalados** (MVP success: `en`; lista ampliable).
2. Toggle de **traducción** al lado (target fijo **ES** en 2.2).
3. **Línea 1 (ES):** solo con traducción ON; texto **confirmado** traducido (no cada parcial).
4. **Línea 2 (ASR en vivo):** siempre el ASR como ahora; se activa/desactiva en **Settings** (`show_asr_line` o equivalente).
5. Traducción OFF → layout de una línea ASR como hoy (la “segunda línea” aplica sobre todo cuando hay traducción / cuando el setting la pide).
6. **Persistencia:** `translation_enabled`, `language`, `installed_languages`, `show_asr_line`, `translation_target` (y el resto de config) se **guardan y restauran** entre reinicios como cualquier otro parámetro.

## Siguiente paso

`spec-driven-development` → `docs/specs/fase2.2-traduccion-en-es-2026-09-13.md`
