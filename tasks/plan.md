# Plan: Empaquetado Linux — Fase A (+ B planificada)

Spec: `docs/specs/packaging-install-desktop-2026-09-13.md`  
Intent: `docs/intent/packaging-install-desktop-2026-09-13.md`  
Rama: `feat/packaging-fase-a-install-desktop`

## Enfoque

1. **Paths XDG** en config/app (testeable sin install real).
2. **Assets** `packaging/` (desktop template, icono SVG, script install).
3. **Make** `install-user` / `uninstall-user` + wrapper.
4. **README** + smoke manual.
5. **Fase B:** solo documentada en spec (no código en esta rama).

## Orden de slices

Paths/config → packaging assets + scripts → Make targets → README/tests finales.

## Crítica / mejoras conscientes

- Copiar a `~/.local/share/...` es más “producto” que apuntar el `.desktop` al clone; cuesta más disco (venv duplicado) pero desacopla del sitio del repo.
- Alternativa rechazada en A: symlink al repo (frágil si mueves el clone).
- En B, reutilizar el mismo `WLCL_*` evita dos modos de config.
