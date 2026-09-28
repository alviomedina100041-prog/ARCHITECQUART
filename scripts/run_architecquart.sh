#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
    echo "ArchiTecQuart: falta .venv." >&2
    echo "Crea el entorno con:" >&2
    echo "  python -m venv .venv" >&2
    echo "  source .venv/bin/activate" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

export LIBVA_DRIVER_NAME="${LIBVA_DRIVER_NAME:-i965}"
export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"

if [[ -f /etc/fonts/fonts.conf ]]; then
    export FONTCONFIG_FILE="${FONTCONFIG_FILE:-/etc/fonts/fonts.conf}"
    export FONTCONFIG_PATH="${FONTCONFIG_PATH:-/etc/fonts}"
fi

export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --disable-gpu --disable-gpu-compositing --disable-vulkan --disable-features=Vulkan,VaapiVideoDecoder,VaapiVideoEncoder --log-level=3"

TARGET="${1:-$HOME}"
exec .venv/bin/python -m app.main "$TARGET"
