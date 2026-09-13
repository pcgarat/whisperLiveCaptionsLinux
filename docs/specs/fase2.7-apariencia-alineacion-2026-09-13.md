Última modificación: 2026-09-13

# Spec: Fase 2.7 — Pestaña Apariencia + alineación de texto

**Estado:** aprobado (pedido chat 2026-09-13).  
**Intent:** `docs/intent/fase2.7-apariencia-alineacion-2026-09-13.md`

## Objective

Mover controles de aspecto a pestaña propia y añadir alineación horizontal del texto del overlay (`center` | `left`). Hot-swap al Guardar (sin reinicio ASR).

## Config

```json
"text_align": "center"
```

- Valores: `center` | `left`. Ausente o inválido → `center`.
- Persistencia en `config.json` / `result_config()`.

## UI Settings

Pestañas: **General** | **Apariencia** | **Traducciones**.

- General: Captura, Latencia, Subtítulos (sin Apariencia ni vista previa).
- Apariencia: vista previa + tamaño, padding, colores, transparencia, **Alineación** (Centro / Izquierda).
- La vista previa refleja alineación y el resto de knobs visuales.

## Overlay

Aplica `text_align` a `translated_label`, `final_label`, `partial_label` y `notice_label` (misma alineación horizontal). Controles del chrome (idioma, botones) no cambian.

## Always / Ask / Never

- **Always:** default centro; clamp/normalización en `validate_config`.
- **Ask:** añadir `right` u otras tipografías.
- **Never:** reiniciar pipeline por cambio de apariencia.

## Verification

- Unit: validate + settings `result_config` + overlay `apply_config`.
- Manual: cambiar Centro↔Izquierda y ver overlay al Guardar.
