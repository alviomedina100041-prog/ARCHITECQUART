#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/architecquart"
DESKTOP_FILE="$DATA_HOME/applications/architecquart.desktop"
PNG_ICON="$DATA_HOME/icons/hicolor/256x256/apps/architecquart.png"
SVG_ICON="$DATA_HOME/icons/hicolor/scalable/apps/architecquart.svg"
BIN_FILE="$HOME/.local/bin/architecquart"

rm -rf "$INSTALL_DIR"
rm -f "$DESKTOP_FILE" "$BIN_FILE" "$PNG_ICON" "$SVG_ICON"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_HOME/applications" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" || true
fi

echo "ArchiTecQuart desinstalado."
