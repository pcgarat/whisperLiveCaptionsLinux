---
name: add-translation-phase
description: Guía para añadir traducción a español y multi-idioma en whisperLiveCaptionsLinux. Usar cuando el usuario pida traducir, Marian/NLLB, o salir de fase 1 solo-EN.
---

# Fase traducción / multi-idioma

## Antes de codear

1. Confirmar intent + escribir **spec nuevo** (no improvisar sobre fase 1).
2. Idioma fuente: **sigue siendo manual** (no auto-detect salvo spec explícito).
3. Traducción **100 % local** (sin APIs cloud).

## Diseño preferido

- Seguir el protocol `Translator` en `src/asr/translate.py`.
- Traducir solo texto **confirmado** (`is_final`), no cada parcial (menos parpadeo y CPU).
- Un modelo multilingual compacto (p. ej. NLLB/CT2 o similar) > muchos Marian por par de idiomas.
- No cargar traducción en el hilo UI.

## No hacer

- Copiar MarianMT multi-modelo del repo `live_translate_subtitles`.
- Bloquear el overlay esperando traducción.
- Mezclar Whisper `task=translate` (solo a inglés) con “traducir a español” sin dejarlo claro en el spec.

## Verificación mínima

- EN→ES estable en sesión larga.
- Con idioma = `es`, no traducir (passthrough).
- `make test` + smoke manual ≥15 min.
