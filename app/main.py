from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_graphics() -> None:
    """Conservative QtWebEngine defaults for Intel Haswell/hybrid laptops."""
    os.environ.setdefault("LIBVA_DRIVER_NAME", "i965")
    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    safe = (
        "--disable-vulkan "
        "--disable-features=Vulkan,VaapiVideoDecoder,VaapiVideoEncoder "
        "--log-level=3"
    )
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{current} {safe}".strip()


configure_graphics()

from PySide6.QtWidgets import QApplication

from .window import MainWindow


def resolve_project() -> str:
    if len(sys.argv) > 1:
        return str(Path(sys.argv[1]).expanduser().resolve())
    env = os.environ.get("ARCHITECQUART_PROJECT")
    if env:
        return str(Path(env).expanduser().resolve())
    return str(Path.home())


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ArchiTecQuart")
    app.setOrganizationName("EduardoMedinaLabs")
    app.setStyle("Fusion")

    window = MainWindow(resolve_project())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
