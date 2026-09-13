Última modificación: 2026-09-13

# Spec: Fase 2.3 — Instalar idiomas desde Settings

**Estado:** aprobado (2026-09-13), alcance simplificado.  
**Intent:** `docs/intent/fase2.3-instalar-idiomas-2026-09-13.md`  
**Base:** Fase 2.2 (`docs/specs/fase2.2-traduccion-en-es-2026-09-13.md`)

## Objective

Permitir ampliar `installed_languages` desde Settings eligiendo idiomas de un catálogo fijo, sin descargas ni progreso. Los idiomas instalados aparecen en el selector de Settings y en el menú del overlay.

## Commands

```bash
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
ruff check src tests
```

## Project Structure

```
src/asr/languages.py     # catálogo AVAILABLE_LANGUAGES + helpers
src/ui/settings.py       # combo idioma + diálogo instalar
src/ui/overlay.py        # menú ya usa installed_languages (sin cambio de contrato)
tests/test_languages.py  # catálogo / merge
docs/intent|specs/fase2.3-...
tasks/plan.md, tasks/todo.md
```

## Comportamiento

### Catálogo
- Fuente de verdad: `AVAILABLE_LANGUAGES` (código → nombre legible).
- Debe coincidir con las claves de `NLLB_LANG_CODES` (misma puerta de traducción).
- Defaults de config siguen siendo `installed_languages=["en","es"]`.

### Settings
- Combo de idioma: solo `installed_languages` (etiqueta `Nombre (code)`).
- Botón “Instalar nuevos idiomas…” abre diálogo modal.
- Diálogo: filas con checkbox por idioma del catálogo **no** instalado; botón “Instalar seleccionados”.
- Al instalar: se añaden a `installed_languages` (orden: existentes + nuevos en orden de catálogo); se refresca el combo; no hace falta Guardar para verlos en el combo del diálogo abierto (sí persisten al Guardar Settings como el resto).
- Si no queda ninguno pendiente: mensaje informativo, sin checks.

### Overlay
- El menú de idioma lista `installed_languages` (ya existente). Tras Guardar Settings (o si se propaga config), el menú muestra los nuevos códigos.

### Persistencia
- `installed_languages` en `config.json` vía flujo Guardar de Settings (igual que hoy).
- El diálogo de instalar solo muta el estado del SettingsDialog hasta Guardar; o bien actualiza `_config` interno para que `result_config()` lo incluya.

## Testing

- Unit: merge de idiomas, catálogo no vacío, códigos alineados con NLLB.
- Manual: instalar `fr` → aparece en combo Settings y en overlay tras Guardar.

## Boundaries

**Always**
- Sin descarga ni % fingidos.
- Persistencia solo vía `installed_languages`.
- Tests unitarios del catálogo/merge.

**Ask first**
- Ampliar catálogo más allá del mapa NLLB.
- UI de desinstalar idiomas.

**Never**
- Marian por par de idiomas.
- Auto-detect.
- Bloquear UI con I/O de red en este flujo.

## Success criteria

1. Settings muestra combo de instalados + “Instalar nuevos idiomas…”.
2. Instalar seleccionados añade códigos y refresca el combo.
3. Tras Guardar, overlay menú incluye los nuevos.
4. `pytest -q` verde.
5. README menciona el flujo en una línea.
