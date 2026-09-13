Última modificación: 2026-09-13

# Spec: Fase 2.5 — Modos sticky de traducción

**Estado:** aprobado (2026-09-13, chat).  
**Intent:** `docs/intent/fase2.5-traduccion-sticky-modos-2026-09-13.md`  
**Base:** Fase 2.2 / 2.4

## Objective

Añadir `translation_sticky_mode` con tres valores. Sticky reutiliza traducciones de **tramos ya enviados a NLLB** (checkpoints), sin re-traducir esos prefijos si el texto crece o reescribe la cola. Con `partials`, también se traduce la hipótesis en vivo (no palabras sueltas inventadas: el string ASR completo o su delta sticky).

**Success:** OFF ≡ comportamiento actual; sticky evita NLLB en prefijos checkpoint; parciales adelantan ES; presets de decoding no cambian.

## Tech Stack

Sin deps nuevas. Tocar: `config`, `pipeline` (tx-worker), `overlay` (TX en parciales), Settings pestaña Traducciones, tests.

## Comportamiento

### Config

```json
"translation_sticky_mode": "off"
```

Valores: `off` | `committed` | `partials`. Inválido → `off`. Default → `off`. Hot-swap vía `apply_translation_settings` (sin reiniciar ASR). Al cambiar de modo sticky, resetear checkpoints del worker.

### Checkpoints sticky

Tras cada decode exitoso (o reuso exacto), guardar `(src_completo, es_completo)`.

Al planificar texto `T`:

1. Elegir el checkpoint con `src` más largo tal que `T.startswith(src)`.
2. Si `src == T` → no llamar NLLB; emitir `es` completo (`translation_append=false`).
3. Si `src` es prefijo propio → traducir solo `T[len(src):].strip()`; emitir ES = `es + " " + nuevo` (append=false, texto ES completo).
4. Si ningún checkpoint aplica → traducir `T` entero; resetear cadena a un solo checkpoint.

Unidades = tramos sticky/delta reales del ASR, **no** tokenización artificial.

### Modo `off`

Como hoy: solo confirmados; extensión → delta + `translation_append=true`; rewrite sin prefijo de `_last_tx_committed` → re-traducir todo. Sin checkpoints.

### Modo `committed`

Solo jobs desde `_emit_committed`. Plan sticky con checkpoints. Emisión TX siempre con ES completo y `translation_append=false`.

### Modo `partials`

Como `committed`, y además al emitir parcial ASR (`committed + partial`) encolar job sticky con el **display text** completo. `seq` del job = `_caption_seq` actual (no incrementa). Overlay aplica `translated_text` en updates `is_final=False` si `seq >= _caption_seq`.

Coalescing del tx-worker se mantiene (salta a lo último antes del decode; emite tras decode aunque haya más nuevo).

### Reset checkpoints

`start`, buffer trim + streamer reset, `stop`, cambio de `translation_sticky_mode`.

### UI

Pestaña Traducciones: combo **Modo sticky** con labels en español + tooltip. Persistir al Guardar.

## Project Structure

```
src/config.py
src/asr/pipeline.py
src/ui/settings.py
src/ui/overlay.py
src/app.py
config.example.json
tests/test_config.py
tests/test_pipeline_translate.py
tests/test_overlay_captions.py
docs/intent|specs/…
tasks/plan.md, tasks/todo.md
flujo-traductor-2026-09-13.md (si se mantiene)
README.md (mención breve)
```

## Commands

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
make lint
```

## Code Style

Helper puro `plan_sticky_translation(checkpoints, text) -> ...` testeable. Sin comentarios obvios.

## Testing Strategy

| Nivel | Qué |
| --- | --- |
| Unit | validate default/clamp de modo |
| Unit | plan sticky: extensión, reuse exacto, rewrite cola conserva prefijo |
| Unit | pipeline `committed`: no re-traduce prefijo tras rewrite de cola |
| Unit | pipeline `partials`: encola/traduce display parcial; coalesce |
| Unit | overlay acepta TX en parcial |
| Manual | sticky+parciales con habla real ≥5 min |

## Boundaries

**Always:** OFF = comportamiento previo; sticky no parte en palabras; decoding del panel; hot-swap; local.

**Ask first:** Alineación sub-checkpoint EN↔ES; traducir solo el `partial` suelto sin committed; nuevo modelo.

**Never:** Cloud; auto-detect; bloquear UI en NLLB; romper seq anti-pisado de confirmados.

## Success Criteria

1. Combo visible y persistente.
2. `off` no cambia tests actuales de delta/append.
3. Sticky committed: `Hello`→TX luego `Hello word`→TX delta luego `Hello world` → NLLB solo recibe `world` (no `Hello`).
4. Sticky partials: aparece ES antes del commit cuando hay hipótesis.
5. `pytest -q` + `make lint` verdes.

## ASSUMPTIONS

1. Emisión sticky siempre con ES completo (`append=false`) para no desincronizar overlay en rewrites.
2. Acortar a un prefijo sin checkpoint exacto → re-traducir ese prefijo (sin magia de truncar ES).
3. Labels UI: «Normal (como ahora)», «Sticky (solo confirmados)», «Sticky + parciales».
