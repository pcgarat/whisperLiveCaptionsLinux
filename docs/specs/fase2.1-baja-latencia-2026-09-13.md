Última modificación: 2026-09-13

# Spec: Fase 2.1 — Modo baja latencia

**Estado:** aprobado e implementado (2026-09-13). Smoke manual confirmado por el usuario.  
**Intent:** `docs/intent/fase2.1-baja-latencia-2026-09-13.md`  
**Base:** Fase 1 aprobada — `docs/specs/fase1-subtitulos-directo-2026-09-13.md`

## Objective

Activar de verdad el flag reservado `latency_mode` (`stable` | `low`) y exponer en Settings controles para equilibrar **estabilidad vs latencia**, con presets por modo persistentes.

**Usuario:** solo el autor.

**Fase 2.1 (este spec):**
- Default sigue siendo `stable` (~1–3 s, texto más estable).
- Modo `low` apunta a retraso percibido típico **~0.5–1 s**, aceptando más parpadeo/reescritura.
- Settings: selector de modo, sliders de **confianza** y **latencia máxima**, tooltips, botón **Restablecer**.
- Valores por modo se cargan al cambiar de modo; overrides del usuario sobreviven reinicios.

**Fuera de 2.1:**
- Traducción / multi-idioma (fase **2.2**).
- Auto-detección de idioma.
- Modelo Whisper distinto por modo.
- Cloud / APIs.
- Reutilizar código de `live_translate_subtitles`.

## Tech Stack

Sin cambios de stack respecto a fase 1 (Python 3.12, PyQt6, faster-whisper, PipeWire).  
Sin dependencias nuevas pesadas.

## Semántica de los controles

| Control | Significado | Rango UI |
|---------|-------------|----------|
| `latency_mode` | Preset activo + carga sus knobs guardados | `stable` \| `low` |
| Confianza | `agreement_n`: cuántas hipótesis consecutivas deben acordar un prefijo antes de confirmar | entero **1–5** |
| Latencia máxima | Techo en segundos: si el texto provisional lleva demasiado sin confirmarse, se **fuerza un commit** del mejor prefijo disponible | **0.5–5.0** s, paso 0.1 |

**Tooltips (texto a mostrar):**
- **Confianza:** “Cuántas hipótesis consecutivas del ASR deben coincidir en un prefijo antes de confirmarlo. Más alto = más estable y más lento; más bajo = más rápido e inestable.”
- **Latencia máxima:** “Techo en segundos: si el subtítulo provisional no se confirma a tiempo, se fuerza un commit. Más bajo = menos retraso, más riesgo de confirmar texto prematuro.”

**Presets de fábrica:**

| Modo | `agreement_n` | `max_latency_sec` | `min_chunk_seconds` |
|------|---------------|-------------------|---------------------|
| `stable` | 2 | 3.0 | 0.8 |
| `low` | 1 | 1.0 | 0.35 |

`min_chunk_seconds` va **dentro del profile por modo** (opción A aprobada): no hay slider dedicado; cambia al cambiar de modo / Restablecer. El spinbox global de chunk de fase 1 se retira o se sustituye por este comportamiento de profile (evitar dos fuentes de verdad).

**Efectos adicionales del modo (no sliders):**
- `beam_size` del motor: `5` en `stable`, `1` en `low` (formalizar el esbozo del pipeline).
- Al aplicar settings que cambien modo/knobs de streaming: reiniciar el pipeline ASR (mismo patrón actual: guardar y reiniciar).

## Modelo de config (propuesta)

Evitar drift entre knobs “activos” y presets: **fuente de verdad = slots por modo** + modo activo.

```json
{
  "latency_mode": "stable",
  "latency_profiles": {
    "stable": {
      "agreement_n": 2,
      "max_latency_sec": 3.0,
      "min_chunk_seconds": 0.8
    },
    "low": {
      "agreement_n": 1,
      "max_latency_sec": 1.0,
      "min_chunk_seconds": 0.35
    }
  }
}
```

Reglas:
1. Al cargar config, los knobs efectivos son `latency_profiles[latency_mode]`.
2. Al cambiar el selector de modo en UI → rellenar sliders desde el slot de ese modo (y aplicar `min_chunk` del profile en runtime).
3. Al mover un slider → actualizar el slot del modo activo (en memoria; persistir al Guardar).
4. **Restablecer** → copiar presets de fábrica al slot del modo activo y refrescar sliders.
5. Migración desde config fase 1: si no hay `latency_profiles`, crear slots con fábrica; si existían `agreement_n` / `min_chunk_seconds` top-level, usarlos como valor inicial del modo activo y fábrica para el otro modo.
6. Tras migración, `agreement_n` / `min_chunk_seconds` top-level dejan de ser fuente de verdad (el pipeline lee el profile efectivo).

Constantes de fábrica en código (p. ej. `LATENCY_FACTORY_PRESETS`) para que Restablecer no dependa de lo que el usuario haya guardado.

## Comportamiento del streamer

Extender `LocalAgreementStreamer` (o el loop del pipeline) para soportar **force-commit por tiempo**:

- Llevar timestamp del último commit / del inicio del parcial pendiente.
- Si `time.monotonic() - t0 >= max_latency_sec` y hay hipótesis/parcial, forzar confirmación del mejor prefijo disponible (p. ej. la última hipótesis normalizada o el common-prefix parcial), emitiendo `is_final=True` cuando corresponda.
- Con `agreement_n == 1`, el acuerdo en una sola hipótesis ya acelera; la latencia máxima es red de seguridad cuando el ASR no estabiliza.

## Commands

Igual que fase 1:

```bash
source .venv/bin/activate
pytest -q
./scripts/run.sh
ruff check src tests
```

## Project Structure

Tocar sobre todo:

```
src/config.py              # profiles + migración + validación max_latency_sec
src/asr/streaming.py       # force-commit por max_latency (si aplica aquí)
src/asr/pipeline.py        # pasar max_latency + beam_size según modo
src/ui/settings.py         # modo, sliders, tooltips, Restablecer
config.example.json
tests/test_config.py
tests/test_streaming.py
docs/intent|specs/…        # este par de docs
tasks/plan.md, tasks/todo.md  # tras aprobar spec
```

## Code Style

- Misma convención fase 1: módulos pequeños; sin comentarios obvios.
- UI: no bloquear el event loop; cambios de latencia vía reinicio de pipeline, no mutación a medias desde el hilo UI.
- Textos de tooltip en español, cortos.

Ejemplo de API de presets:

```python
LATENCY_FACTORY_PRESETS: dict[str, dict[str, float | int]] = {
    "stable": {"agreement_n": 2, "max_latency_sec": 3.0, "min_chunk_seconds": 0.8},
    "low": {"agreement_n": 1, "max_latency_sec": 1.0, "min_chunk_seconds": 0.35},
}

def effective_latency_profile(cfg: dict) -> dict[str, float | int]:
    return cfg["latency_profiles"][cfg["latency_mode"]]
```

## Testing Strategy

| Nivel | Qué |
|-------|-----|
| Unit | Migración de config antigua → `latency_profiles`; clamp de rangos; Restablecer = fábrica del modo |
| Unit | Streamer: con `agreement_n=1` confirma antes; con techo de latencia fuerza commit aunque no haya acuerdo completo |
| Manual | `stable` sigue ~1–3 s usable; `low` se siente ~0.5–1 s en vídeo EN; overrides sobreviven reinicio; Restablecer vuelve al preset |
| No CI | Medición formal de latencia end-to-end con GPU |

## Boundaries

**Always:**
- Default `latency_mode=stable`.
- Persistencia **por modo** en `config.json`.
- Tooltips con la semántica acordada.
- Tests unitarios de config + force-commit en verde antes de cerrar la lógica.
- ASR/captura fuera del hilo UI.

**Ask first:**
- Cambiar los números de fábrica acordados.
- Añadir un slider visible para `min_chunk_seconds` (hoy solo via profile).
- Dependencias nuevas.

**Never:**
- Traducción / auto-detect en esta fase.
- Cloud.
- Romper el arranque con configs fase 1 existentes (migrar con defaults).

## Success Criteria

1. Settings muestra selector `stable`/`low`, sliders confianza + latencia máxima, tooltips, botón Restablecer.
2. Default al primer arranque / config nueva: `stable` con fábrica (2 / 3.0 s).
3. Cambiar de modo carga los valores guardados de ese modo; Restablecer restaura fábrica del modo activo.
4. Guardar + reiniciar pipeline aplica knobs; reiniciar la app conserva overrides por modo.
5. En `low` (fábrica), el subtítulo se percibe claramente más inmediato que en `stable` (objetivo ~0.5–1 s en uso normal con GPU).
6. En `stable`, comportamiento no empeora de forma notable respecto a fase 1.
7. `pytest -q` pasa sin GPU.
8. `config.example.json` y README/settings note reflejan los nuevos campos.

## Open Questions

Resueltas al aprobar el spec (2026-09-13):

1. `min_chunk_seconds` por modo → **opción A** (`stable=0.8`, `low=0.35`, sin slider extra).
2. Aplicar cambios → **mismo patrón actual** (guardar y reiniciar pipeline).
3. `beam_size` 5/`stable` vs 1/`low` → **formalizar**.

---

**Siguiente:** PLAN / TASKS en `tasks/plan.md` y `tasks/todo.md` (solo 2.1).
