Última modificación: 2026-09-13

# Intent: Fase 2.3 — Instalar idiomas desde Settings

Confirmado 2026-09-13 (simplificado: sin descargas ni %).

## Framing

- **2.2:** traducción EN→ES + `installed_languages` como lista de UI.
- **2.3:** ampliar `installed_languages` desde Settings con un catálogo fijo.

## Intent

- **Outcome:** En Settings, opción “Instalar nuevos idiomas” con lista + check + Instalar; al instalar, los códigos pasan a `installed_languages` y aparecen en el selector de Settings y en el menú del overlay.
- **User:** Solo el autor.
- **Success:** Marcar idiomas no instalados → Instalar → aparecen en ambos selectores; persisten en `config.json`.
- **Constraint:** Sin descarga de artefactos ni progreso; sin Marian; catálogo acotado a idiomas con mapa NLLB (traducción usable) + ASR Whisper.

## UI

1. Selector de idioma en Settings = combo de `installed_languages`.
2. Botón “Instalar nuevos idiomas…”.
3. Diálogo: checkboxes del catálogo aún no instalados; “Instalar seleccionados”.
4. Overlay: menú de idioma refleja `installed_languages` actualizado.

## Fuera de alcance

Descargas, %, desinstalar, auto-detect, target ≠ `es`.
