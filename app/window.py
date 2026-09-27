from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .book_model import BookModel, parse_bib_file
from .editor import CodeEditor
from .quarto_manager import QuartoManager
from .terminal import TerminalWidget
from .theme import APP_STYLE


class MainWindow(QMainWindow):
    def __init__(self, project_root: str):
        super().__init__()

        self.project_root = Path(project_root).expanduser().resolve()
        self.book = BookModel(self.project_root)
        self.current_file: Path | None = None
        self.dirty = False
        self._loading_editor = False

        self.log_lines: list[str] = []
        self.bib_entries: list[dict[str, str]] = []

        self.preview_dialog: QDialog | None = None
        self.preview_view: QWebEngineView | None = None
        self.logs_dialog: QDialog | None = None
        self.logs_view: QPlainTextEdit | None = None
        self.bib_dialog: QDialog | None = None
        self.terminal_dialog: QDialog | None = None

        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen else None
        self.compact = bool(
            geometry and (geometry.width() <= 1400 or geometry.height() <= 820)
        )

        self.setWindowTitle("ArchiTecQuart — Quarto Book Studio")
        if geometry:
            self.resize(
                min(1366 if self.compact else 1600, geometry.width()),
                min(780 if self.compact else 940, geometry.height()),
            )
        else:
            self.resize(1366, 780)
        self.setMinimumSize(1050, 650)

        self.quarto = QuartoManager()
        self.quarto.log_line.connect(self._append_log)
        self.quarto.preview_ready.connect(self._preview_ready)
        self.quarto.preview_stopped.connect(self._preview_stopped)
        self.quarto.render_finished.connect(self._render_finished)

        # Write to disk only after the user has paused for a moment.
        # This prevents Quarto Preview from rebuilding while a sentence is
        # still being typed.
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(2500)
        self.autosave_timer.timeout.connect(self._autosave)

        self._build_ui()
        self.setStyleSheet(APP_STYLE)
        self._load_project(self.project_root)

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(7, 7, 7, 7)
        outer.setSpacing(6)

        outer.addWidget(self._build_top_bar())

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(3)

        self.main_splitter.addWidget(self._build_book_panel())
        self.main_splitter.addWidget(self._build_editor_panel())
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        if self.compact:
            self.main_splitter.setSizes([285, 1040])
        else:
            self.main_splitter.setSizes([320, 1240])

        outer.addWidget(self.main_splitter, 1)
        outer.addWidget(self._build_status_bar())
        self.setCentralWidget(central)

    def _build_top_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("TopBar")
        frame.setFixedHeight(52 if self.compact else 62)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        title = QLabel("▣  ArchiTecQuart")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.project_label = QLabel("Sin libro")
        self.project_label.setObjectName("Muted")
        self.project_label.setMaximumWidth(150 if self.compact else 240)
        layout.addWidget(self.project_label)
        layout.addStretch(1)

        self.preview_state = QLabel("● Preview detenido")
        self.preview_state.setObjectName("PreviewOff")
        layout.addWidget(self.preview_state)

        open_btn = QPushButton("Abrir")
        open_btn.clicked.connect(self._choose_project)

        new_btn = QPushButton("+ Cap.")
        new_btn.setToolTip("Nuevo capítulo")
        new_btn.clicked.connect(self._new_chapter)

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self._save_current)

        self.auto_btn = QPushButton("Auto")
        self.auto_btn.setCheckable(True)
        self.auto_btn.setChecked(True)
        self.auto_btn.setToolTip(
            "Mantiene Quarto Preview ejecutándose. "
            "El archivo se guarda 2.5 s después de dejar de escribir."
        )
        self.auto_btn.toggled.connect(self._toggle_auto_preview)

        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._show_preview_dialog)

        bib_btn = QPushButton("Biblio")
        bib_btn.setToolTip("Bibliografía")
        bib_btn.clicked.connect(self._show_bibliography_dialog)

        logs_btn = QPushButton("Logs")
        logs_btn.clicked.connect(self._show_logs_dialog)

        terminal_btn = QPushButton("Terminal")
        terminal_btn.clicked.connect(self._show_terminal_dialog)

        render_btn = QPushButton("▶ Render")
        render_btn.setObjectName("Primary")
        render_btn.clicked.connect(lambda: self._render(None))

        export_btn = QToolButton()
        export_btn.setText("Exportar ▾")
        export_menu = QMenu(export_btn)

        for label, target in [
            ("HTML", "html"),
            ("PDF", "pdf"),
            ("EPUB", "epub"),
        ]:
            action = QAction(label, export_menu)
            action.triggered.connect(
                lambda _checked=False, fmt=target: self._render(fmt)
            )
            export_menu.addAction(action)

        export_btn.setMenu(export_menu)
        export_btn.setPopupMode(QToolButton.InstantPopup)

        for widget in [
            open_btn,
            new_btn,
            save_btn,
            self.auto_btn,
            preview_btn,
            bib_btn,
            logs_btn,
            terminal_btn,
            render_btn,
            export_btn,
        ]:
            layout.addWidget(widget)

        return frame

    def _build_book_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SidePanel")

        if self.compact:
            frame.setMinimumWidth(250)
            frame.setMaximumWidth(340)
        else:
            frame.setMinimumWidth(280)
            frame.setMaximumWidth(390)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("Estructura del libro")
        title.setObjectName("SectionTitle")

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.setToolTip("Nuevo capítulo")
        add_btn.clicked.connect(self._new_chapter)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.book_tree = QTreeWidget()
        self.book_tree.setHeaderHidden(True)
        self.book_tree.itemClicked.connect(self._tree_item_clicked)
        layout.addWidget(self.book_tree, 1)

        return frame

    def _build_editor_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("EditorPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.file_label = QLabel("Selecciona un capítulo")
        self.file_label.setObjectName("SectionTitle")
        top.addWidget(self.file_label)
        top.addStretch(1)

        tools = [
            ("H1", "# "),
            ("Figura", "![Descripción](images/figura.png){#fig-id}\n"),
            ("Tabla", "| Columna | Valor |\n|---|---|\n| A | 1 |\n"),
            ("Cita", "[@clave]\n"),
            ("Ecuación", "$$\nE = mc^2\n$$\n"),
            ("Código", "\x60\x60\x60{python}\n# código\n\x60\x60\x60\n"),
            ("Nota", "::: {.callout-note}\n## Nota\nContenido\n:::\n"),
        ]

        for label, text in tools:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, value=text: self._insert_text(value)
            )
            top.addWidget(button)

        layout.addLayout(top)

        self.editor = CodeEditor()
        self.editor.textChanged.connect(self._editor_changed)
        layout.addWidget(self.editor, 1)

        return frame

    def _build_status_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("StatusBar")
        frame.setFixedHeight(28)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(9, 2, 9, 2)

        self.left_status = QLabel("Listo")
        self.left_status.setObjectName("Muted")

        self.right_status = QLabel("Quarto: comprobando…")
        self.right_status.setObjectName("Muted")
        self.right_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.left_status)
        layout.addStretch(1)
        layout.addWidget(self.right_status)

        return frame

    def _dialog_size(self, width_ratio: float = 0.82, height_ratio: float = 0.82) -> tuple[int, int]:
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen else None

        if not geometry:
            return 1000, 650

        width = min(1120, max(760, int(geometry.width() * width_ratio)))
        height = min(690, max(500, int(geometry.height() * height_ratio)))
        return width, height

    def _new_dialog(self, title: str, width_ratio: float = 0.82) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setWindowFlag(Qt.Dialog, True)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)

        width, height = self._dialog_size(width_ratio)
        dialog.resize(width, height)
        dialog.setStyleSheet(APP_STYLE)
        return dialog

    def _load_project(self, root: Path) -> None:
        self._save_current(silent=True)
        self.quarto.stop_preview()
        self._set_preview_state(False)

        if self.preview_dialog:
            self.preview_dialog.close()
        if self.bib_dialog:
            self.bib_dialog.close()
        if self.terminal_dialog:
            self.terminal_dialog.close()

        self.project_root = root.expanduser().resolve()
        self.book = BookModel(self.project_root)
        self.current_file = None

        self._loading_editor = True
        self.editor.clear()
        self._loading_editor = False

        self.file_label.setText("Selecciona un capítulo")
        self.project_label.setText(self.book.title())
        self._refresh_tree()
        self._refresh_bibliography()

        version = self.quarto.quarto_version()
        self.right_status.setText(f"Quarto {version}  •  UTF-8")

        if self.book.is_book() and self.auto_btn.isChecked():
            QTimer.singleShot(350, self._ensure_preview)

    def _refresh_tree(self) -> None:
        self.book_tree.clear()

        if not self.book.is_book():
            item = QTreeWidgetItem(["No se encontró _quarto.yml"])
            item.setFlags(Qt.NoItemFlags)
            self.book_tree.addTopLevelItem(item)
            return

        index_file = self.project_root / "index.qmd"
        if index_file.exists():
            item = QTreeWidgetItem(["Portada"])
            item.setData(0, Qt.UserRole, str(index_file))
            self.book_tree.addTopLevelItem(item)

        def add(parent: QTreeWidgetItem | None, entry: dict) -> None:
            item = QTreeWidgetItem([entry["title"]])
            path = entry.get("path")

            if path:
                item.setData(0, Qt.UserRole, str(self.project_root / path))

            if parent is None:
                self.book_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

            for child in entry.get("children", []):
                add(item, child)

        for entry in self.book.chapters():
            if entry.get("path") == "index.qmd":
                continue
            add(None, entry)

        refs = QTreeWidgetItem(["Referencias"])
        refs.setData(0, Qt.UserRole, "__bibliography__")
        self.book_tree.addTopLevelItem(refs)
        self.book_tree.expandAll()

    def _tree_item_clicked(self, item: QTreeWidgetItem) -> None:
        value = item.data(0, Qt.UserRole)
        if not value:
            return

        if value == "__bibliography__":
            self._show_bibliography_dialog()
            return

        path = Path(value)
        if path.suffix.lower() == ".qmd":
            self._open_file(path)

    def _open_file(self, path: Path) -> None:
        self._save_current(silent=True)

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo abrir", str(exc))
            return

        self._loading_editor = True
        self.current_file = path
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self._loading_editor = False

        self.dirty = False
        self.file_label.setText(path.name)

        try:
            relative = path.relative_to(self.project_root)
            self.left_status.setText(str(relative))
        except ValueError:
            self.left_status.setText(path.name)

        # Switching chapters may change the URL, but we never force a reload
        # while the user is typing.
        if self.preview_view and self.quarto.base_url:
            QTimer.singleShot(250, self._sync_preview_url)

    def _editor_changed(self) -> None:
        if self._loading_editor or not self.current_file:
            return

        self.dirty = True
        self.left_status.setText(f"{self.current_file.name}  •  escribiendo…")
        self.autosave_timer.start()

    def _autosave(self) -> None:
        self._save_current(silent=True)

        # Quarto Preview watches files itself. Do not call reload() here.
        # Its own live-reload script updates an open Preview dialog after
        # Quarto has finished rebuilding the page.
        if self.auto_btn.isChecked() and not self.quarto.is_preview_running():
            self._ensure_preview()

    def _save_current(self, _checked=False, silent: bool = False) -> None:
        if not self.current_file or not self.dirty:
            return

        try:
            self.current_file.write_text(
                self.editor.toPlainText(),
                encoding="utf-8",
            )
            self.dirty = False
            self.editor.document().setModified(False)
            self.left_status.setText(
                f"{self.current_file.name}  •  guardado"
            )

            if not silent:
                self._set_status("Guardado")

        except Exception as exc:
            if not silent:
                QMessageBox.warning(self, "Error al guardar", str(exc))

    def _insert_text(self, text: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _ensure_preview(self) -> bool:
        if not self.book.is_book():
            self._set_status("Abre una carpeta con un libro Quarto.")
            return False

        try:
            self._save_current(silent=True)
            self.quarto.start_preview(self.project_root)
            self._set_preview_state(self.quarto.is_preview_running())
            self._set_status("Quarto Preview activo")
            return True
        except Exception as exc:
            self._set_preview_state(False)
            QMessageBox.warning(self, "Quarto Preview", str(exc))
            return False

    def _preview_ready(self, _base: str) -> None:
        self._set_preview_state(True)
        self._set_status("Quarto Preview activo")
        self._sync_preview_url()

    def _preview_stopped(self) -> None:
        self._set_preview_state(False)
        self._set_status("Quarto Preview detenido")

    def _set_preview_state(self, running: bool) -> None:
        self.preview_state.setText(
            "● Preview activo" if running else "● Preview detenido"
        )
        self.preview_state.setObjectName(
            "PreviewOn" if running else "PreviewOff"
        )
        self.preview_state.style().unpolish(self.preview_state)
        self.preview_state.style().polish(self.preview_state)
        self.preview_state.update()

    def _toggle_auto_preview(self, enabled: bool) -> None:
        if enabled:
            self._ensure_preview()
            return

        self.quarto.stop_preview()
        self._set_preview_state(False)
        self._set_status("Auto Preview pausado")

    def _show_preview_dialog(self) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Preview",
                "Abre primero un proyecto Quarto Book.",
            )
            return

        if not self.quarto.is_preview_running():
            if not self.auto_btn.isChecked():
                self.auto_btn.setChecked(True)
            elif not self._ensure_preview():
                return

        if self.preview_dialog:
            self._sync_preview_url()
            self.preview_dialog.show()
            self.preview_dialog.raise_()
            self.preview_dialog.activateWindow()
            return

        dialog = self._new_dialog("ArchiTecQuart — Preview", 0.88)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel("Vista previa del libro")
        title.setObjectName("SectionTitle")

        state = QLabel("● Quarto activo")
        state.setObjectName("PreviewOn")

        reload_btn = QPushButton("↻ Recargar")
        reload_btn.clicked.connect(
            lambda: self.preview_view.reload() if self.preview_view else None
        )

        external_btn = QPushButton("↗ Navegador")
        external_btn.clicked.connect(self._open_preview_external)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.close)

        top.addWidget(title)
        top.addWidget(state)
        top.addStretch(1)
        top.addWidget(reload_btn)
        top.addWidget(external_btn)
        top.addWidget(close_btn)
        layout.addLayout(top)

        view = QWebEngineView()
        view.setZoomFactor(0.90 if self.compact else 1.0)
        view.setHtml(
            "<html><body style='font-family:sans-serif;padding:32px;color:#64748b'>"
            "<h2>Preparando vista previa…</h2>"
            "<p>Quarto Preview está ejecutándose.</p>"
            "</body></html>"
        )
        layout.addWidget(view, 1)

        self.preview_dialog = dialog
        self.preview_view = view

        def cleanup(*_args) -> None:
            self.preview_dialog = None
            self.preview_view = None

        dialog.destroyed.connect(cleanup)
        self._sync_preview_url()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _sync_preview_url(self) -> None:
        if not self.preview_view or not self.quarto.base_url:
            return

        desired = self.quarto.url_for_source(self.current_file)
        if desired and self.preview_view.url().toString() != desired:
            self.preview_view.setUrl(QUrl(desired))

    def _show_bibliography_dialog(self) -> None:
        self._refresh_bibliography()

        if self.bib_dialog:
            self.bib_dialog.show()
            self.bib_dialog.raise_()
            self.bib_dialog.activateWindow()
            return

        dialog = self._new_dialog("ArchiTecQuart — Bibliografía", 0.80)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        top = QHBoxLayout()
        title = QLabel("Bibliografía del libro")
        title.setObjectName("SectionTitle")
        count = QLabel(f"{len(self.bib_entries)} referencias")
        count.setObjectName("Muted")
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.close)

        top.addWidget(title)
        top.addWidget(count)
        top.addStretch(1)
        top.addWidget(close_btn)
        layout.addLayout(top)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Clave", "Autor", "Título", "Año", "Tipo"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        for entry in self.bib_entries:
            row = table.rowCount()
            table.insertRow(row)
            for col, key in enumerate(
                ["key", "author", "title", "year", "type"]
            ):
                table.setItem(
                    row,
                    col,
                    QTableWidgetItem(entry.get(key, "")),
                )

        layout.addWidget(table, 1)
        self.bib_dialog = dialog

        def cleanup(*_args) -> None:
            self.bib_dialog = None

        dialog.destroyed.connect(cleanup)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_logs_dialog(self) -> None:
        if self.logs_dialog:
            self.logs_dialog.show()
            self.logs_dialog.raise_()
            self.logs_dialog.activateWindow()
            return

        dialog = self._new_dialog("ArchiTecQuart — Logs", 0.78)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        top = QHBoxLayout()
        title = QLabel("Quarto / ArchiTecQuart")
        title.setObjectName("SectionTitle")

        clear_btn = QPushButton("Limpiar")
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.close)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(clear_btn)
        top.addWidget(close_btn)
        layout.addLayout(top)

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMaximumBlockCount(1500)
        view.setPlainText("\n".join(self.log_lines))
        layout.addWidget(view, 1)

        def clear_logs() -> None:
            self.log_lines.clear()
            view.clear()

        clear_btn.clicked.connect(clear_logs)

        self.logs_dialog = dialog
        self.logs_view = view

        def cleanup(*_args) -> None:
            self.logs_dialog = None
            self.logs_view = None

        dialog.destroyed.connect(cleanup)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_terminal_dialog(self) -> None:
        if self.terminal_dialog:
            self.terminal_dialog.show()
            self.terminal_dialog.raise_()
            self.terminal_dialog.activateWindow()
            return

        dialog = self._new_dialog("ArchiTecQuart — Terminal", 0.78)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)

        terminal = TerminalWidget(str(self.project_root))
        layout.addWidget(terminal, 1)

        self.terminal_dialog = dialog

        def cleanup(*_args) -> None:
            self.terminal_dialog = None

        dialog.destroyed.connect(cleanup)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _render(self, target: str | None) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Render",
                "Abre primero un proyecto Quarto Book.",
            )
            return

        try:
            self._save_current(silent=True)
            self.quarto.render(self.project_root, target)
            self._set_status(f"Renderizando {target or 'proyecto'}…")
        except Exception as exc:
            QMessageBox.warning(self, "Render", str(exc))

    def _render_finished(self, _ok: bool, message: str) -> None:
        self._set_status(message)

    def _choose_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Abrir libro Quarto",
            str(self.project_root),
        )

        if folder:
            self._load_project(Path(folder))

    def _new_chapter(self) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Nuevo capítulo",
                "Abre primero un proyecto Quarto Book.",
            )
            return

        title, ok = QInputDialog.getText(
            self,
            "Nuevo capítulo",
            "Título del capítulo:",
        )

        if not ok or not title.strip():
            return

        try:
            path = self.book.add_chapter(title.strip())
            self._refresh_tree()
            self._open_file(path)
            self._append_log(f"Capítulo creado: {path.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Nuevo capítulo", str(exc))

    def _refresh_bibliography(self) -> None:
        entries: list[dict[str, str]] = []

        for path in self.book.bibliography_files():
            entries.extend(parse_bib_file(path))

        self.bib_entries = entries

    def _open_preview_external(self) -> None:
        if not self.quarto.is_preview_running():
            if not self._ensure_preview():
                return

        url = self.quarto.url_for_source(self.current_file)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _append_log(self, text: str) -> None:
        self.log_lines.append(text)

        if len(self.log_lines) > 1500:
            self.log_lines = self.log_lines[-1500:]

        if self.logs_view:
            self.logs_view.appendPlainText(text)

    def _set_status(self, text: str) -> None:
        self.left_status.setText(text)

    def closeEvent(self, event) -> None:
        self._save_current(silent=True)
        self.quarto.shutdown()
        super().closeEvent(event)
