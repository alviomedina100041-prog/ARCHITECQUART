#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/architecquart"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
SCALABLE_ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
BIN_DIR="$HOME/.local/bin"
STAGING="${INSTALL_DIR}.new"

echo "== ArchiTecQuart Installer =="
echo

sudo pacman -S --needed \
    python \
    python-pip \
    python-virtualenv \
    hicolor-icon-theme

if ! command -v quarto >/dev/null 2>&1; then
    echo
    echo "AVISO: Quarto CLI no está en PATH."
    echo "ArchiTecQuart se instalará, pero Preview/Render requieren Quarto."
    echo "Comprueba después con: quarto --version"
    echo
fi

rm -rf "$STAGING"
mkdir -p \
    "$STAGING" \
    "$DESKTOP_DIR" \
    "$ICON_DIR" \
    "$SCALABLE_ICON_DIR" \
    "$BIN_DIR"

cp -a "$SOURCE_DIR/app" "$STAGING/"
cp -a "$SOURCE_DIR/assets" "$STAGING/"
cp -a "$SOURCE_DIR/scripts" "$STAGING/"
cp "$SOURCE_DIR/requirements.txt" "$STAGING/"
cp "$SOURCE_DIR/README.md" "$STAGING/"

python -m venv "$STAGING/.venv"
"$STAGING/.venv/bin/python" -m pip install --upgrade pip
"$STAGING/.venv/bin/python" -m pip install -r "$STAGING/requirements.txt"

chmod +x "$STAGING/scripts/run_architecquart.sh"
chmod +x "$STAGING/scripts/install_arch.sh"
chmod +x "$STAGING/scripts/uninstall_arch.sh"

rm -rf "$INSTALL_DIR"
mv "$STAGING" "$INSTALL_DIR"

sed "s|__PROJECT_DIR__|$INSTALL_DIR|g" \
    "$INSTALL_DIR/scripts/architecquart.desktop" \
    > "$DESKTOP_DIR/architecquart.desktop"
chmod +x "$DESKTOP_DIR/architecquart.desktop"

# Install the icon using the freedesktop icon-theme layout.
# The desktop file can then use Icon=architecquart instead of an absolute SVG path.
rm -f "$ICON_DIR/architecquart.png" "$SCALABLE_ICON_DIR/architecquart.svg"
cp "$INSTALL_DIR/assets/icon.png" "$ICON_DIR/architecquart.png"
cp "$INSTALL_DIR/assets/icon.svg" "$SCALABLE_ICON_DIR/architecquart.svg"

cat > "$BIN_DIR/architecquart" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/scripts/run_architecquart.sh" "\$@"
EOF
chmod +x "$BIN_DIR/architecquart"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental || true
fi

echo
echo "Instalado en: $INSTALL_DIR"
echo "Icono instalado como: architecquart"
echo "Busca 'ArchiTecQuart' en el menú de aplicaciones."
echo "También puedes ejecutar: architecquart"
