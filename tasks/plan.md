# Implementation Plan: Fase 2.3 — Instalar idiomas

## Overview

Catálogo fijo de idiomas + diálogo en Settings para añadirlos a `installed_languages`. Sin descargas ni progreso. Selectores Settings/overlay consumen esa lista.

**Spec:** `docs/specs/fase2.3-instalar-idiomas-2026-09-13.md`  
**Intent:** `docs/intent/fase2.3-instalar-idiomas-2026-09-13.md`

## Architecture Decisions

- **Catálogo en `src/asr/languages.py`:** desacopla UI de NLLB; `NLLB_LANG_CODES` se alinea con las mismas claves.
- **Sin worker/descarga:** instalar = merge de listas en memoria.
- **Settings posee el estado:** el diálogo muta `installed_languages` del SettingsDialog; Guardar persiste.
- **Overlay sin API nueva:** ya lee `installed_languages` en el menú.

## Dependency Graph

```
languages catalog
    │
    ├── Settings combo + InstallLanguagesDialog
    │
    └── (indirect) Overlay lang menu via installed_languages
```

## Tasks

1. Catálogo + helpers + alinear NLLB + tests
2. Settings: combo + diálogo instalar + README/todo
