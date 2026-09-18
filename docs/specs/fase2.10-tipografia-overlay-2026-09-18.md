Última modificación: 2026-09-18

# Spec: Fase 2.10 — tipografía del overlay

**Estado:** aprobado (chat 2026-09-18).
**Intent:** `docs/intent/fase2.10-tipografia-overlay-2026-09-18.md`

## Objective

Elegir familia tipográfica y peso del texto de subtítulos desde Settings → Apariencia,
con hot-swap al Guardar (sin reiniciar ASR ni recargar modelos).

## Config

```json
"font_family": "",
"font_weight": "semibold"
```

- `font_family`: nombre de familia tal cual. `""` = fuente por defecto de Qt (comportamiento
  actual). **No** se valida contra las fuentes instaladas: una config puede viajar a otra
  máquina y Qt ya hace fallback solo. Normalización: recorte, colapso de espacios, máximo
  64 caracteres y borrado de `"` `'` `;` `{` `}` (el valor se interpola en QSS).
- `font_weight`: `normal` | `semibold` | `bold`. Ausente o inválido → `semibold`, que es el
  `font-weight: 600` que el overlay ya pinta hoy: las configs existentes no cambian de aspecto.
- Mapeo a CSS: `normal` → 400, `semibold` → 600, `bold` → 700. Qt 6 respeta los pesos
  numéricos, pero una familia con solo dos caras (Regular + Bold, p. ej. DejaVu Sans)
  resuelve 600 y 700 a la misma: el *hint* del selector lo advierte.
- Persistencia en `config.json` y en `result_config()`; entran solas en los snapshots de
  presets generales (son claves de config como el resto).

## Catálogo de fuentes (`src/ui/fonts.py`)

- `CAPTION_FONT_PRESETS`: familias curadas por legibilidad en subtítulos, en orden de
  preferencia (palo seco primero, luego condensadas y serif).
- `available_caption_fonts()` → `(curadas_instaladas, resto)`:
  - Fuente de verdad: `QFontDatabase.families(WritingSystem.Latin)`, que ya descarta
    fuentes de símbolos/emoji al exigir cobertura latina.
  - Se excluyen familias privadas (`isPrivateFamily`) y no escalables (bitmap).
  - Se recorta el sufijo de fundición (`Nimbus Sans [urw]`): ese nombre no resuelve como
    `font-family` en QSS y además duplica la misma familia una vez por fundición.
  - `resto` va sin las curadas y sin duplicados (comparación *case-insensitive*).
- `font_family_css()` / `font_weight_css()`: valores listos para interpolar en QSS.

## UI Settings → Apariencia

Dos filas nuevas en la sección «Texto y colores», antes de «Tamaño de texto»:

- **Tipo de letra** (combo `lg`): `Sistema (por defecto)` (dato `""`) → curadas instaladas →
  separador → resto de familias. Cada ítem se dibuja con su propia tipografía (`FontRole`),
  así el desplegable es su propia muestra.
- **Grosor** (combo `md`): Normal / Seminegrita / Negrita.

Reglas:

- Si `font_family` no está instalada, se añade como ítem `«X» (no instalada)` y queda
  seleccionada: guardar desde la UI no pierde el valor (mismo patrón que `translator_model`).
- La vista previa refleja familia y peso junto al resto de knobs visuales.
- `reload_from_config()` sincroniza ambos controles al aplicar un preset general.

## Overlay

`_apply_style()` aplica la **familia** a `translatedCaption`, `finalCaption` y
`partialCaption`, y el **peso** solo a las dos primeras: la línea parcial es
deliberadamente discreta (cursiva, con alfa) y engordarla anularía esa señal. El chrome
(idioma, botones, HUD de depuración) mantiene su tipografía.

## Always / Ask / Never

- **Always:** default `""` + `semibold` (aspecto idéntico al actual); normalización en
  `validate_config`; hot-swap al Guardar.
- **Ask:** cursiva, contorno/sombra, tipografías distintas por línea, empaquetar fuentes.
- **Never:** reiniciar el pipeline por un cambio de tipografía; escribir en `config.json` una
  familia que rompa el QSS.

## Verification

- Unit: `validate_config` (normalización y defaults), `result_config()` del diálogo,
  `available_caption_fonts()` (no cuela privadas ni duplicados), `apply_config` del overlay
  (la hoja de estilo lleva familia y peso).
- Manual: elegir una familia y un peso, Guardar, y ver el cartón cambiar sin cortes de audio
  ni recarga de modelos.
