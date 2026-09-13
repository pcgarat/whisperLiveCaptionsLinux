Última modificación: 2026-09-13

# Spec: Fase 2.6 — Política de display de captions

**Estado:** aprobado (2026-09-13, chat).  
**Intent:** `docs/intent/fase2.6-politica-display-captions-2026-09-13.md`  
**Base:** Fase 1 (parcial+confirmado) + overlay/pipeline actuales.

## Objective

Dos knobs de display independientes. Default = comportamiento actual. Éxito: OFF de parciales no pinta hipótesis; OFF de rewrite no sustituye ni acorta texto confirmado ya mostrado; el overlay es un scroll anclado al final (siempre se ve lo último). Un commit divergente sin prefijo común con la frase actual **no borra** scrollback: abre frase nueva.

## Tech Stack

Sin deps nuevas. Tocar: `config`, `pipeline` (filtro parciales + reset), `overlay`, Settings (General), `CaptionUpdate`, tests, `config.example.json`.

## Comportamiento

### Config

```json
"captions_show_partials": true,
"captions_allow_rewrite": true
```

- Bool; ausente → default `true`. Hot-swap al Guardar (sin reinicio ASR).
- Sync a `pipeline.config` para el filtro de parciales.

### `captions_show_partials`

| Valor | Efecto |
| --- | --- |
| `true` | Emite y muestra parciales (`is_final=False`) como hoy. |
| `false` | Pipeline no pone parciales en la cola ni agenda TX sticky de parciales. Overlay ignora parciales residuales y oculta `partial_label`. Al desactivar, limpia `_partial_text`. |

No altera commits ni `second_line_mode` (con TX, `live_asr` solo tendrá confirmed si no hay parciales).

### `captions_allow_rewrite`

| Valor | Efecto |
| --- | --- |
| `true` | Crece por extensión; permite corregir la frase actual si comparte prefijo de palabras (sin acortar); divergencia sin prefijo → nueva frase (append al scrollback, no wipe). Pipeline emite acortes/rewrites. |
| `false` | Pipeline **no encola** commits que no extiendan el último texto ya enviado al overlay (ni su TX). Overlay solo acepta extensión (o set si está vacío). |

El estado interno del streamer (`_last_committed`) sigue actualizándose aunque no se emita al UI, para no bloquear el ASR.

### Reset de frase

Tras buffer trim + `streamer.reset()`:

- Emitir `reset_display` como **corte de frase**, no como wipe.
- El overlay **conserva** lo pintado y **añade** la frase nueva.
- Viewport fijo con scroll interno anclado abajo: lo viejo sube, siempre se lee lo último.
- El buffer de display se recorta por caracteres (cola) para no crecer sin límite.
- Rewrite OFF solo impide sustituir texto *dentro* de la frase actual.

### UI

Pestaña General → sección **Subtítulos**:

1. Checkbox **Mostrar texto parcial** + tooltip.
2. Checkbox **Permitir reescritura** + tooltip.

Persistir en `result_config()` / `config.json`.

### Conflicto: sin parciales + sticky parciales

Incompatible: `captions_show_partials=false` y `translation_sticky_mode=partials`.

Al crear el conflicto (toggle, combo o Guardar), diálogo modal:

- Texto explicando por qué no se pueden mezclar.
- **Cancelar** → deshace el cambio que provocó el conflicto (en Guardar: no cierra/acepta).
- Botón de arreglo → cambia la *otra* opción a una compatible:
  - Si se desactivaron parciales → sticky pasa a `committed`.
  - Si se eligió sticky parciales → se activan parciales.
  - En Guardar → sticky a `committed` (conserva sin parciales).

### Tooltips (texto)

- Parciales: explicar que ON muestra la hipótesis en vivo (puede cambiar) y OFF solo actualiza al confirmar (más estable, más “a saltos”).
- Reescritura: explicar que ON permite corregir texto ya confirmado y OFF solo deja crecer; el overlay es un scroll anclado abajo.

## Project Structure

```
src/config.py
src/asr/types.py
src/asr/pipeline.py
src/ui/overlay.py
src/ui/settings.py
src/app.py
src/debug/trace.py
config.example.json
tests/test_config.py
tests/test_overlay_captions.py
tests/test_pipeline_translate.py (si aplica filtro parcial)
docs/intent|specs/…
tasks/plan.md, tasks/todo.md
```

## Commands

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
make lint
```

## Testing Strategy

| Nivel | Qué |
| --- | --- |
| Unit | Defaults y bools en `validate_config` |
| Unit | Overlay: `show_partials=false` ignora parcial |
| Unit | Overlay: `allow_rewrite=false` ignora shrink/rewrite; acepta extensión |
| Unit | Overlay: `reset_display` limpia buffers |
| Unit | Pipeline: `show_partials=false` no encola parcial |
| Unit | Conflicto parciales↔sticky: detect + cancel/fix en Settings |
| Manual | Toggles ON/OFF con habla real unos minutos |

## Boundaries

**Always:** Defaults = comportamiento previo; knobs independientes; hot-swap; local.

**Ask first:** Filtrar acortes también en pipeline; unificar con `second_line_mode`.

**Never:** Cloud; auto-detect; bloquear UI; romper seq anti-pisado de TX.

## Success Criteria

1. Dos checkboxes visibles con tooltip al hover; persisten.
2. Defaults `true`/`true` no cambian tests existentes relevantes.
3. Sin parciales → no aparece hipótesis en overlay.
4. Sin rewrite → texto confirmado solo crece o se limpia en reset.
5. `pytest -q` + `make lint` verdes.

## Open Questions

Ninguna pendiente (chat 2026-09-13).
