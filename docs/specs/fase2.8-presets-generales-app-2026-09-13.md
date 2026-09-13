Última modificación: 2026-09-13

# Spec: Fase 2.8 — Presets generales de aplicación

**Estado:** aprobado (decisiones confirmadas 2026-09-13).  
**Intent:** `docs/intent/fase2.8-presets-generales-app-2026-09-13.md`  
**Base:** config unificada (`src/config.py`), Settings (`src/ui/settings.py`), apply path en `src/app.py`.

## Objective

Permitir guardar, aplicar al instante y borrar **presets generales de usuario** que restauran el estado completo de la app (pipeline + UI + geometría).

**Usuario:** solo el autor.

**Success de producto:** recuperar una sesión tipificada (idioma/modelo/audio/latencia/TX/apariencia/ventanas) en un clic, y persistir esos presets entre reinicios.

## Tech Stack

Sin dependencias nuevas. Reutilizar:

| Pieza | Uso |
|-------|-----|
| `config.json` + `validate_config` | almacén de presets + blob snapshot |
| PyQt6 Settings | barra de presets encima del `QTabWidget` |
| `AppController.open_settings` / hot-swap / restart | aplicar snapshot con la misma matriz ASR vs hot-swap |

## Modelo de datos

```json
{
  "app_preset": null,
  "app_presets": {
    "directo-es": { /* snapshot completo validate_config, sin meta */ }
  }
}
```

| Clave | Tipo | Default | Notas |
|-------|------|---------|-------|
| `app_preset` | `string \| null` | `null` | Id del último preset aplicado/guardado; `null` = ninguno |
| `app_presets` | `object` | `{}` | Mapa id → snapshot. **Sin fábrica.** |

### Qué entra en un snapshot

**Todo** lo que `validate_config` considera estado de app, **excepto** las meta-claves:

- Excluir del blob: `app_preset`, `app_presets`.
- Incluir siempre: ASR (`language`, `model`, `device`, `compute_type`, `use_vad`, `buffer_trimming_sec`, `installed_languages`), audio (`audio_monitor`), latencia (`latency_mode`, `latency_profiles` + espejos derivados al validar), traducción (`translation_*`, `translator_model`, `second_line_mode`, profiles/preset decode), display (`captions_*`), apariencia (`always_on_top`, font/colores/padding/`text_align`), geometría overlay (`window_pos/width/height`) y Settings (`settings_window_*`).

Fuente al **Guardar / Guardar como**: estado vivo = config en memoria + geometría actual del overlay + geometría actual del diálogo Settings (si está abierto).

### Meta no recursiva

Al guardar un snapshot, **nunca** anidar `app_presets` dentro del blob. Al aplicar, se fusiona el blob sobre la config viva **conservando** el mapa `app_presets` intacto y actualizando solo `app_preset` al id elegido.

### Ids

- Slug: mismo criterio que presets TX (`[a-z0-9_-]`, minúsculas, no vacío).
- Colisión: rechazar si el id ya existe en **Guardar como** (salvo que se implemente confirmación de sobrescritura; en v1: error y pedir otro nombre).
- **Guardar** (sin “como”): sobrescribe el blob del `app_preset` activo; si `app_preset` es `null`, la acción está deshabilitada (obligar Guardar como…).

## Comportamiento

### UI (Settings)

Barra **encima** de las pestañas (visible desde cualquier tab):

1. Combo **Preset** — lista de ids en `app_presets` + entrada “(ninguno)” cuando `app_preset` es `null` o no hay presets.
2. **Guardar** — enabled solo si hay `app_preset` activo presente en el mapa; escribe snapshot vivo encima.
3. **Guardar como…** — diálogo de nombre → slug → crea entrada, la deja activa, aplica meta.
4. **Borrar** — enabled solo si hay activo; confirma; elimina del mapa. Tras borrar: `app_preset = null` (combo “(ninguno)”); **no** auto-aplicar otro preset.

Sin presets de fábrica. Sin renombrar en v1.

### Aplicar al instante

Al cambiar el combo a un id existente:

1. Construir config candidata = `validate_config({**snapshot, "app_presets": mapa_actual, "app_preset": id})`.
2. Persistencia inmediata en `config.json` (no esperar al botón Guardar del diálogo).
3. Aplicar a runtime con la misma clasificación que hoy en `open_settings`:
   - Keys ASR-restart → reiniciar pipeline.
   - Latencia / traducción → hot-swap.
   - UI/apariencia/display → `overlay.apply_config`.
   - Geometría overlay → restaurar pos/tamaño (clamp a pantallas).
   - Geometría Settings → mover/redimensionar el diálogo abierto.
4. Si `audio_monitor` del snapshot **no** está en la lista actual de monitores: conservar el monitor vivo actual, mostrar aviso no modal (o `QMessageBox` informativo), y seguir aplicando el resto.
5. Cambiar a “(ninguno)” **no** revierte config; solo pone `app_preset = null` y persiste meta (evita sorpresa de “deshacer”).

### Guardar (sobrescribir)

1. Requiere `app_preset` ∈ `app_presets`.
2. Sustituye `app_presets[id]` por snapshot vivo.
3. Persiste de inmediato.
4. No reinicia pipeline (solo escritura de biblioteca de presets).

### Guardar como…

1. Nombre → slug; validar no vacío / no colisión.
2. Inserta snapshot; `app_preset = slug`.
3. Persiste de inmediato.
4. Actualiza combo al nuevo id.

### Borrar

1. Confirmación (“¿Borrar el preset «id»?”).
2. Elimina entrada; `app_preset = null`.
3. Persiste; no altera el resto de la config viva.

### Relación con presets parciales

`latency_profiles` y `translation_profiles` viajan **dentro** del snapshot. Los selectores de la pestaña Traducciones / Latencia siguen funcionando igual; un preset general es una capa superior.

### Geometría

Siempre incluida. Al aplicar:

- Overlay: `window_pos/width/height` → `_restore_geometry` / clamp existente.
- Settings: `settings_window_*` → `apply_saved_geometry`.
- Si la posición queda fuera de pantallas → reclavar (comportamiento ya existente del overlay).

## Project Structure (tocar)

```
src/config.py              # app_preset(s), snapshot helpers, slug, CRUD
src/app.py                 # apply_app_preset / save paths + matriz restart
src/ui/settings.py         # barra de presets + wiring
src/ui/overlay.py          # solo si hace falta exponer geometría viva al snapshot
config.example.json
tests/test_config.py
tests/test_settings_ui.py
tests/test_app_presets.py  # nuevo: snapshot exclude meta, apply merge
docs/intent|specs/fase2.8-…
README.md                  # mención breve
tasks/plan.md, tasks/todo.md
```

## Commands

```bash
make test
make lint
make run
```

## Code Style

Helpers puros en `config.py` (como TX):

```python
APP_PRESET_META_KEYS = frozenset({"app_preset", "app_presets"})

def snapshot_app_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Copia validada sin meta de presets generales."""
    ...

def apply_app_preset(cfg: dict[str, Any], preset_id: str) -> dict[str, Any]:
    """Fusiona snapshot sobre cfg conservando app_presets; valida."""
    ...
```

- Deepcopy de profiles anidados.
- UI: textos en español; sin comentarios obvios.

## Testing Strategy

| Nivel | Qué |
|-------|-----|
| Unit | Snapshot excluye meta; apply conserva `app_presets`; slug/colisión |
| Unit | Guardar / Guardar como / Borrar mutan el mapa y `app_preset` |
| Unit | `validate_config` defaults `app_preset=null`, `app_presets={}` |
| UI (offscreen) | Combo lista ids; Guardar disabled sin activo; Guardar como añade |
| Manual | Crear dos presets con geometría distinta; cambiar combo → overlay/settings saltan; reiniciar app |
| Manual | Snapshot con monitor inexistente → aviso + resto aplicado |

## Boundaries

**Always:**
- Snapshot completo excepto `app_preset` / `app_presets`.
- Geometría siempre incluida.
- Aplicar al instante al cambiar combo; persistir meta al momento.
- Sin fábrica; solo usuario.
- Misma matriz ASR-restart vs hot-swap que Settings Guardar.

**Ask first:**
- Presets de fábrica empaquetados.
- Renombrar / export-import fichero.
- Indicador dirty tras retocar.
- Incluir/excluir geometría con toggle (decidido: siempre ON).

**Never:**
- Anidar `app_presets` dentro de un snapshot.
- Cloud.
- Borrar sin confirmación.
- Al elegir “(ninguno)”, revertir automáticamente al estado anterior.

## Success Criteria

1. Barra de presets generales en Settings (combo + Guardar + Guardar como… + Borrar).
2. Guardar como crea preset con **todas** las keys de estado (ver checklist de snapshot).
3. Cambiar combo aplica al instante (UI + geometría + pipeline según matriz).
4. Guardar sobrescribe el activo; Borrar pide confirmación y deja `(ninguno)`.
5. Tras reinicio, mapa + `app_preset` se restauran; aplicar de nuevo funciona.
6. `make test` / `make lint` verdes; README menciona presets generales.

## ASSUMPTIONS

1. Nombre de fase **2.8** (siguiente a 2.7 apariencia).
2. UI del combo muestra el **slug** (sin label display separado en v1).
3. “(ninguno)” no es un preset almacenado; es UI para `app_preset is null`.
4. Monitor ausente: conservar el actual + aviso; no abortar el apply completo.
5. Tras Borrar, no se aplica otro preset automáticamente.
6. Retocar knobs tras aplicar **no** limpia el combo en v1 (sin dirty); Guardar escribe el estado vivo encima del id activo.

---

**Siguiente:** PLAN/TASKS e implementación en rama `feat/presets-generales-app`.
