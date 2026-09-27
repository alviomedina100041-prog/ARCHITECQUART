#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/architecquart"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN_DIR="$HOME/.local/bin"
STAGING="${INSTALL_DIR}.new"

echo "== ArchiTecQuart Installer =="
echo

sudo pacman -S --needed python python-pip python-virtualenv

if ! command -v quarto >/dev/null 2>&1; then
    echo
    echo "AVISO: Quarto CLI no está en PATH."
    echo "ArchiTecQuart se instalará, pero Preview/Render requieren Quarto."
    echo "Comprueba después con: quarto --version"
    echo
fi

rm -rf "$STAGING"
mkdir -p "$STAGING" "$DESKTOP_DIR" "$BIN_DIR"

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

sed "s|__PROJECT_DIR__|$INSTALL_DIR|g"     "$INSTALL_DIR/scripts/architecquart.desktop"     > "$DESKTOP_DIR/architecquart.desktop"
chmod +x "$DESKTOP_DIR/architecquart.desktop"

cat > "$BIN_DIR/architecquart" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/scripts/run_architecquart.sh" "\$@"
EOF
chmod +x "$BIN_DIR/architecquart"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" || true
fi

echo
echo "Instalado en: $INSTALL_DIR"
echo "Busca 'ArchiTecQuart' en el menú de aplicaciones."
echo "También puedes ejecutar: architecquart"
