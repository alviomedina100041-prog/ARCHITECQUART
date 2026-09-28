from __future__ import annotations

import shutil
import socket
from pathlib import Path
from urllib.parse import quote

import yaml
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class QuartoManager(QObject):
    log_line = Signal(str)
    preview_ready = Signal(str)
    preview_stopped = Signal()
    # ok, human-readable message, generated output path
    render_finished = Signal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.preview_process: QProcess | None = None
        self.render_process: QProcess | None = None
        self.project_root: Path | None = None
        self.port: int | None = None

        self.render_root: Path | None = None
        self.render_target_format: str | None = None
        self.render_output_lines: list[str] = []

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

    def is_preview_running(self) -> bool:
        return bool(
            self.preview_process
            and self.preview_process.state() != QProcess.NotRunning
        )

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

        def announce_ready() -> None:
            if self.is_preview_running() and self.base_url:
                self.preview_ready.emit(self.base_url)

        QTimer.singleShot(1400, announce_ready)

    def _read_preview_output(self) -> None:
        if not self.preview_process:
            return

        data = bytes(self.preview_process.readAllStandardOutput())
        text = data.decode(errors="ignore")
        for line in text.splitlines():
            if line.strip():
                self.log_line.emit(line.rstrip())

    def _preview_finished(self, *_args) -> None:
        self.preview_process = None
        self.port = None
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
            raise RuntimeError(
                "No se encontró Quarto CLI. Verifica con: quarto --version"
            )

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

        env = QProcessEnvironment.systemEnvironment()
        env.insert("NO_COLOR", "1")
        process.setProcessEnvironment(env)

        self.render_root = root
        self.render_target_format = target_format
        self.render_output_lines = []

        process.readyReadStandardOutput.connect(self._read_render_output)
        process.finished.connect(self._render_done)
        self.render_process = process
        process.start()

        if not process.waitForStarted(3000):
            self.render_process = None
            raise RuntimeError("No se pudo iniciar 'quarto render'.")

        label = target_format.upper() if target_format else "configuración del proyecto"
        self.log_line.emit(f"Render iniciado: {label}")
        self.log_line.emit(f"Proyecto: {root}")

    def _read_render_output(self) -> None:
        if not self.render_process:
            return

        text = bytes(self.render_process.readAllStandardOutput()).decode(errors="ignore")
        for line in text.splitlines():
            if not line.strip():
                continue
            cleaned = line.rstrip()
            self.render_output_lines.append(cleaned)
            self.render_output_lines = self.render_output_lines[-300:]
            self.log_line.emit(cleaned)

    def _configured_output_dir(self, root: Path) -> Path:
        config_path = root / "_quarto.yml"
        output_dir = "_book"

        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            project = data.get("project") or {}
            configured = project.get("output-dir")
            if isinstance(configured, str) and configured.strip():
                output_dir = configured.strip()
        except Exception:
            pass

        candidate = Path(output_dir).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()

    def _detect_render_output(
        self,
        root: Path,
        target_format: str | None,
    ) -> Path | None:
        output_dir = self._configured_output_dir(root)

        if target_format == "html":
            index = output_dir / "index.html"
            if index.exists():
                return output_dir
            if output_dir.exists():
                html_files = sorted(
                    output_dir.rglob("*.html"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
                if html_files:
                    return output_dir

        if target_format in {"pdf", "epub"}:
            extension = f".{target_format}"
            candidates: list[Path] = []

            if output_dir.exists():
                candidates.extend(output_dir.rglob(f"*{extension}"))

            # Custom projects sometimes place single-file output elsewhere.
            candidates.extend(
                path
                for path in root.glob(f"*{extension}")
                if path.is_file()
            )

            unique = {path.resolve(): path.resolve() for path in candidates}
            if unique:
                return max(
                    unique.values(),
                    key=lambda path: path.stat().st_mtime,
                )

        if target_format is None and output_dir.exists():
            return output_dir

        return None

    def _render_done(self, exit_code: int, *_args) -> None:
        # Capture any bytes Quarto emitted between the last readyRead signal
        # and process termination.
        self._read_render_output()

        root = self.render_root
        target = self.render_target_format
        ok = exit_code == 0
        output_path = ""

        if ok and root:
            detected = self._detect_render_output(root, target)
            if detected:
                output_path = str(detected)

            label = target.upper() if target else "proyecto"
            if output_path:
                message = f"Render {label} completado."
            else:
                message = (
                    f"Render {label} completado, pero no pude localizar "
                    "automáticamente el archivo generado."
                )
        else:
            tail = "\n".join(self.render_output_lines[-14:]).strip()
            message = f"Quarto terminó con código {exit_code}."
            if tail:
                message += f"\n\nÚltimos mensajes de Quarto:\n{tail}"

        self.log_line.emit(message)
        self.render_process = None
        self.render_finished.emit(ok, message, output_path)

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
