Última modificación: 2026-09-13

# Intent: Fase 2.5 — Modos sticky de traducción

Confirmado en chat 2026-09-13.

## Framing

- **2.2–2.4:** NLLB, idiomas, presets de decoding (hechos).
- **2.5 (este intent):** reutilizar traducciones ya hechas y, opcionalmente, adelantar parciales.

## Intent

- **Outcome:** En Settings → Traducciones, un selector de modo sticky: apagado / solo confirmados / confirmados+parciales.
- **User:** Autor, afinando latencia percibida vs CPU sin re-traducir prefijos ya fijados.
- **Why now:** Cada rewrite del committed re-traduce todo; quiere congelar lo ya traducido y poder traducir parciales sin partir en palabras sueltas.
- **Success:** Con sticky OFF el pipeline se comporta como hoy; con `committed` no re-traduce checkpoints de origen ya enviados a NLLB; con `partials` además traduce la hipótesis (committed+partial) con la misma política sticky; decoding sigue siendo el del panel (preset/beam/etc.).
- **Constraint:** 100 % local; hot-swap sin reiniciar Whisper; no auto-detect de idioma.
- **Out of scope:** Alineación palabra a palabra EN↔ES, Marian, cloud, traducir tokens sueltos artificiales.

## UI acordada

Combo (un solo control, mutuamente excluyente):

| Valor | Label |
| --- | --- |
| `off` | Normal (como ahora) |
| `committed` | Sticky (solo confirmados) |
| `partials` | Sticky + parciales |

## Siguiente paso

Spec → `docs/specs/fase2.5-traduccion-sticky-modos-2026-09-13.md`
