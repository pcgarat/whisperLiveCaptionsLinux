Última modificación: 2026-09-13

# Intent — Fase 2.9: presets de vídeo por idioma y modelos preinstalados

## Problema

Hoy la app arranca con `small` + NLLB-600M y un único preset general (`default`).
Para el caso de uso real —subtitular vídeos de internet y leerlos en español— eso
obliga a tocar cinco o seis ajustes cada vez que cambia el idioma del vídeo, y los
modelos por defecto no son los mejores que aguanta esta máquina.

Además, la primera vez que se elige un modelo o un traductor nuevo hay una descarga
de 1–3 GB en caliente: la app parece colgada mientras baja pesos.

## Qué queremos

1. **Un preset por idioma de origen** listo para usar, pensado para vídeo de internet,
   que deje los subtítulos en español sin configurar nada más.
2. **Los mejores modelos que caben en esta máquina** (RTX 4060, 8 GB de VRAM) como
   valores de esos presets, elegidos con mediciones propias y no por intuición.
3. **Modelos ya descargados al instalar la app**, para que el primer arranque de
   cualquier preset no dispare una descarga larga.

## Por qué ahora

La fase 2.8 dejó el mecanismo de presets generales (snapshot de toda la config) ya
funcionando. Falta poblarlo: el mecanismo existe pero solo hay un preset.

## Restricciones heredadas

- Arquitectura B in-process, `faster-whisper` + CTranslate2 en CUDA, PyQt6.
- El idioma lo elige el usuario: **sin auto-detect**.
- Sin dependencias pesadas nuevas (`torch`, `transformers`).
- 100 % local, sin cloud.

Esta restricción se dio por incumplible para los modelos Marian/Opus-MT y no lo era:
CTranslate2 trae `OpusMTConverter`, que convierte desde el ZIP original con numpy y
pyyaml. El único añadido es `sentencepiece` (2,9 MB). La spec lo documenta.

## Fuera de alcance

- Traducción a idiomas distintos del español.
- Auto-detección del idioma del vídeo.
- Descarga de modelos bajo demanda desde la UI con barra de progreso.
- Cambiar la política de streaming (LocalAgreement) o los perfiles de latencia
  que el usuario ya tiene ajustados.

## Criterio de éxito

- Elegir el preset del idioma del vídeo y ver subtítulos en español, sin más pasos.
- Mejor calidad de reconocimiento y traducción que los valores anteriores,
  demostrada con números medidos en esta GPU.
- Whisper + traductor caben juntos en la VRAM con el escritorio y el navegador
  reproduciendo vídeo.
- Tras `make install-user`, ningún preset de fábrica necesita descargar pesos.
