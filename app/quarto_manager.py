from __future__ import annotations

import shutil
import socket
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class QuartoManager(QObject):
    log_line = Signal(str)
    preview_ready = Signal(str)
    preview_stopped = Signal()
    render_finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.preview_process: QProcess | None = None
        self.render_process: QProcess | None = None
        self.project_root: Path | None = None
        self.port: int | None = None

    def quarto_path(self) -> str | None:
        return shutil.which("quarto")

    def quarto_version(self) -> str:
        path = self.quarto_path()
        if not path:
            return "No instalado"

        process = QProcess()
        process.start(path, ["--version"])
        if process.waitForFinished(2500):
            output = bytes(process.readAllStandardOutput())
            return output.decode(errors="ignore").strip() or "detectado"
        return "detectado"

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @property
    def base_url(self) -> str | None:
        if self.port is None:
            return None
        return f"http://127.0.0.1:{self.port}"

    def start_preview(self, project_root: str | Path) -> None:
        root = Path(project_root).resolve()
        path = self.quarto_path()
        if not path:
            raise RuntimeError(
                "No se encontró Quarto CLI. Verifica con: quarto --version"
            )

        if (
            self.preview_process
            and self.preview_process.state() != QProcess.NotRunning
            and self.project_root == root
        ):
            if self.base_url:
                self.preview_ready.emit(self.base_url)
            return

        self.stop_preview()
        self.project_root = root
        self.port = self._free_port()

        process = QProcess(self)
        process.setWorkingDirectory(str(root))
        process.setProgram(path)
        process.setArguments([
            "preview",
            ".",
            "--no-browser",
            "--port",
            str(self.port),
        ])
        process.setProcessChannelMode(QProcess.MergedChannels)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("NO_COLOR", "1")
        process.setProcessEnvironment(env)

        process.readyReadStandardOutput.connect(self._read_preview_output)
        process.finished.connect(self._preview_finished)
        self.preview_process = process
        process.start()

        if not process.waitForStarted(3500):
            self.preview_process = None
            raise RuntimeError("No se pudo iniciar 'quarto preview'.")

        self.log_line.emit(f"Preview persistente iniciado en {self.base_url}")
        QTimer.singleShot(
            1400,
            lambda: self.preview_ready.emit(self.base_url or ""),
        )

    def _read_preview_output(self) -> None:
        if not self.preview_process:
            return

        data = bytes(self.preview_process.readAllStandardOutput())
        text = data.decode(errors="ignore")
        for line in text.splitlines():
            if line.strip():
                self.log_line.emit(line.rstrip())

    def _preview_finished(self, *_args) -> None:
        self.preview_stopped.emit()

    def stop_preview(self) -> None:
        if self.preview_process and self.preview_process.state() != QProcess.NotRunning:
            self.preview_process.terminate()
            if not self.preview_process.waitForFinished(1800):
                self.preview_process.kill()
                self.preview_process.waitForFinished(1000)

        self.preview_process = None
        self.port = None

    def render(self, project_root: str | Path, target_format: str | None = None) -> None:
        path = self.quarto_path()
        if not path:
            raise RuntimeError("No se encontró Quarto CLI.")

        if self.render_process and self.render_process.state() != QProcess.NotRunning:
            raise RuntimeError("Ya hay un render en ejecución.")

        root = Path(project_root).resolve()
        process = QProcess(self)
        process.setWorkingDirectory(str(root))
        process.setProgram(path)

        args = ["render", "."]
        if target_format:
            args += ["--to", target_format]

        process.setArguments(args)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_render_output)
        process.finished.connect(self._render_done)
        self.render_process = process
        process.start()

        if not process.waitForStarted(3000):
            self.render_process = None
            raise RuntimeError("No se pudo iniciar 'quarto render'.")

        label = target_format or "configuración del proyecto"
        self.log_line.emit(f"Render iniciado: {label}")

    def _read_render_output(self) -> None:
        if not self.render_process:
            return

        text = bytes(self.render_process.readAllStandardOutput()).decode(errors="ignore")
        for line in text.splitlines():
            if line.strip():
                self.log_line.emit(line.rstrip())

    def _render_done(self, exit_code: int, *_args) -> None:
        ok = exit_code == 0
        message = (
            "Render completado."
            if ok
            else f"Render terminó con código {exit_code}."
        )
        self.log_line.emit(message)
        self.render_finished.emit(ok, message)

    def url_for_source(self, source_file: str | Path | None) -> str:
        base = self.base_url or ""
        if not source_file or not self.project_root:
            return base

        path = Path(source_file).resolve()
        try:
            relative = path.relative_to(self.project_root)
        except ValueError:
            return base

        if relative.suffix.lower() == ".qmd":
            relative = relative.with_suffix(".html")

        if relative.name == "index.html":
            return f"{base}/"

        return f"{base}/{quote(relative.as_posix())}"

    def shutdown(self) -> None:
        self.stop_preview()
        if self.render_process and self.render_process.state() != QProcess.NotRunning:
            self.render_process.terminate()
