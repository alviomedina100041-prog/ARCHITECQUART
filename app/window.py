from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
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
    QTabWidget,
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
        self.quarto.preview_stopped.connect(
            lambda: self._set_status("Preview detenido")
        )
        self.quarto.render_finished.connect(self._render_finished)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(900)
        self.autosave_timer.timeout.connect(self._autosave)

        self.reload_timer = QTimer(self)
        self.reload_timer.setSingleShot(True)
        self.reload_timer.setInterval(1500)
        self.reload_timer.timeout.connect(self._reload_preview)

        self._build_ui()
        self.setStyleSheet(APP_STYLE)
        self._load_project(self.project_root)

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(7, 7, 7, 7)
        outer.setSpacing(6)

        outer.addWidget(self._build_top_bar())

        vertical = QSplitter(Qt.Vertical)
        horizontal = QSplitter(Qt.Horizontal)
        horizontal.setChildrenCollapsible(False)

        horizontal.addWidget(self._build_book_panel())
        horizontal.addWidget(self._build_editor_panel())
        horizontal.addWidget(self._build_preview_panel())

        if self.compact:
            horizontal.setSizes([225, 610, 485])
        else:
            horizontal.setSizes([270, 760, 560])

        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setStretchFactor(2, 1)

        vertical.addWidget(horizontal)
        vertical.addWidget(self._build_bottom_panel())
        vertical.setSizes([565, 150] if self.compact else [690, 190])
        vertical.setStretchFactor(0, 1)
        vertical.setStretchFactor(1, 0)

        outer.addWidget(vertical, 1)
        outer.addWidget(self._build_status_bar())
        self.setCentralWidget(central)

    def _build_top_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("TopBar")
        frame.setFixedHeight(50 if self.compact else 62)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(11, 6, 11, 6)
        layout.setSpacing(6)

        title = QLabel("▣  ArchiTecQuart")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.project_label = QLabel("Sin libro")
        self.project_label.setObjectName("Muted")
        layout.addWidget(self.project_label)
        layout.addStretch(1)

        open_btn = QPushButton("Abrir")
        open_btn.clicked.connect(self._choose_project)

        new_btn = QPushButton("+ Capítulo")
        new_btn.clicked.connect(self._new_chapter)

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self._save_current)

        self.auto_btn = QPushButton("Auto Preview")
        self.auto_btn.setCheckable(True)
        self.auto_btn.setChecked(True)
        self.auto_btn.setToolTip(
            "Quarto Preview se inicia una sola vez. "
            "El editor guarda con debounce y la vista se recarga sin reiniciar Quarto."
        )
        self.auto_btn.toggled.connect(self._toggle_auto_preview)

        render_btn = QPushButton("▶ Render")
        render_btn.setObjectName("Primary")
        render_btn.clicked.connect(lambda: self._render(None))

        preview_btn = QPushButton("◉ Preview")
        preview_btn.clicked.connect(self._ensure_preview)

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
            render_btn,
            preview_btn,
            export_btn,
        ]:
            layout.addWidget(widget)

        return frame

    def _build_book_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SidePanel")
        frame.setMinimumWidth(195)
        frame.setMaximumWidth(285)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Estructura del libro")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.book_tree = QTreeWidget()
        self.book_tree.setHeaderHidden(True)
        self.book_tree.itemClicked.connect(self._tree_item_clicked)
        layout.addWidget(self.book_tree, 1)

        return frame

    def _build_editor_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("EditorPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

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

    def _build_preview_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PreviewPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        top = QHBoxLayout()
        title = QLabel("Vista previa")
        title.setObjectName("SectionTitle")
        top.addWidget(title)
        top.addStretch(1)

        reload_btn = QPushButton("↻")
        reload_btn.setFixedWidth(30)
        reload_btn.setToolTip("Recargar vista")
        reload_btn.clicked.connect(self._reload_preview)

        external_btn = QPushButton("↗")
        external_btn.setFixedWidth(30)
        external_btn.setToolTip("Abrir preview en navegador")
        external_btn.clicked.connect(self._open_preview_external)

        top.addWidget(reload_btn)
        top.addWidget(external_btn)
        layout.addLayout(top)

        self.preview = QWebEngineView()
        self.preview.setZoomFactor(0.82 if self.compact else 1.0)
        self.preview.setHtml(
            "<html><body style='font-family:sans-serif;padding:40px;color:#64748b'>"
            "<h2>Vista previa de Quarto</h2>"
            "<p>Abre un libro Quarto para iniciar el preview automático.</p>"
            "</body></html>"
        )
        layout.addWidget(self.preview, 1)

        return frame

    def _build_bottom_panel(self) -> QWidget:
        self.bottom_tabs = QTabWidget()

        self.bib_table = QTableWidget(0, 5)
        self.bib_table.setHorizontalHeaderLabels(
            ["Clave", "Autor", "Título", "Año", "Tipo"]
        )
        self.bib_table.horizontalHeader().setStretchLastSection(True)
        self.bottom_tabs.addTab(self.bib_table, "Bibliografía")

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(1200)
        self.bottom_tabs.addTab(self.logs, "Logs")

        self.terminal = TerminalWidget(str(self.project_root))
        self.bottom_tabs.addTab(self.terminal, "Terminal")

        return self.bottom_tabs

    def _build_status_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("StatusBar")
        frame.setFixedHeight(27)

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

    def _load_project(self, root: Path) -> None:
        self._save_current(silent=True)
        self.quarto.stop_preview()

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
            QTimer.singleShot(250, self._ensure_preview)

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

        def add(parent, entry: dict) -> None:
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
            self.bottom_tabs.setCurrentIndex(0)
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

        if self.quarto.base_url:
            QTimer.singleShot(250, self._show_current_preview)

    def _editor_changed(self) -> None:
        if self._loading_editor or not self.current_file:
            return

        self.dirty = True
        self.left_status.setText(f"{self.current_file.name}  •  sin guardar")
        self.autosave_timer.start()

    def _autosave(self) -> None:
        self._save_current(silent=True)

        if self.auto_btn.isChecked():
            if not self.quarto.base_url:
                self._ensure_preview()
            else:
                self.reload_timer.start()

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

    def _ensure_preview(self) -> None:
        if not self.book.is_book():
            self._set_status("Abre una carpeta con un libro Quarto.")
            return

        try:
            self._save_current(silent=True)
            self.quarto.start_preview(self.project_root)
            self._set_status("Preview automático activo")
        except Exception as exc:
            QMessageBox.warning(self, "Quarto Preview", str(exc))

    def _preview_ready(self, _base: str) -> None:
        self._show_current_preview()
        self._set_status("Quarto Preview activo")

    def _show_current_preview(self) -> None:
        url = self.quarto.url_for_source(self.current_file)
        if url:
            self.preview.setUrl(QUrl(url))

    def _reload_preview(self) -> None:
        if not self.quarto.base_url:
            return

        desired = self.quarto.url_for_source(self.current_file)
        if desired and self.preview.url().toString() != desired:
            self.preview.setUrl(QUrl(desired))
        else:
            self.preview.reload()

    def _toggle_auto_preview(self, enabled: bool) -> None:
        if enabled:
            self._ensure_preview()
            return

        self.reload_timer.stop()
        self._set_status(
            "Auto Preview pausado; usa Preview cuando quieras refrescar."
        )

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
            self.bottom_tabs.setCurrentIndex(1)
            self._set_status(f"Renderizando {target or 'proyecto'}…")
        except Exception as exc:
            QMessageBox.warning(self, "Render", str(exc))

    def _render_finished(self, ok: bool, message: str) -> None:
        self._set_status(message)
        if ok and self.auto_btn.isChecked():
            self.reload_timer.start(500)

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
        entries = []
        for path in self.book.bibliography_files():
            entries.extend(parse_bib_file(path))

        self.bib_table.setRowCount(0)

        for entry in entries:
            row = self.bib_table.rowCount()
            self.bib_table.insertRow(row)

            for col, key in enumerate(
                ["key", "author", "title", "year", "type"]
            ):
                self.bib_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(entry.get(key, "")),
                )

    def _open_preview_external(self) -> None:
        url = self.quarto.url_for_source(self.current_file)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _append_log(self, text: str) -> None:
        self.logs.appendPlainText(text)

    def _set_status(self, text: str) -> None:
        self.left_status.setText(text)

    def closeEvent(self, event) -> None:
        self._save_current(silent=True)
        self.quarto.shutdown()
        super().closeEvent(event)
