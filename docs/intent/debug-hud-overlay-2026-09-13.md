Última modificación: 2026-09-13

# Intent: HUD debug en overlay (VRAM + ASR)

## Qué

Chip discreto en el overlay, solo en modo debug, con:

- VRAM GPU usada/total (si hay NVIDIA/NVML)
- Latencia del último chunk ASR (`infer_ms`) y señales de cola (profundidad `CaptionUpdate` + duración del ring de audio)

## Por qué

Afinar `compute_type` / modelos y detectar si ASR se atrasa sin abrir `nvidia-smi` ni el JSON de trazas.

## Quién

Solo el autor en sesiones de diagnóstico (`make debug` o toggle en overlay).

## No es

Telemetría permanente en uso diario, panel de Settings, ni métricas de traducción (salvo que un spec futuro lo pida).
