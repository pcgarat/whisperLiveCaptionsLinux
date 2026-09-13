Última modificación: 2026-09-13

# Intent: subtítulos en directo (Linux, local)

Confirmado en entrevista 2026-09-13.

## Intent

- **Outcome:** App Linux nueva de subtítulos en directo sobre el audio del sistema, overlay flotante, 100 % local.
- **User:** Solo el autor, viendo vídeo/navegador; meta futura: varios idiomas → español.
- **Why now:** El proyecto anterior (`live_translate_subtitles`) se cuelga; se quiere motor nuevo y estable, sin reutilizar ese código.
- **Success (fase 1):** Vídeo en inglés, idioma `en` elegido a mano, subtítulos estables con ~1–3 s de retraso, capítulo entero sin cuelgues ni cloud.
- **Constraint:** Calidad/estabilidad primero; arquitectura preparada para un modo baja-latencia y, después, multi-idioma + traducción a ES (sin auto-detección de idioma).
- **Out of scope (fase 1):** Reutilizar lógica/backend del proyecto viejo (solo referencia visual del overlay), traducción, auto-detección de idioma, diarización, multi-usuario, cloud/API, extensión de navegador, TensorRT.

## Notas de producto

- Idioma fuente: lo especifica el usuario (nunca auto-detect en el diseño previsto).
- Fase 1: solo inglés, sin traducción.
- Fases posteriores: varios idiomas + traducción a español.
- UI: ventana flotante siempre encima, semitransparente, arrastrable, configurable (tamaño/color/opacidad); captura vía monitor PipeWire del sistema.
- Uso concurrente típico: navegador o reproductor de vídeo (no juegos AAA).
- Preferencia de latencia: por defecto algo de retraso a cambio de texto estable; dejar abierta la opción de un modo más agresivo/bajo latencia más adelante.
- Backend candidato de referencia: WhisperLive (`faster_whisper`); no anclar el intent a un repo concreto hasta el spec.

## Siguiente paso

`spec-driven-development` → requisitos y criterios de aceptación de la fase 1.
