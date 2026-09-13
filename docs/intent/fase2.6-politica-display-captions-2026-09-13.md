Última modificación: 2026-09-13

# Intent: Fase 2.6 — Política de display de captions

Confirmado en chat 2026-09-13.

## Framing

- Fase 1 fijó overlay = **parcial + confirmado**, con reescritura al corregir.
- El usuario quiere controlar eso desde Settings, con **dos toggles independientes**.

## Intent

- **Outcome:** En Settings, dos checkboxes con tooltip al hover:
  1. Mostrar (o no) el texto parcial / hipótesis en vivo.
  2. Permitir (o no) que el texto ya confirmado en el overlay se reescriba.
- **User:** Quiere subtítulos estables en pantalla; a veces solo definitivos y sin que lo escrito “parpadee” o se corrija in-place.
- **Why now:** El rewrite de confirmados y los parciales molestan al leer; no quiere un solo interruptor que mezcle semánticas.
- **Success:** Con ambos ON (default) el comportamiento es el actual; OFF en cada uno aplica solo esa política; hot-swap al Guardar sin reiniciar ASR.
- **Constraint:** 100 % local; no cambia LocalAgreement ni latencia ASR; al recortar buffer / nueva frase el overlay puede limpiar y empezar de cero.
- **Out of scope:** Cambiar `second_line_mode`, sticky TX, latency profiles.

## UI acordada

| Clave | Label | Default |
| --- | --- | --- |
| `captions_show_partials` | Mostrar texto parcial | `true` |
| `captions_allow_rewrite` | Permitir reescritura | `true` |

Tooltips explican ON vs OFF en cada control.

## Siguiente paso

Spec → `docs/specs/fase2.6-politica-display-captions-2026-09-13.md`
