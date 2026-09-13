Última modificación: 2026-09-13

# Intent: Fase 2.8 — Presets generales de aplicación

Confirmado en chat 2026-09-13 (fábrica `default` confirmada el mismo día).

## Problema

Los presets actuales son parciales (latencia por modo, decoding de traducción). No hay forma de recuperar de golpe una sesión completa: idioma, modelo, audio, latencia, traducción, apariencia, toggles del overlay y geometría de ventanas.

## Outcome

- Presets **generales de usuario** que hacen snapshot de **absolutamente toda** la config activa (todas las pestañas + estado vivo del overlay + posiciones/tamaños).
- Acciones: **Guardar** (sobrescribe el activo), **Guardar como…**, **Borrar**.
- Aplicar **al instante** al cambiar el selector (sin esperar al Guardar del diálogo).
- Un preset de fábrica **`default`**: snapshot de la configuración de referencia del producto; es el único preset en instalación nueva y queda **activo** al primer arranque.

## Usuario / éxito

- El autor puede guardar “Directo ES”, “Estudio EN”, etc., y volver a cualquiera en un clic.
- Tras reiniciar la app, los presets y el último activo siguen disponibles.
- Instalación limpia: solo `default`, ya seleccionado.

## Decisiones confirmadas

1. Geometría de overlay y Settings **siempre** dentro del preset.
2. Acciones: Guardar + Guardar como… + Borrar (no solo Guardar como).
3. Aplicación inmediata al cambiar el combo.
4. Fábrica: un solo preset `default` (contenido = config de referencia en `config.example.json`); activo en primer arranque. Audio/monitor y posiciones de ventana de fábrica van vacíos/`null` (no atar a hardware del autor). No se puede borrar.

## Fuera de alcance

- Renombrar presets.
- Export/import de ficheros sueltos.
- Más presets de fábrica empaquetados (solo `default`).
- Sincronización en la nube.
- Indicador “dirty” si se retoca tras aplicar (v1: opcional diferido).

## Siguiente paso

Spec → `docs/specs/fase2.8-presets-generales-app-2026-09-13.md`
