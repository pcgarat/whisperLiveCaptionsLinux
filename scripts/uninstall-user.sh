#!/usr/bin/env bash
# Desinstala la copia de usuario (~/.local). No borra config salvo PURGE_CONFIG=1.
set -euo pipefail

APP_ID="whisper-live-captions"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"

APP_ROOT="${WLCL_INSTALL_ROOT:-$XDG_DATA_HOME/$APP_ID}"
BIN_PATH="$XDG_BIN_HOME/$APP_ID"
DESKTOP="$XDG_DATA_HOME/applications/whisper-live-captions.desktop"
ICON_SVG="$XDG_DATA_HOME/icons/hicolor/scalable/apps/whisper-live-captions.svg"
CONFIG_DIR="$XDG_CONFIG_HOME/$APP_ID"

rm -rf "$APP_ROOT"
rm -f "$BIN_PATH" "$DESKTOP" "$ICON_SVG"
for size in 32 48 64 128 256; do
  rm -f "$XDG_DATA_HOME/icons/hicolor/${size}x${size}/apps/whisper-live-captions.png"
done

if [[ "${PURGE_CONFIG:-0}" == "1" ]]; then
  rm -rf "$CONFIG_DIR"
  echo "Config borrada: $CONFIG_DIR"
else
  echo "Config conservada: $CONFIG_DIR (PURGE_CONFIG=1 para borrar)"
fi

DESKTOP_DIR="$XDG_DATA_HOME/applications"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$XDG_DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "OK: $APP_ID desinstalado"
