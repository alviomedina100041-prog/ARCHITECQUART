#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
    echo "ArchiTecQuart: falta .venv. Ejecuta scripts/install_arch.sh primero." >&2
    exit 1
fi

export LIBVA_DRIVER_NAME="${LIBVA_DRIVER_NAME:-i965}"
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --disable-vulkan --disable-features=Vulkan,VaapiVideoDecoder,VaapiVideoEncoder --log-level=3"

TARGET="${1:-$HOME}"
exec .venv/bin/python -m app.main "$TARGET"
