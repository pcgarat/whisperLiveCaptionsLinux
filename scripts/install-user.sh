#!/usr/bin/env bash
# Instala la app en ~/.local (sin root): binario, menú e icono.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"
APP_ID="whisper-live-captions"

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

APP_ROOT="${WLCL_INSTALL_ROOT:-$XDG_DATA_HOME/$APP_ID}"
BIN_PATH="$XDG_BIN_HOME/$APP_ID"
DESKTOP_DIR="$XDG_DATA_HOME/applications"
ICON_DIR="$XDG_DATA_HOME/icons/hicolor/scalable/apps"
CONFIG_DIR="$XDG_CONFIG_HOME/$APP_ID"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: se necesita $PYTHON en PATH" >&2
  exit 1
fi
if ! command -v rsync >/dev/null 2>&1; then
  echo "error: se necesita rsync en PATH" >&2
  exit 1
fi

echo "Instalando en $APP_ROOT"
mkdir -p "$APP_ROOT" "$XDG_BIN_HOME" "$DESKTOP_DIR" "$ICON_DIR" "$CONFIG_DIR"

rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.py[cod]' \
  "$ROOT/src/" "$APP_ROOT/src/"
rsync -a --delete "$ROOT/packaging/" "$APP_ROOT/packaging/"
rsync -a --delete "$ROOT/assets/" "$APP_ROOT/assets/"
cp "$ROOT/requirements.txt" "$ROOT/config.example.json" "$APP_ROOT/"
mkdir -p "$APP_ROOT/scripts"
cp "$ROOT/scripts/prefetch-models.py" "$APP_ROOT/scripts/"

if [[ ! -d "$APP_ROOT/.venv" ]]; then
  "$PYTHON" -m venv "$APP_ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$APP_ROOT/.venv/bin/activate"
pip install -q -U pip
pip install -q -r "$APP_ROOT/requirements.txt"

# Precarga: sin esto, el primer arranque de un preset baja gigas en caliente y,
# en el caso de Opus-MT, convierte a CT2 con la app ya abierta.
# Un fallo de red no debe tumbar la instalación; la app los bajará al usarlos.
if [[ -n "${WLCL_SKIP_MODEL_PREFETCH:-}" ]]; then
  echo "Precarga de modelos saltada (WLCL_SKIP_MODEL_PREFETCH)."
else
  echo "Descargando y convirtiendo modelos de los presets (~4 GB de descarga)…"
  if ! python "$APP_ROOT/scripts/prefetch-models.py"; then
    echo "aviso: falló la precarga de modelos; la app los bajará al usarlos." >&2
  fi
fi

cat >"$BIN_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$APP_ROOT"
CONFIG_DIR="$CONFIG_DIR"
# shellcheck disable=SC1091
source "\$APP_ROOT/.venv/bin/activate"
export PYTHONPATH="\$APP_ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
export WLCL_APP_ROOT="\$APP_ROOT"
export WLCL_CONFIG_DIR="\$CONFIG_DIR"
QT6_ROOT="\$(python -c 'import PyQt6, pathlib; print(pathlib.Path(PyQt6.__file__).resolve().parent / "Qt6")')"
export LD_LIBRARY_PATH="\$QT6_ROOT/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="\$QT6_ROOT/plugins"
export QT_QPA_PLATFORM="\${QT_QPA_PLATFORM:-xcb}"
exec python -m src.app "\$@"
EOF
chmod +x "$BIN_PATH"

cp "$ROOT/packaging/icons/whisper-live-captions.svg" \
  "$ICON_DIR/whisper-live-captions.svg"
for size in 32 48 64 128 256; do
  size_dir="$XDG_DATA_HOME/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$size_dir"
  cp "$ROOT/packaging/icons/whisper-live-captions-${size}.png" \
    "$size_dir/whisper-live-captions.png"
done

# Exec absoluto: no depende de que ~/.local/bin esté en PATH del .desktop.
sed "s|@EXEC@|$BIN_PATH|g" \
  "$ROOT/packaging/whisper-live-captions.desktop.in" \
  >"$DESKTOP_DIR/whisper-live-captions.desktop"
chmod 644 "$DESKTOP_DIR/whisper-live-captions.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "OK: $APP_ID instalado"
echo "  lanzador: $BIN_PATH"
echo "  menú:     $DESKTOP_DIR/whisper-live-captions.desktop"
echo "  config:   $CONFIG_DIR/config.json (se crea al guardar)"
if [[ ":$PATH:" != *":$XDG_BIN_HOME:"* ]]; then
  echo "aviso: $XDG_BIN_HOME no está en PATH; el menú usa ruta absoluta, la CLI puede no resolver el comando." >&2
fi
