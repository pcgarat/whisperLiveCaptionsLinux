Última modificación: 2026-09-13

# Intent: Empaquetado Linux — install de usuario + menú de aplicaciones

Confirmado en chat 2026-09-13.

## Problema

Hoy la app solo se arranca desde el repo (`make run` / `scripts/run.sh`). No hay entrada en el menú de aplicaciones de GNOME ni un install “de producto” que un usuario no técnico reconozca.

## Outcome

- **Fase A (ahora):** install de usuario en `~/.local` con lanzador, icono en el menú de aplicaciones y config en XDG. Se siente instalada, sin root.
- **Fase B (planificada):** paquete `.deb` repartible (GitHub Releases / apt local) con dependencias de sistema declaradas.

## Usuario / éxito

- Tras `make install-user`, la app aparece en Actividades / menú de aplicaciones con icono.
- Clic en el icono arranca overlay + Settings (mismo comportamiento que `make run`).
- Preferencias persisten entre reinicios aunque se lance desde el menú (no dependen del cwd del repo).
- `make uninstall-user` limpia lanzador, icono y copia instalada (sin borrar la config del usuario salvo flag explícito).

## Decisiones confirmadas

1. Empezar por **Fase A** (user-local); **Fase B** solo planificada en spec/plan.
2. **No** Flatpak / Snap / AppImage en esta fase (CUDA + PipeWire monitor).
3. Modelos Whisper/NLLB **no** van en el install; siguen en caché Hugging Face.
4. Config de runtime instalado → XDG (`~/.config/whisper-live-captions/`).
5. Modo desarrollo (`make run` en el repo) sigue funcionando; no obliga a instalar.

## Fuera de alcance (A y B)

- Tienda Snap/Flatpak.
- Firma de código / notarización.
- Auto-update.
- Bundlear CUDA ni drivers NVIDIA.
- Redistribuir modelos dentro del paquete.
- Branding comercial formal / marketing (sí hace falta un icono usable).

## Riesgo de licencia (recordatorio)

NLLB es CC-BY-NC-4.0. Un `.deb` “comercial” que lo use en runtime debe respetar NC; no es bloqueo de la Fase A (uso personal), sí de distribución comercial en B.

## Siguiente paso

Spec → `docs/specs/packaging-install-desktop-2026-09-13.md`
