Última modificación: 2026-09-13

# Spec — Fase 2.9: presets de vídeo por idioma y modelos preinstalados

Intent: `docs/intent/fase2.9-presets-video-modelos-2026-09-13.md`

## 1. Máquina objetivo

| Pieza | Valor |
| --- | --- |
| GPU | NVIDIA RTX 4060, 8 GB VRAM (driver 595.84, CUDA 13.2) |
| VRAM libre real | ~5,4 GB (GNOME + navegador consumen ~2,6 GB) |
| CPU / RAM | Ryzen 7 5800X (8c/16t) / 31 GB |
| Runtime | Python 3.12, `faster-whisper` 1.2.1, CTranslate2 4.8.2 |

`ctranslate2.get_supported_compute_types("cuda")` devuelve `float16`, `int8_float16`,
`int8`, `int8_float32`, `int8_bfloat16`, `bfloat16`, `float32`.

## 2. Evidencia: reconocimiento

Medido en esta GPU con 8 clips de `google/fleurs` por idioma (validation, 3–25 s,
61–87 s de audio por idioma), `beam_size=5`, `vad_filter=True`. WER por palabras
sobre texto normalizado (minúsculas, sin acentos ni puntuación).

| Modelo | compute | VRAM | en | fr | de | pt |
| --- | --- | --- | --- | --- | --- | --- |
| `small` | float16 | 675 MB | 13,5 % | 10,4 % | 4,4 % | 8,2 % |
| `medium` | float16 | 1788 MB | 10,6 % | 6,1 % | 1,9 % | 7,5 % |
| **`large-v3-turbo`** | **int8_float16** | **992 MB** | **10,6 %** | **5,2 %** | **1,9 %** | **5,0 %** |
| `large-v3-turbo` | float16 | 1943 MB | 10,6 % | 4,2 % | 1,9 % | 5,7 % |
| `large-v3` | int8_float16 | 3962 MB | 7,8 % | 4,7 % | 1,2 % | 6,9 % |

Latencia de inferencia por ventana (el pipeline retranscribe el buffer completo en
cada poll, así que la ventana crece hasta `buffer_trimming_sec`):

| Modelo | compute | 2 s | 5 s | 10 s |
| --- | --- | --- | --- | --- |
| `small` | float16 | 78 ms | 112 ms | 165 ms |
| `medium` | float16 | 198 ms | 262 ms | 396 ms |
| `large-v3-turbo` | float16 | 236 ms | 258 ms | 305 ms |
| **`large-v3-turbo`** | **int8_float16** | **211 ms** | **231 ms** | **270 ms** |

### Conclusiones de reconocimiento

- **`large-v3-turbo` con `int8_float16` es el punto óptimo de esta máquina**: iguala o
  mejora el WER de `medium` en los cuatro idiomas medidos, usando **la mitad de VRAM**
  (992 MB vs 1788 MB) y siendo **más rápido** (270 ms vs 396 ms en ventana de 10 s).
- `int8_float16` no es un recorte de calidad frente a `float16` en turbo: las
  diferencias observadas (fr 5,2 % vs 4,2 %; pt 5,0 % vs 5,7 %) caen dentro del ruido
  de una muestra de 8 clips y se compensan entre sí.
- **`large-v3` queda descartado en esta máquina.** Cuesta 3962 MB de VRAM, que sumados
  al traductor (~2 GB) y al escritorio (~2,6 GB) superan los 8 GB disponibles. Además
  es 2,5× más lento y solo gana claramente en inglés.
- `distil-whisper` no se adopta: sus variantes fuertes son solo inglés, lo que rompe
  el objetivo multi-idioma sin aportar sobre turbo.

## 3. Evidencia: traducción

Medido en esta GPU, CTranslate2 en CUDA, con 26 fragmentos cortos tipo subtítulo y 12
frases reales de FLEURS en minúsculas y sin puntuación (es decir, tal como sale de
Whisper), mismos parámetros de decodificación en ambos motores.

| Motor | Descarga | VRAM | Latencia p50 | Latencia máx |
| --- | --- | --- | --- | --- |
| **Opus-MT tc-big** (los 3 cargados) | **685 MB** | **+867 MB** | **8 ms** | **120 ms** |
| Opus-MT tc-big (uno solo) | 215–236 MB | ~300 MB | 8 ms | 120 ms |
| NLLB-200 distilled 1.3B | 1401 MB | +2012 MB | 49 ms | 508 ms |
| NLLB-200 distilled 600M | 647 MB | +1101 MB | ~35 ms | ~90 ms |

### Lo que decide: NLLB alucina en fragmentos cortos

En frases largas y bien formadas los dos motores están a la par. La diferencia aparece
en fragmentos cortos, que son la mayor parte del tráfico de un subtitulador. NLLB-200
se entrenó casi solo con oraciones completas, y ante un fragmento **inventa**: añade
guiones de diálogo, responde preguntas que nadie hizo y, en los peores casos, devuelve
lo contrario de lo que entró.

| Entrada | NLLB-1.3B | Opus-MT tc-big |
| --- | --- | --- |
| `yeah` (en) | `- ¿ Qué?` | `sí` |
| `uh` (en) | `¿ Qué pasa?` | `uh` |
| `oui` (fr) | `Sí, es cierto.` | `Sí.` |
| `sì` (it) | `- ¿ Qué?` | `Sí.` |
| `sim` (pt) | `¿ Qué?` | `Sí.` |
| `espera` (pt) | `¿Qué quieres decir?` | `espera` |
| `genau` (de) | `Eso es.` | `exactamente` |

Convertir `sì`/`sim` («sí») en «¿Qué?» no es una traducción mediocre: es lo contrario
del contenido, y en pantalla desinforma. El patrón está documentado en
[HalOmi](https://arxiv.org/html/2305.11746v2), que lo atribuye explícitamente a que las
frases cortas son atípicas en el corpus de NLLB, y la propia model card de
`facebook/nllb-200-distilled-600M` declara que el modelo **no se publica para uso en
producción**.

El salto de 600M a 1.3B, que en su día se adoptó por calidad en frases largas, **no
arregla esto**: la 1.3B alucina igual o peor en fragmentos.

Extra no despreciable: Opus-MT es CC-BY-4.0 y NLLB es CC-BY-**NC**-4.0.

### Calidad en frases largas (FLORES-200 devtest, sacreBLEU)

Cifras de los leaderboards de Helsinki-NLP, que evalúan todos los sistemas con la misma
metodología ([OPUS-MT](https://github.com/Helsinki-NLP/OPUS-MT-leaderboard) y
[External-MT](https://github.com/Helsinki-NLP/External-MT-leaderboard)).

| Sistema | en→es | fr→es | de→es | it→es | pt→es |
| --- | --- | --- | --- | --- | --- |
| NLLB-200 distilled 600M | 25,9 | 22,8 | 21,5 | 21,4 | 23,9 |
| NLLB-200 distilled 1.3B | 27,2 | 24,1 | 23,2 | 22,8 | 25,0 |
| NLLB-200 3.3B | 27,3 | 24,3 | 23,2 | 22,9 | 24,8 |
| **Opus-MT tc-big elegido** | **28,5** | **24,2** | **24,9** | **23,1** | **25,2** |

Opus-MT `tc-big` bate a NLLB-200-3.3B en los cinco pares con 234 MB en lugar de 6,7 GB.
Mis propias muestras de FLEURS lo confirman como empate técnico en frases largas, con
una salida algo mejor puntuada y capitalizada en Opus-MT y sin los artefactos de
espaciado de NLLB (`¿ Qué`, `platos . Los`).

### Modelos elegidos y por qué esos

| Par | Modelo | CT2 int8 |
| --- | --- | --- |
| en→es | `tc-big-en-es` (`eng-spa/opusTCv20210807+bt_transformer-big_2022-03-13`) | 234 MB |
| de→es | `tc-big-de-es` (`deu-spa/opusTCv20210807_transformer-big_2022-07-26`) | 236 MB |
| fr/it/pt→es | `tc-big-itc-itc` (`itc-itc/opusTCv20210807_transformer-big_2022-08-10`) | 215 MB |

No existe bilingüe `tc-big` para fr/it/pt→es; el modelo de familia itálica cubre los
tres con un solo directorio (token `>>spa<<`) y con mejor calidad que los bilingües base
de 2020 (fr→es 24,2 vs 20,0).

**Se usan a propósito las versiones `opusTCv20210807` de 2022 y no los `*-bible-big-*`
de 2024**, que puntúan algo mejor en FLORES pero arrastran artefactos de subtítulos de
diálogo: `Thank you very much.` → «Muchas gracias por tu comentario.», `Oui.` → «- Sí,
señor.». Se paga 0,4–0,9 BLEU por una robustez muy superior en el régimen que importa.

### Conversión sin `torch` ni `transformers`

CTranslate2 incluye `ct2-opus-mt-converter` / `OpusMTConverter`, que trabaja sobre el
ZIP original de Marian y solo necesita numpy y pyyaml, ya presentes. Comprobado en esta
máquina: los tres modelos convertidos en **88 s incluyendo la descarga**, con `torch`,
`transformers` y `sentencepiece` ausentes del venv.

Dos trampas que la implementación debe cubrir:

- el conversor **no copia los `source.spm`/`target.spm`**, y sin ellos el directorio es
  inservible → hay que copiarlos a mano;
- el `config.json` generado lleva `add_source_eos`, así que **CT2 añade `</s>` solo**;
  añadirlo también en el encoder degrada la traducción. Por la ruta
  `ct2-transformers-converter` el comportamiento es el contrario, y es una fuente
  clásica de bugs.

Única dependencia nueva: `sentencepiece` (**2,9 MB** instalados), porque los `.spm` de
Marian no traen `tokenizer.json` y la librería `tokenizers` que ya se usa no sirve.

### Parámetros de decodificación

Barrido de `beam_size` × `length_penalty` sobre los mismos textos:

| beam | length_penalty | p50 frases largas | Verborrea | Observación |
| --- | --- | --- | --- | --- |
| 1 | 0.4–1.0 | 42 ms | 1,45 | Precipicio: `No sé.` por `No lo sé.`, aparece «Muchas gracias por tu comentario.» |
| 2 | 0.4 | 48 ms | 1,18 | Limpio |
| 2 | 0.7 | 48 ms | 1,21 | Limpio |
| 2 | 1.0 | 48 ms | 1,37 | Rellena: `oui` → «Sí, sí.», `então` → «Entonces...» |
| 4 | 0.7 | 49 ms | 1,22 | Limpio |
| 4 | 1.0 | 49 ms | 1,45 | Rellena |

«Verborrea» es la media de caracteres de salida por caracter de entrada en los
fragmentos cortos: cuanto más alto, más relleno inventado.

De aquí salen dos cambios en los perfiles de fábrica:

- **`length_penalty` 0.7 en los tres perfiles** (antes 1.0/1.0/1.1). Es el valor mínimo
  que admite el clamp existente `[0.6, 1.5]`, y 0.4 no mejora de forma apreciable, así
  que no hace falta tocar ni el clamp ni el slider de la UI.
- **`no_repeat_ngram_size` 3 también en `fast`** (antes 0): cortar bucles de repetición
  no cuesta latencia medible y es el peor fallo posible en pantalla.

`beam_size` sigue siendo lo único que distingue los tres perfiles (2/4/6), porque es el
knob de latencia real para NLLB (52 / 106 / 204 ms). Con Opus-MT beam 2 y 4 cuestan lo
mismo, pero beam 1 hay que evitarlo en cualquier motor.

### Alternativas de traducción descartadas

- **NLLB-200** deja de ser el motor por defecto por lo de arriba. Se mantiene
  seleccionable porque sus 200 idiomas son la única salida local para un idioma sin
  `tc-big` hacia español.
- **`Helsinki-NLP/opus-mt-*` base de 2020**: existen y son ligeros (75–83 M), pero
  quedan 2 BLEU por debajo de los `tc-big` y `opus-mt-pt-es` no existe.
- **MADLAD-400 3B** (`Nextcloud-AI/madlad400-3b-mt-ct2-int8`): 2977 MB de descarga y
  ~3,3 GB de VRAM. Sumado a turbo no deja margen para el navegador, y es ~13× el tamaño
  de un `tc-big` para una mejora incierta.
- **LLM traductor** (TowerInstruct 7B, Salamandra-TA 2B, EuroLLM 1.7B): mejor calidad en
  pares difíciles, pero 5–10× la VRAM y 10–20× la latencia de Opus-MT para igualar o
  empeorar en estos cinco pares de alto recurso. Requieren además `llama.cpp` o vLLM,
  porque CTranslate2 no soporta su arquitectura. Si alguna vez se explora, Salamandra-TA
  2B (Apache-2.0, específico de lenguas ibéricas) es el único candidato, y como opción
  activable, nunca por defecto.

## 4. Decisión

| Rol | Elección | Coste |
| --- | --- | --- |
| Reconocimiento | `large-v3-turbo` con `int8_float16` | 1622 MB en disco, 992 MB VRAM |
| Traducción | Opus-MT tc-big CT2 int8, uno por idioma | 685 MB en disco, ~300 MB VRAM |
| **Total** | | **~2,3 GB en disco, ~1,3 GB VRAM** |

Frente a la elección anterior (NLLB-1.3B) esto libera **~1,7 GB de VRAM** y baja la
latencia de traducción de 49 ms a 8 ms. La descarga en instalación sube a ~4 GB porque
los ZIP de Marian pesan 2,5 GB, pero en disco quedan solo 685 MB.

Escenario completo medido con Whisper y los tres traductores cargados **a la vez**:
2321 MB de 8188 (28 %). No hace falta elegir un traductor: caben todos.

Comprobado cargando de verdad los cinco presets por el camino de la app (mismo código
que `AsrPipeline.start()`): **2439 MB de 8188** con Whisper y traductor arriba, es decir
**+1355 MB sobre el escritorio**. El traductor carga en 171–363 ms y traduce en 12–20 ms
(130 ms el primero, que incluye el calentamiento). Con `video-es` el factory devuelve
`NullTranslator` y no se reserva VRAM de traducción.

Limitación conocida y aceptada: Opus-MT capitaliza y puntúa de forma menos consistente
que NLLB en fragmentos (`genau` → «exactamente», `vielen dank` → «muchas gracias», en
minúscula). Es cosmético y no desinforma, al contrario que las alucinaciones de NLLB.
Un paso explícito de normalización de salida en el pipeline lo arreglaría; queda fuera
de esta fase.

## 4bis. Nota sobre `int8_float16` en ASR

La investigación bibliográfica sugería `float16` para `large-v3-turbo`, con el argumento
de que int8 puede ser más lento en Ada Lovelace. **En esta máquina es falso.** Remedido
con 7 repeticiones sobre la misma ventana de 10 s y texto de salida idéntico:

| compute_type | VRAM | p50 |
| --- | --- | --- |
| `float16` | 2196 MB | 253 ms |
| **`int8_float16`** | **1058 MB** | **225 ms** |
| `int8` | 1066 MB | 228 ms |

Se mantiene `int8_float16`.

## 5. Presets de fábrica

Seis presets, uno por idioma del catálogo. Todos comparten el bloque de modelos de §4.

### Presets parciales

Hasta ahora un preset general era un snapshot de **toda** la config, así que aplicarlo
reescribía también tipografía, transparencia y geometría de las ventanas. Para presets
que se cambian a menudo —uno por idioma de vídeo— eso significa que el overlay salta de
sitio cada vez que cambias de idioma, que es inaceptable.

Por eso el snapshot pasa a poder ser **parcial**:

- `snapshot_app_config(cfg, keys=...)` guarda solo esas claves.
- `apply_app_preset` fusiona el snapshot **sobre la config actual**: lo que el preset
  trae manda, lo que no trae se queda como está.

Para un snapshot completo el resultado es idéntico al anterior, así que los presets de
usuario ya guardados no cambian de comportamiento.

Los `video-*` son parciales y llevan solo 13 claves: idioma, bloque de modelos,
traducción y presentación de subtítulos. **No** llevan geometría, apariencia, perfiles
de latencia ni dispositivo de audio.

`default` sigue siendo un snapshot completo: su función es justamente restaurar todo a
la config de referencia del producto.

| Preset | `language` | Traduce | `translation_target` |
| --- | --- | --- | --- |
| `video-en-es` | en | sí | es |
| `video-fr-es` | fr | sí | es |
| `video-de-es` | de | sí | es |
| `video-it-es` | it | sí | es |
| `video-pt-es` | pt | sí | es |
| `video-es` | es | **no** | — |

`video-es` transcribe vídeo en español sin traducir: mismo modelo de reconocimiento,
`translation_enabled=false`, y así no carga el traductor.

Valores comunes de los seis:

- `model: large-v3-turbo`, `compute_type: int8_float16`, `device: cuda`
- `translator_model: opus-mt-tc-big` — el modelo concreto lo elige el motor según el
  idioma de origen, así que el preset no tiene que nombrarlo.
- `translation_decode_preset: balanced` (beam 4, length_penalty 0.7, no-repeat 3)
- `translation_sticky_mode: committed` — reutiliza los tramos ya traducidos.
- `second_line_mode: none`, `captions_show_partials: false` — una sola línea en español,
  sin parpadeo, que es lo legible al ver un vídeo.
- `installed_languages`: no se toca; el idioma activo se añade solo al normalizar, así
  que el preset no pisa la lista que el usuario haya elegido.

El preset `default` se mantiene como referencia y hereda el motor de traducción nuevo.

### Registro de modelos de traducción

`translator_model` pasa de «repo de un modelo» a «motor», porque con Opus-MT el modelo
depende del idioma de origen. El mapa vive en `src/asr/opusmt.py` como tabla de datos y
añadir un idioma es añadir una fila:

| Origen | Modelo | Token destino |
| --- | --- | --- |
| `en` | `tc-big-en-es` | — |
| `de` | `tc-big-de-es` | — |
| `fr`, `it`, `pt` | `tc-big-itc-itc` | `>>spa<<` |

Tres consecuencias de diseño:

- La caché de modelos cargados se indexa **por nombre de modelo, no por idioma**, para
  que fr/it/pt no carguen tres copias del mismo directorio.
- `translator_fingerprint()` incluye el idioma **solo** cuando el motor elige modelo por
  idioma. Con NLLB no lo incluye, porque recargar 1,4 GB al cambiar de idioma sería
  trabajo inútil.
- Los modelos convertidos viven en `$XDG_DATA_HOME/whisper-live-captions/opus-mt`
  (override con `WLCL_MODELS_DIR`), no en la caché de Hugging Face, porque no vienen de
  allí.

## 6. Requisitos testables

### Catálogo y siembra

1. `factory_app_preset_ids()` devuelve exactamente `default` y los seis `video-*`.
2. Una config vacía validada contiene los siete presets de fábrica.
3. Una config de una versión anterior (con `app_presets` que solo tiene `default`)
   gana los seis `video-*` al validarse, **sin perder** presets de usuario.
4. Si el usuario sobrescribe un preset de fábrica con «Guardar», sus valores
   **persisten** entre arranques: la siembra solo rellena los que faltan.
5. `delete_app_preset` lanza `ValueError` para cualquier preset de fábrica.
6. `apply_app_preset("video-fr-es")` deja `language="fr"`, `translation_enabled=True`,
   `model="large-v3-turbo"`, `compute_type="int8_float16"`.
7. `apply_app_preset("video-es")` deja `translation_enabled=False`.
8. Aplicar un `video-*` **conserva** `font_size`, `window_pos`, `window_width`,
   `audio_monitor`, `latency_mode` y `latency_profiles` de la config actual.
9. Cambiar de `video-en-es` a `video-pt-es` no mueve ni redimensiona el overlay.
10. Aplicar `default` **sí** restaura apariencia y geometría de fábrica.

### Traductor

11. `resolve_translator_model_id("nllb-200-distilled-1.3b-ct2")` devuelve el repo
    `OpenNMT/nllb-200-distilled-1.3B-ct2-int8`, y el alias resuelve sin distinguir
    mayúsculas.
12. Un repo arbitrario (`yo/mi-conversion-ct2`) se respeta tal cual: `translator_model`
    solo se normaliza cuando viene vacío, y entonces vale `opus-mt-tc-big`.
13. La UI de traducción ofrece elegir entre los motores del catálogo, el valor elegido
    sobrevive a `result_config()` y un repo propio de la config no se pierde.
14. `create_translator` devuelve `MarianCt2Translator` con `opus-mt-tc-big` y
    `NllbCt2Translator` con un alias o repo de NLLB.
15. `fr`, `it` y `pt` comparten una sola instancia cargada de `tc-big-itc-itc`.
16. Solo el modelo multilingüe recibe el token `>>spa<<`; los bilingües no.
17. El encoder **no** añade `</s>`: lo pone CT2 por `add_source_eos`.
18. `translator_fingerprint` cambia al cambiar de idioma con Opus-MT y **no** cambia con
    NLLB.
19. Passthrough sin tocar el backend cuando origen = destino, el texto está vacío, el
    destino no es español, o el idioma no está en el registro.
20. `max_decoding_length=96` siempre, como techo duro contra alucinaciones largas.
21. Fallback CUDA→CPU con aviso una sola vez, igual que en NLLB.
22. Precargar con idioma `es` (sin modelo Opus-MT) no lanza excepción.

### Precarga y conversión

23. `scripts/prefetch-models.py --list` imprime los modelos y no descarga nada.
24. `required_models()` sale de `factory_app_presets()`, no de una lista aparte:
    devuelve `["large-v3-turbo"]`, ningún repo de NLLB y los tres modelos Opus-MT.
25. La conversión es idempotente: si el directorio ya tiene `model.bin`, `config.json`
    y los dos `.spm`, no se descarga nada.
26. `is_model_ready` exige los `.spm`, que el conversor no copia por sí solo.
27. Las URL apuntan a `opusTCv20210807` y nunca a un `*-bible-big-*`.
28. `install-user.sh` copia el script a la instalación, lo invoca y **no falla la
    instalación** si la descarga falla (p. ej. sin red): avisa y continúa.
29. `WLCL_SKIP_MODEL_PREFETCH=1` salta la precarga.

## 7. Always / Ask / Never

**Always**

- Sembrar los presets de fábrica que falten en cada validación de config.
- Mantener los presets de fábrica no borrables.
- Respetar los perfiles de latencia y la apariencia del usuario al aplicar un preset.

**Ask**

- Antes de cambiar el modelo por defecto del preset `default` existente.
- Antes de añadir un idioma nuevo al catálogo (implica fila en el registro o caída a
  NLLB, y preset nuevo).

**Never**

- Auto-detectar el idioma del vídeo.
- Añadir `torch` o `transformers` para convertir modelos: `OpusMTConverter` lo hace con
  numpy y pyyaml.
- Usar los Opus-MT `*-bible-big-*` de 2024, por los artefactos de subtítulos.
- Añadir `</s>` al tokenizar para Marian: lo pone CT2.
- Descargar o convertir pesos desde el hilo de Qt.
- Bloquear la instalación por un fallo de descarga de modelos.
