#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/architecquart"
DESKTOP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/architecquart.desktop"
BIN_FILE="$HOME/.local/bin/architecquart"

rm -rf "$INSTALL_DIR"
rm -f "$DESKTOP_FILE" "$BIN_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" || true
fi

echo "ArchiTecQuart desinstalado."
