Última modificación: 2026-09-13

# Spec: HUD debug en overlay

**Estado:** aprobado (2026-09-13).  
**Intent:** `docs/intent/debug-hud-overlay-2026-09-13.md`

## Objective

Mostrar un chip de métricas en vivo en el overlay **solo en modo debug**, sin degradar el hot path ASR/UI.

## Requirements

1. El HUD es **visible** sii `debug_hud=true` **o** `WLCL_DEBUG_HUD` truthy **o** `WLCL_DEBUG_TRACE` truthy (`make debug`).
2. Chip en overlay: una línea discreta (no compite con captions). Formato orientativo:
   `ASR 180ms · q0 · buf2.1s · VRAM 3.1/8G`
   - `ASR`: `infer_ms` del último `transcribe` (o `…` si está ocupado).
   - `q`: `out_queue.qsize()` muestreado en el poll UI.
   - `buf`: duración del ring de audio (s).
   - `VRAM`: usada/total GPU vía NVML; si no hay NVIDIA → omitir o `VRAM n/a`.
3. Actualización HUD ≈ **1 Hz** (VRAM + repintado). Escritura de métricas ASR: tras cada infer, bajo lock barato (sin I/O).
4. **Never** spawn `nvidia-smi` en shell; **Never** leer VRAM en el hilo ASR.
5. Toggle en menú contextual del overlay: «HUD debug»; persiste `debug_hud` vía save config.
6. Default `debug_hud=false`. No usar `opt_perf_metrics` (sigue true de fábrica y no es modo debug).
7. Sin dependencia pip nueva (NVML por `ctypes` / `libnvidia-ml.so.1`).

## Always / Ask / Never

| Always | Ask | Never |
|--------|-----|-------|
| HUD apagado por defecto | Añadir más métricas (tx_lag vivo, RTF en chip) | Poll VRAM &lt; 500 ms; scrapear nvidia-smi; meter métricas en `CaptionUpdate` |

## Verify

- Unit: `debug_hud_enabled` env/config; snapshot métricas; VRAM mock/ctypes fail → n/a.
- Unit/UI: overlay oculta chip si off; muestra texto con snapshot si on.
- Manual: `make debug` → chip visible; cambiar float16/int8_float16 → VRAM coherente.
