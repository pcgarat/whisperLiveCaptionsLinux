---
name: phase-workflow
description: Flujo intent→spec→plan→tasks→implement de whisperLiveCaptionsLinux. Usar al empezar features, cambiar alcance o antes de codear sin spec.
---

# Flujo de fases del proyecto

## Orden

1. **Intent** (`docs/intent/`) — qué y por qué (confirmado por el usuario).
2. **Spec** (`docs/specs/`) — requisitos testables; asunciones explícitas; Always/Ask/Never.
3. **Plan + tasks** (`tasks/plan.md`, `tasks/todo.md`) — slices verticales.
4. **Implement** — una task a la vez; verificar (tests/manual) antes de seguir.

No implementar features “porque encajan” si están fuera del spec vigente.

## Al cambiar alcance

1. Actualizar intent/spec (fecha de modificación).
2. Ajustar plan/todo.
3. Luego código.

## Fase 1 (recordatorio)

Éxito: EN manual, ~1–3 s, ≥30 min sin cuelgue, overlay usable, sin cloud.

Extensiones previstas (solo stubs/diseño hasta nuevo spec): traducción ES, `latency_mode=low`, más idiomas.
