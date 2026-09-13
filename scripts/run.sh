#!/usr/bin/env bash
# Prefija las libs Qt empaquetadas con PyQt6 para evitar mezclarlas
# con /usr/lib (p. ej. LD_LIBRARY_PATH inyectado por Cursor AppImage).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

QT6_ROOT="$(python -c 'import PyQt6, pathlib; print(pathlib.Path(PyQt6.__file__).resolve().parent / "Qt6")')"
export LD_LIBRARY_PATH="$QT6_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="$QT6_ROOT/plugins"

exec python -m src.app "$@"
