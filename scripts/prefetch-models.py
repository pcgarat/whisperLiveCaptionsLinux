#!/usr/bin/env python3
"""Descarga (y convierte) los modelos que usan los presets de fábrica.

Se ejecuta en la instalación para que el primer arranque de cualquier preset no
dispare una descarga de gigas en caliente. Los modelos se derivan del catálogo
(`src/presets.py`), así que no hay una lista paralela que se desincronice.

Tres procedencias distintas, cada una con el mismo código que usa la app:
`faster_whisper.download_model` para el reconocimiento, `snapshot_download` para
NLLB, y descarga del ZIP de Marian + `ct2-opus-mt-converter` para Opus-MT. La
conversión de Opus-MT baja ~2,5 GB de ZIP y deja ~685 MB en disco; se hace aquí y
no en caliente porque tarda ~90 s.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.asr.opusmt import OpusMtModel  # noqa: E402
from src.asr.opusmt import convert_model, is_model_ready
from src.asr.opusmt import required_models as opus_models_for  # noqa: E402
from src.asr.translate import is_opus_mt_model, resolve_translator_model_id  # noqa: E402
from src.config import factory_app_presets  # noqa: E402


def required_models() -> tuple[list[str], list[str], list[OpusMtModel]]:
    """(modelos Whisper, repos NLLB, modelos Opus-MT) que piden los presets."""
    whisper: list[str] = []
    nllb: list[str] = []
    opus_languages: list[str] = []
    for snapshot in factory_app_presets().values():
        name = str(snapshot.get("model") or "").strip()
        if name and name not in whisper:
            whisper.append(name)
        if not bool(snapshot.get("translation_enabled", False)):
            continue
        model = str(snapshot.get("translator_model") or "")
        if is_opus_mt_model(model):
            opus_languages.append(str(snapshot.get("language") or ""))
            continue
        repo = resolve_translator_model_id(model)
        if repo and repo not in nllb:
            nllb.append(repo)
    return whisper, nllb, opus_models_for(opus_languages)


def fetch_whisper(name: str) -> None:
    from faster_whisper import download_model

    download_model(name)


def fetch_nllb(repo_id: str) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=repo_id)


def fetch_opus(model: OpusMtModel) -> None:
    if is_model_ready(model):
        return
    convert_model(model)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list", action="store_true", help="solo listar los modelos, sin descargar"
    )
    args = parser.parse_args()

    whisper, nllb, opus = required_models()
    jobs: list[tuple[str, str, object, object]] = [
        *(("reconocimiento", name, fetch_whisper, name) for name in whisper),
        *(("traducción NLLB", repo, fetch_nllb, repo) for repo in nllb),
        *(("traducción Opus-MT", m.name, fetch_opus, m) for m in opus),
    ]

    if args.list:
        for kind, label, _, _ in jobs:
            print(f"{kind}: {label}")
        return 0

    logging.basicConfig(level=logging.INFO, format="  %(message)s")
    failures: list[str] = []
    for index, (kind, label, fetch, payload) in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {kind}: {label}", flush=True)
        try:
            fetch(payload)  # type: ignore[operator]
        except Exception as exc:
            print(f"  fallo: {exc}", file=sys.stderr)
            failures.append(label)

    if failures:
        print(
            "\nNo se pudieron descargar: "
            + ", ".join(failures)
            + "\nLa app los bajará al usarlos por primera vez.",
            file=sys.stderr,
        )
        return 1
    print("\nModelos listos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
