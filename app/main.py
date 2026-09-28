from __future__ import annotations

import os
import signal
import sys
from pathlib import Path


def configure_graphics() -> None:
    """Stable QtWebEngine defaults for older Intel/Haswell laptops."""
    os.environ.setdefault("LIBVA_DRIVER_NAME", "i965")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

    fonts_conf = Path("/etc/fonts/fonts.conf")
    if fonts_conf.exists():
        os.environ.setdefault("FONTCONFIG_FILE", str(fonts_conf))
        os.environ.setdefault("FONTCONFIG_PATH", str(fonts_conf.parent))

    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    safe = (
        "--disable-gpu "
        "--disable-gpu-compositing "
        "--disable-vulkan "
        "--disable-features=Vulkan,VaapiVideoDecoder,VaapiVideoEncoder "
        "--log-level=3"
    )
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{current} {safe}".strip()


configure_graphics()

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
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

    icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
    fallback_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    app.setWindowIcon(QIcon.fromTheme("architecquart", fallback_icon))

    window = MainWindow(resolve_project())

    # Python only receives SIGINT while it gets regular interpreter time.
    # A tiny Qt timer keeps Ctrl+C responsive and lets us shut down
    # QWebEngine/QProcess children before QApplication exits.
    signal_timer = QTimer()
    signal_timer.setInterval(200)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start()

    def graceful_quit(*_args) -> None:
        window.shutdown()
        app.quit()

    signal.signal(signal.SIGINT, graceful_quit)
    signal.signal(signal.SIGTERM, graceful_quit)
    app.aboutToQuit.connect(window.shutdown)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
