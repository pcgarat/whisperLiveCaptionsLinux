Última modificación: 2026-09-18

# Intent: Fase 2.10 — tipografía del overlay

**Estado:** confirmado (chat 2026-09-18).

## Qué

Selector de **tipo de letra** y de **peso** en Settings → Apariencia, aplicado al texto de
los subtítulos del overlay.

## Por qué

El overlay hereda la fuente por defecto de Qt (Cantarell/DejaVu según el escritorio) con
`font-weight: 600` fijo. Sobre vídeo, la legibilidad depende tanto de la familia como del
grosor del trazo: una humanista de palo seco con peso alto se lee sobre fondo claro donde
la fuente del sistema se pierde. Es el único knob visual del cartón que aún no se puede
tocar desde la UI, y ya estaba previsto como **Ask** en el spec de la fase 2.7.

## Decisiones del usuario

1. **Lista curada + resto de familias instaladas.** Arriba las tipografías legibles para
   subtítulos que estén instaladas; separador; después el resto de familias del sistema
   que sirvan para texto latino. Se descarta el `QFontComboBox` pelado: mete fuentes de
   símbolos y dingbats que en un subtítulo se ven como cajas.
2. **Sí a un selector de peso** (Normal / Seminegrita / Negrita), no solo familia.

## Fuera de alcance

Cursiva, interletraje, contorno/sombra del texto, fuentes distintas por línea
(traducción vs reconocimiento), empaquetar fuentes con la app.
