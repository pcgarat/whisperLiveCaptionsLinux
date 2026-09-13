Última modificación: 2026-09-13

# Spec: Fase 2.2 — Traducción EN→ES

**Estado:** aprobado (2026-09-13); enmienda segunda línea (selector).  
**Intent:** `docs/intent/fase2.2-traduccion-en-es-2026-09-13.md`  
**Base:** Fase 1 + 2.1 (`docs/specs/fase2.1-baja-latencia-2026-09-13.md`)  
**Skill de diseño:** `.cursor/skills/add-translation-phase/SKILL.md`

## Objective

Añadir traducción **100 % local** del texto ASR confirmado a español, con controles en el overlay y una segunda línea configurable.

**Usuario:** solo el autor.

**Fase 2.2 (este spec):**
- Success de producto: **EN→ES** estable.
- Idioma fuente sigue siendo **manual** (sin auto-detect).
- Target de traducción en esta fase: **`es`** fijo.
- Traducir solo `is_final` (confirmado), no cada parcial.
- UI: código de idioma clicable + toggle traducción; Settings: mostrar/ocultar línea ASR.

**Fuera de 2.2:**
- Calidad garantizada de otros pares (fr→es, etc.) — solo dejar la puerta abierta.
- Auto-detect, cloud, diarización.
- Copiar Marian multi-modelo de `live_translate_subtitles`.
- Usar Whisper `task=translate` (solo traduce a inglés) como solución a “traducir a ES”.

## Tech Stack

| Pieza | Elección propuesta |
|-------|--------------------|
| Contrato | Protocolo `Translator` en `src/asr/translate.py` |
| Motor MVP | **NLLB-200 distilled (CT2)** un solo modelo multilingual (preferido al skill) |
| Alternativa si VRAM aprieta | CT2 `int8` y/o traducción en **CPU**; Ask antes de cambiar a Marian opus-mt-en-es |
| Hilos | Traducción en worker ASR (o cola dedicada), **nunca** en el hilo UI |
| UI | PyQt6 overlay + Settings |

**Ask first** antes de añadir deps pesadas (`transformers` full, torch extra, descarga multi-GB). Preferir paquetes CT2 ya convertidos / `ctranslate2` + tokenizers ligeros.

## Comportamiento

### Traducción
- `translation_enabled=true` y `language != es` → traducir texto confirmado a ES y mostrarlo en **línea 1**.
- `language == es` o toggle OFF → `NullTranslator` / passthrough; **sin** línea 1 de traducción.
- Fallo del traductor → no tumbar la app; mostrar ASR; log/mensaje discreto opcional.

### Overlay
| Elemento | Comportamiento |
|----------|----------------|
| Código idioma | Clic → menú de `installed_languages` (MVP: al menos `en`; incluir `es` para passthrough) |
| Toggle ES | Activa/desactiva `translation_enabled`; persiste en config |
| Línea 1 | ES confirmado traducido; visible solo si traducción ON y hay texto |
| Línea 2 | Con traducción ON, según `second_line_mode` (una sola fila visual; **nunca** traducción + final + parcial = 3 líneas). Con traducción OFF: ASR final+parcial como hoy |

Valores de `second_line_mode`:
- `live_asr` — ASR en vivo (confirmado + parcial en **una** línea)
- `original` — solo texto confirmado en el idioma fuente
- `none` — sin segunda línea

### Settings
- Selector: **Segunda línea** (`second_line_mode`, default `live_asr`).
- Migración: legacy `show_asr_line=true|false` → `live_asr` / `none`.
- Lista o nota de idiomas instalados (MVP puede ser fija en código + config).

### Config (propuesta)

```json
{
  "language": "en",
  "installed_languages": ["en", "es"],
  "translation_enabled": false,
  "translation_target": "es",
  "second_line_mode": "live_asr",
  "translator_model": "nllb-200-distilled-ct2"
}
```

Default `translation_enabled=false` en **config nueva**; si el usuario lo activa, el valor (y el resto de flags de traducción/idioma/`second_line_mode`) **persisten en `config.json` y se restauran al reiniciar** como el resto de parámetros. Carga del modelo: lazy al primer ON de la sesión, o al arranque si el flag ya venía `true` en config.

## Contrato de datos

Extender sin romper el polling actual, p. ej.:

```python
@dataclass(frozen=True)
class CaptionUpdate:
    text: str                 # ASR (origen)
    is_final: bool
    language: str             # fuente elegida
    ts_mono: float
    translated_text: str | None = None  # ES si aplica; solo con is_final relevante
```

La UI:
- actualiza línea ASR desde `text` / parciales como ahora;
- actualiza línea ES solo cuando `translated_text` no es `None` (típicamente en updates finales).

## Project Structure (tocar)

```
src/asr/translate.py      # NullTranslator + NllbTranslator (CT2)
src/asr/types.py          # CaptionUpdate.translated_text
src/asr/pipeline.py       # traducir finales; lazy load
src/ui/overlay.py         # lang click, toggle, línea ES + ASR
src/ui/settings.py        # second_line_mode
src/config.py             # nuevos campos + validación
config.example.json
tests/test_translate.py   # passthrough, EN→ES mockeado
tests/test_config.py
docs/intent|specs/…
tasks/plan.md, tasks/todo.md
```

## Commands

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
./scripts/run.sh
```

Documentar descarga/caché del modelo de traducción en README.

## Code Style

- Implementar `Translator`; pipeline depende del protocol, no de NLLB concreto.
- Lazy-load del modelo al activar traducción (o al start si ya estaba ON).
- No bloquear Qt: traducción en el mismo worker ASR **después** de confirmar, o hilo/cola propia si la latencia de translate supera ~200–300 ms de forma habitual.
- Sin comentarios obvios.

## Testing Strategy

| Nivel | Qué |
|-------|-----|
| Unit | `NullTranslator` passthrough; con `source==es` no traduce |
| Unit | Pipeline/helper: solo llama `translate` en `is_final` |
| Unit | Config: defaults y clamps de flags nuevos |
| Manual | EN→ES ≥15 min; toggle ON/OFF; `second_line_mode`; click idioma `en`/`es` |
| No CI | Inferencia NLLB GPU real (mock del Translator en unit) |

## Boundaries

**Always:**
- Traducción local; solo confirmados.
- ASR + translate fuera del hilo UI.
- Passthrough si `language==es` o toggle OFF.
- Persistir y restaurar flags de traducción/idioma/`second_line_mode` en `config.json` entre reinicios.
- Actualizar este spec si cambia el modelo o el layout.

**Ask first:**
- Añadir `transformers`/torch pesado o cambiar a Marian opus-mt-en-es.
- Descargar modelos >~1 GB sin documentar tamaño/VRAM.
- Traducir parciales (rompería el acuerdo de estabilidad).

**Never:**
- Cloud/API de traducción.
- Auto-detect de idioma.
- Reutilizar código del repo `live_translate_subtitles`.
- Bloquear el overlay esperando translate.

## Success Criteria

1. Toggle traducción e idioma en overlay / Settings **persisten** y se restauran al reiniciar; se reinicia/recarga translator según haga falta.
2. Con EN + traducción ON, línea 1 muestra ES de texto confirmado; línea 2 según `second_line_mode` (`live_asr` / `original` / `none`); como máximo **2** líneas de caption.
3. Con traducción OFF, overlay vuelve al comportamiento de una línea ASR.
4. Con idioma `es`, no se invoca traducción real (passthrough).
5. Click en código de idioma cambia entre `installed_languages` y persiste.
6. Sesión manual EN→ES ≥15 min sin cuelgue de UI.
7. `pytest -q` verde sin GPU de traducción obligatoria.
8. README documenta modelo, VRAM aproximada y cómo activar traducción.

## ASSUMPTIONS / Open Questions

Resueltas al aprobar el spec (2026-09-13):

1. Modelo → **NLLB-200 distilled vía CT2** (lazy; CUDA int8 o CPU si hace falta).
2. Default `translation_enabled` → **false** en config nueva; si el usuario lo activa, **persiste y se restaura** al reiniciar.
3. Default `second_line_mode` → **`live_asr`** (migración desde `show_asr_line`).
4. Carga → **lazy** al primer ON; si el flag ya venía `true` en config, cargar al arrancar el pipeline.
5. Solo texto **confirmado**; flags de traducción/idioma en `config.json` como el resto.

---

**Siguiente:** PLAN / TASKS en `tasks/plan.md` y `tasks/todo.md` (solo 2.2).
