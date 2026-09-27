from __future__ import annotations

import re

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class TerminalWidget(QWidget):
    def __init__(self, working_directory: str):
        super().__init__()

        self.process = QProcess(self)
        self.process.setWorkingDirectory(working_directory)
        self.process.setProgram("/bin/bash")
        self.process.setArguments(["--noprofile", "--norc", "-i"])

        env = QProcessEnvironment.systemEnvironment()
        env.insert("TERM", "dumb")
        env.insert("NO_COLOR", "1")
        env.insert("PS1", "$ ")
        self.process.setProcessEnvironment(env)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(1000)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Comando…")
        self.input.returnPressed.connect(self.run_command)

        run = QPushButton("Ejecutar")
        run.clicked.connect(self.run_command)

        bottom = QHBoxLayout()
        bottom.addWidget(self.input, 1)
        bottom.addWidget(run)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.output, 1)
        layout.addLayout(bottom)

        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.start()

    def _clean(self, value: str) -> str:
        return ANSI.sub("", value).replace("\r", "")

    def _append(self, value: str) -> None:
        value = self._clean(value).strip("\n")
        if value:
            self.output.appendPlainText(value)

    def _read_stdout(self) -> None:
        self._append(
            bytes(self.process.readAllStandardOutput()).decode(errors="ignore")
        )

    def _read_stderr(self) -> None:
        self._append(
            bytes(self.process.readAllStandardError()).decode(errors="ignore")
        )

    def run_command(self) -> None:
        command = self.input.text().strip()
        if not command:
            return

        self.output.appendPlainText(f"$ {command}")
        self.process.write((command + "\n").encode())
        self.input.clear()
