Última modificación: 2026-09-13

# Spec: Fase 2.4 — Presets de calidad de traducción

**Estado:** aprobado (2026-09-13).  
**Intent:** `docs/intent/fase2.4-traduccion-presets-calidad-2026-09-13.md`  
**Base:** Fase 2.2 (`docs/specs/fase2.2-traduccion-en-es-2026-09-13.md`)

## Objective

Exponer y persistir parámetros de **decoding** del traductor NLLB CT2 desde Settings, en una pestaña **Traducciones**, con presets de fábrica, Custom persistente y presets de usuario (crear/borrar).

**Usuario:** solo el autor.

**Success de producto:** poder pasar de “rápido/flojo” a “más calidad / más CPU” sin editar código, y recuperar esa elección tras reiniciar.

## Tech Stack

Sin dependencias nuevas. Reutilizar:

| Pieza | Uso |
|-------|-----|
| `ctranslate2.Translator.translate_batch` | `beam_size`, `length_penalty`, `no_repeat_ngram_size` |
| Config JSON | perfiles + preset activo |
| PyQt6 Settings | `QTabWidget` (General / Traducciones) |

## Comportamiento

### Parámetros (únicos en alcance)

| Clave | Tipo | Rango (clamp) | Default Equilibrado |
|-------|------|---------------|---------------------|
| `beam_size` | int | 1–8 | 4 |
| `length_penalty` | float | 0.6–1.5 | 1.0 |
| `no_repeat_ngram_size` | int | 0–5 (`0` = off) | 3 |

### Presets de fábrica (inmutables)

Ids estables en código; labels en UI en español:

| Id | Label | beam | length_penalty | no_repeat_ngram |
|----|-------|------|----------------|-----------------|
| `fast` | Rápido | 2 | 1.0 | 0 |
| `balanced` | Equilibrado | 4 | 1.0 | 3 |
| `quality` | Calidad | 6 | 1.1 | 3 |

- `custom` es un perfil especial (no fábrica de producto, pero siempre presente): guarda los últimos valores editados a mano.
- Default de config nueva: preset activo **`balanced`**.

### Presets de usuario

- **Guardar como preset…:** diálogo de nombre; id = slug seguro (minúsculas, `[a-z0-9_-]`, sin vacío); rechazar colisión con ids de fábrica (`fast`/`balanced`/`quality`/`custom`) o con otro usuario.
- **Borrar:** solo si el id no es de fábrica ni `custom`. Si el borrado era el activo → pasar a `custom` (conservando valores actuales) o `balanced` si no hay valores (preferir **`custom`** con snapshot actual).
- **No renombrar** en esta fase.

### UX Settings

1. `QTabWidget`: pestaña **General** (todo lo actual excepto bloque Traducción) y **Traducciones**.
2. En **Traducciones**:
   - `second_line_mode` (mover desde la sección actual).
   - Combo **Preset** (fábrica + Custom + usuario).
   - Spins: beam / length penalty / no-repeat n-gram (tooltips en español).
   - Botones: **Guardar como preset…**, **Borrar preset** (enabled solo si usuario), opcional **Restablecer** al valor de fábrica del preset fábrica seleccionado (si aplica; para `custom`/usuario no obligatorio en v1 — **Ask:** omitir restablecer salvo presets fábrica; en v1: al elegir de nuevo un preset fábrica se recargan valores de fábrica desde constante, **no** desde copia editable en config).
3. Editar un spin con preset ≠ `custom` → preset pasa a `custom` y se copian los valores resultantes al perfil `custom`.
4. Elegir preset fábrica → cargar valores de la constante de fábrica (ignorar basura en `translation_profiles` para esas keys; al cargar config se re-sincronizan fábrica).
5. Elegir preset usuario o `custom` → cargar desde `translation_profiles`.

### Aplicación en runtime

- Los knobs se leen en cada `translate()` / `translate_batch` (no hace falta recargar el modelo NLLB).
- Al **Guardar** Settings: persistir y hot-aplicar vía el mismo camino que `apply_translation_settings` (ampliar keys de snapshot), **sin** reiniciar Whisper/captura.
- Overlay toggle ES no cambia.

### Config (propuesta)

```json
{
  "translation_decode_preset": "balanced",
  "translation_profiles": {
    "fast": { "beam_size": 2, "length_penalty": 1.0, "no_repeat_ngram_size": 0 },
    "balanced": { "beam_size": 4, "length_penalty": 1.0, "no_repeat_ngram_size": 3 },
    "quality": { "beam_size": 6, "length_penalty": 1.1, "no_repeat_ngram_size": 3 },
    "custom": { "beam_size": 4, "length_penalty": 1.0, "no_repeat_ngram_size": 3 }
  }
}
```

Notas de migración:

- Config antigua sin estas keys → defaults (`balanced` + perfiles fábrica + `custom` = copia de `balanced`).
- Claves de fábrica en `translation_profiles` siempre se sobrescriben al validar con la constante (el usuario no “edita fábrica”; editar → `custom`).
- Perfiles con id desconocido (no fábrica, no `custom`) = usuario; se clampean.

Helper: `effective_translation_decode(cfg) -> dict` análogo a `effective_latency_profile`.

## Project Structure (tocar)

```
src/config.py                 # presets, clamp, effective_*, validate
src/asr/translate.py          # pasar knobs a translate_batch
src/asr/pipeline.py           # snapshot de decode en translate_confirmed / hot-swap keys
src/ui/settings.py            # QTabWidget + pestaña Traducciones
config.example.json
tests/test_config.py
tests/test_translate.py       # mock: beam_size etc llegan al translator
tests/test_settings_ui.py     # si ya hay harness; preset→custom al editar
docs/intent|specs/…
README.md                     # mención breve presets
tasks/plan.md, tasks/todo.md
```

## Commands

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
make lint
make run
```

## Code Style

- Misma forma que latencia: constantes `TRANSLATION_FACTORY_PRESETS`, helpers puros en `config.py`.
- Protocol `Translator.translate(...)` puede aceptar kwargs opcionales de decode **o** el translator lee un `decode_params` inyectado; preferir **argumentos en `translate` / método `set_decode_params`** sin romper callers: ampliar firma con params opcionales con defaults del equilibrado.
- Sin comentarios obvios.

Ejemplo de estilo deseado:

```python
results = self._translator.translate_batch(
    [source_tokens],
    target_prefix=[[tgt_code]],
    beam_size=int(decode["beam_size"]),
    length_penalty=float(decode["length_penalty"]),
    no_repeat_ngram_size=int(decode["no_repeat_ngram_size"]) or None,
    max_decoding_length=256,
)
```

(`no_repeat_ngram_size=0` → no pasar / `None` según API CT2.)

## Testing Strategy

| Nivel | Qué |
|-------|-----|
| Unit | Clamps, migración defaults, factory overwrite, slug de nombre, borrar usuario |
| Unit | `effective_translation_decode` respeta preset activo |
| Unit | Translator (fake CT2) recibe beam/length/ngram del decode activo |
| UI (si viable sin display) | Editar spin → preset `custom`; fábrica no borrable |
| Manual | Cambiar Rápido↔Calidad con traducción ON; Guardar como preset; reiniciar y ver restauración |
| No CI | Calidad subjetiva del español |

## Boundaries

**Always:**
- Solo decoding; persistir preset + perfiles en `config.json`.
- Hot-aplicar al Guardar sin reiniciar ASR.
- Fábrica inmutable; Custom y usuario persistentes.
- Actualizar este spec si se añaden knobs o buffer/contexto.

**Ask first:**
- Cambiar modelo / float16 / Marian.
- Buffer por oración o contexto multi-frase.
- Añadir renombrado de presets.
- Deps nuevas.

**Never:**
- Cloud.
- Traducir parciales por este cambio.
- Permitir borrar/sobrescribir `fast`/`balanced`/`quality`.
- Bloquear UI esperando translate.

## Success Criteria

1. Settings tiene pestaña **Traducciones** con segunda línea + presets + knobs.
2. Default nuevo = `balanced`; valores llegan a `translate_batch`.
3. Editar knobs → `custom`; Custom sobrevive reinicio.
4. Guardar como preset crea entrada seleccionable; borrar solo usuario.
5. Cambiar preset y Guardar afecta traducciones siguientes sin reiniciar captura/Whisper.
6. `pytest -q` verde; README menciona la pestaña/presets.

## ASSUMPTIONS

1. Valores de fábrica de la tabla anterior (elige el agente; ajustables si el usuario los nota extremos).
2. Fábrica siempre re-sincronizada desde constante al `validate_config` (no “editar fábrica en disco”).
3. `no_repeat_ngram_size=0` desactiva el filtro en CT2.
4. Nombre de preset usuario → slug; UI muestra el id slugificado (sin label separado en v1).
5. Mover `second_line_mode` a la pestaña Traducciones (General queda sin bloque Traducción).

---

**Siguiente:** tras aprobación → PLAN/TASKS e implementación.
