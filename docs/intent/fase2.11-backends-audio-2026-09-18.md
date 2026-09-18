Última modificación: 2026-09-18

# Intent: Fase 2.11 — abstracción de backends de audio

**Estado:** confirmado (chat 2026-09-18).

## Qué

Separar «de dónde sale el audio» del resto de la app: un contrato `AudioBackend` con un
registro, y PipeWire/Pulse (`pactl` + `parec`) como única implementación por ahora.

## Por qué

La pregunta de partida fue si la app puede funcionar con cualquier sistema de audio y en
Windows. Del análisis salieron tres conclusiones:

1. **El acoplamiento es pequeño**: `SystemAudioCapture` se instancia en un sitio
   (`src/asr/pipeline.py`) y la lista de dispositivos se pide en dos (`app.py`,
   `src/ui/settings.py`). Hoy esos tres puntos saben que existe `parec` y que un
   dispositivo es un nombre Pulse acabado en `.monitor`.
2. **«Cualquier sistema de audio» en Linux rinde poco.** PipeWire y PulseAudio ya están
   cubiertos (vía `pipewire-pulse`). ALSA puro no tiene monitor de salida: capturar lo que
   suena exigiría que el usuario cargase `snd-aloop`. No compensa.
3. **Windows queda fuera por ahora**, por decisión explícita: no hay máquina Windows con
   NVIDIA donde verificarlo, y escribir soporte que no se puede probar contradice cómo
   trabajamos. Además el camino obvio falla: `sounddevice` no expone loopback WASAPI
   porque PortAudio lo tiene en `master` sin release; habría que ir a PyAudioWPatch, sumar
   la instalación de cuBLAS 12 + cuDNN 9 y rehacer el empaquetado.

Queda entonces la parte que mejora el código hoy y deja el hueco abierto: el contrato.

## Alcance acordado

- Sí: contrato + registro + backend Pulse/PipeWire, con etiquetas legibles como parte del
  backend (hoy viven en la UI, que es una fuga de capa).
- **No**: remuestreo ni mezcla a mono. `parec` ya entrega mono a 16 kHz; un remuestreador
  sin backend que lo use sería código muerto. Se escribirá con el primer backend que lo
  necesite.
- No: backend WASAPI, ALSA, JACK ni macOS. No: empaquetado para Windows.
