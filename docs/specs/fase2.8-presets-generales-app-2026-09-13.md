Última modificación: 2026-09-13

# Spec: Fase 2.8 — Presets generales de aplicación

**Estado:** aprobado (decisiones confirmadas 2026-09-13; fábrica `default` 2026-09-13).  
**Intent:** `docs/intent/fase2.8-presets-generales-app-2026-09-13.md`  
**Base:** config unificada (`src/config.py`), Settings (`src/ui/settings.py`), apply path en `src/app.py`.

## Objective

Permitir guardar, aplicar al instante y borrar **presets generales de usuario** que restauran el estado completo de la app (pipeline + UI + geometría).

**Usuario:** solo el autor.

**Success de producto:** recuperar una sesión tipificada (idioma/modelo/audio/latencia/TX/apariencia/ventanas) en un clic, y persistir esos presets entre reinicios. Instalación nueva arranca con preset de fábrica `default` activo.

## Tech Stack

Sin dependencias nuevas. Reutilizar:

| Pieza | Uso |
|-------|-----|
| `config.json` + `validate_config` | almacén de presets + blob snapshot |
| `config.example.json` | defaults de primer arranque + snapshot fábrica `default` |
| PyQt6 Settings | barra de presets encima del `QTabWidget` |
| `AppController.open_settings` / hot-swap / restart | aplicar snapshot con la misma matriz ASR vs hot-swap |

## Modelo de datos

```json
{
  "app_preset": "default",
  "app_presets": {
    "default": { /* snapshot completo validate_config, sin meta */ }
  }
}
```

| Clave | Tipo | Default | Notas |
|-------|------|---------|-------|
| `app_preset` | `string \| null` | `default` (`APP_PRESET_DEFAULT`) | Id del último preset aplicado/guardado; `null` = ninguno |
| `app_presets` | `object` | `{ "default": <snapshot> }` | Mapa id → snapshot. Fábrica: solo `default` en install limpia |

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
- Id de fábrica: `default` (`APP_PRESET_DEFAULT`).

### Snapshot de fábrica (`default`)

Contenido = configuración de referencia del producto (misma que top-level en `config.example.json` / `_builtin_defaults`), con:

- `audio_monitor` vacío (no atar a un monitor del autor).
- `window_pos` / `settings_window_pos` = `null` (el WM coloca en primer uso).

En instalación nueva / `load_config` sin fichero: `app_preset=default` y `app_presets` solo con esa entrada.

## Comportamiento

### UI (Settings)

Barra **encima** de las pestañas (visible desde cualquier tab):

1. Combo **Preset** — lista de ids en `app_presets` + entrada “(ninguno)” cuando `app_preset` es `null` o no hay presets.
2. **Guardar** — enabled solo si hay `app_preset` activo presente en el mapa; escribe snapshot vivo encima.
3. **Guardar como…** — diálogo de nombre → slug → crea entrada, la deja activa, aplica meta.
4. **Borrar** — enabled solo si hay activo **y** no es `default`; confirma; elimina del mapa. Tras borrar: `app_preset = null` (combo “(ninguno)”); **no** auto-aplicar otro preset. El preset de fábrica `default` no se puede borrar (botón deshabilitado + `delete_app_preset` rechaza).

Sin renombrar en v1.

### Aplicar al instante

Al cambiar el combo a un id existente:

1. Construir config candidata = `validate_config({**snapshot, "app_presets": mapa_actual, "app_preset": id})`.
2. Persistencia inmediata en `config.json` (no esperar al botón Guardar del diálogo).
3. Aplicar al controller con la misma matriz ASR-restart / latency hot-swap / translation hot-swap que el Guardar de Settings.
4. Recargar controles del diálogo Settings desde la config aplicada.
5. Cambiar a “(ninguno)” **no** revierte config; solo pone `app_preset = null` y persiste meta (evita sorpresa de “deshacer”).

### Guardar

1. Requiere `app_preset` ∈ `app_presets`.
2. Sustituye `app_presets[id]` por snapshot vivo.

### Guardar como…

1. Nombre → slug; rechazar vacío / colisión.
2. Inserta snapshot; `app_preset = slug`.

### Borrar

1. Confirmación.
2. Elimina entrada; `app_preset = null`.

## Relación con presets parciales

`latency_profiles` y `translation_profiles` viajan **dentro** del snapshot. Los selectores de la pestaña Traducciones / Latencia siguen funcionando igual; un preset general es una capa superior.

## Archivos

```
src/config.py              # app_preset(s), snapshot helpers, slug, CRUD, APP_PRESET_DEFAULT
src/app.py                 # apply_app_preset / save paths + matriz restart
src/ui/settings.py         # barra Preset general
config.example.json        # defaults + único preset fábrica `default`
tests/test_app_presets.py  # snapshot exclude meta, apply merge, defaults fábrica
```

## Pseudocódigo (núcleo)

```python
APP_PRESET_DEFAULT = "default"
APP_PRESET_META_KEYS = frozenset({"app_preset", "app_presets"})

def apply_app_preset(cfg: dict[str, Any], preset_id: str) -> dict[str, Any]:
    """Fusiona snapshot sobre cfg conservando app_presets; valida."""
```

## Tests

| Tipo | Caso |
|------|------|
| Unit | Snapshot excluye meta; apply conserva `app_presets`; slug/colisión |
| Unit | Guardar / Guardar como / Borrar mutan el mapa y `app_preset` |
| Unit | `validate_config({})` → `app_preset=default`, `app_presets` solo `{default}` |
| UI (offscreen) | Combo lista ids; Guardar disabled sin activo; Guardar como añade |
| Manual | Crear dos presets con geometría distinta; cambiar combo → overlay/settings saltan; reiniciar app |
| Manual | Snapshot con monitor inexistente → aviso + resto aplicado |
| Manual | Install limpia: solo `default` activo |

## Boundaries

**Always:**
- Snapshot completo excepto `app_preset` / `app_presets`.
- Geometría siempre incluida.
- Aplicar al instante al cambiar combo; persistir meta al momento.
- Install limpia: único preset `default`, activo.
- El preset de fábrica `default` no se puede borrar.
- Fábrica no incluye `audio_monitor` ni posiciones de ventana del autor.
- Misma matriz ASR-restart vs hot-swap que Settings Guardar.

**Ask first:**
- Más presets de fábrica además de `default`.
- Renombrar / export-import fichero.
- Indicador dirty tras retocar.
- Incluir/excluir geometría con toggle (decidido: siempre ON).

**Never:**
- Anidar `app_presets` dentro de un snapshot.
- Cloud.
- Borrar sin confirmación.
- Al elegir “(ninguno)”, revertir automáticamente al estado anterior.
- Embarcar monitores Bluetooth / rutas de audio del autor en `config.example.json`.

## Success Criteria

1. Barra de presets generales en Settings (combo + Guardar + Guardar como… + Borrar).
2. Guardar como crea preset con **todas** las keys de estado (ver checklist de snapshot).
3. Cambiar combo aplica al instante (UI + geometría + pipeline según matriz).
4. Guardar sobrescribe el activo; Borrar pide confirmación y deja `(ninguno)`.
5. Tras reinicio, mapa + `app_preset` se restauran; aplicar de nuevo funciona.
6. Primer arranque / config ausente: `app_preset=default` y mapa solo con `default`.
7. `make test` / `make lint` verdes; README menciona presets generales y fábrica `default`.

## ASSUMPTIONS

1. Nombre de fase **2.8** (siguiente a 2.7 apariencia).
2. UI del combo muestra el **slug** (sin label display separado en v1) → se ve `default`.
3. “(ninguno)” no es un preset almacenado; es UI para `app_preset is null`.
4. Monitor ausente: conservar el actual + aviso; no abortar el apply completo.
5. Tras Borrar, no se aplica otro preset automáticamente.
6. Retocar knobs tras aplicar **no** limpia el combo en v1 (sin dirty); Guardar escribe el estado vivo encima del id activo.
7. Migración de installs ya existentes: **no** se reescribe `config.json` del usuario; solo afecta installs nuevas / sin fichero.

---

**Siguiente:** PLAN/TASKS e implementación en rama `feat/presets-generales-app`.
