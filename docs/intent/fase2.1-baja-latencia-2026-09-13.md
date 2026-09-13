Última modificación: 2026-09-13

# Intent: Fase 2.1 — Modo baja latencia

Confirmado en entrevista 2026-09-13.

## Framing de fases

- **2.1 (este intent):** modo baja latencia + controles en settings.
- **2.2 (después):** multi-idioma + traducción a español (fuera de alcance aquí).

## Intent

- **Outcome:** Poder elegir un modo `low` que reduzca el retraso percibido de los subtítulos, con presets por modo y sliders de confianza / latencia máxima (persistentes, con tooltips y restablecer).
- **User:** Solo el autor, viendo vídeo/navegador cuando el lag de `stable` molesta.
- **Why now:** La fase 1 ya da subtítulos EN estables (~1–3 s); el siguiente dolor es latencia, no aún traducción.
- **Success:** En `low`, retraso percibido típico ~0.5–1 s (más parpadeo OK); `stable` sigue siendo el default; ajustes por modo sobreviven reinicios.
- **Constraint:** 100 % local; ASR fuera del hilo UI; no degradar el default `stable` sin querer.
- **Out of scope (2.1):** Traducción / multi-idioma (2.2), auto-detección de idioma, cambiar modelo Whisper por modo, cloud/API, reutilizar `live_translate_subtitles`.

## Comportamiento UI acordado

1. Selector `stable` | `low` (default **`stable`**).
2. Al cambiar de modo → se cargan los valores **guardados de ese modo**.
3. Sliders: **confianza** (`agreement_n`) y **latencia máxima** (techo para forzar commit), con tooltips explicativos.
4. **Restablecer** → vuelve a los presets de fábrica del modo activo.
5. Cambios del usuario → se guardan en `config.json` y sobreviven reinicios **por modo**.

## Presets de fábrica acordados

| Modo | confianza (`agreement_n`) | latencia máxima | `min_chunk_seconds` (sin slider) |
|------|---------------------------|-----------------|----------------------------------|
| `stable` | 2 | 3.0 s | 0.8 |
| `low` | 1 | 1.0 s | 0.35 |

Asunciones aprobadas con el spec: profiles por modo + migración; `beam_size` 5/`stable` vs 1/`low`; `min_chunk` dentro del profile (opción A).

## Siguiente paso

`spec-driven-development` → `docs/specs/fase2.1-baja-latencia-2026-09-13.md`
