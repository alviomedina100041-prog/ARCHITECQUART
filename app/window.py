from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeView,
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
        self.terminal_widget: TerminalWidget | None = None

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

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(2500)
        self.autosave_timer.timeout.connect(self._autosave)

        self._build_ui()
        self.setStyleSheet(APP_STYLE)

        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.escape_shortcut.activated.connect(self._hide_overlay)

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

        self._build_overlay(central)
        self._resize_overlay()

    def _build_top_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("TopBar")
        frame.setFixedHeight(52 if self.compact else 62)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        icon_label = QLabel()
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        26,
                        26,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
        icon_label.setFixedSize(30, 30)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("ArchiTecQuart")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.project_label = QLabel("Sin libro")
        self.project_label.setObjectName("Muted")
        self.project_label.setMaximumWidth(135 if self.compact else 230)
        layout.addWidget(self.project_label)
        layout.addStretch(1)

        self.preview_state = QLabel("● Preview detenido")
        self.preview_state.setObjectName("PreviewOff")
        layout.addWidget(self.preview_state)

        new_book_btn = QPushButton("+ Libro")
        new_book_btn.setToolTip("Crear un libro Quarto nuevo")
        new_book_btn.clicked.connect(self._new_book)

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
        preview_btn.clicked.connect(lambda: self._show_overlay("preview"))

        bib_btn = QPushButton("Biblio")
        bib_btn.setToolTip("Bibliografía")
        bib_btn.clicked.connect(lambda: self._show_overlay("bibliography"))

        logs_btn = QPushButton("Logs")
        logs_btn.clicked.connect(lambda: self._show_overlay("logs"))

        terminal_btn = QPushButton("Terminal")
        terminal_btn.clicked.connect(lambda: self._show_overlay("terminal"))

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
            new_book_btn,
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
            frame.setMinimumWidth(270)
            frame.setMaximumWidth(360)
        else:
            frame.setMinimumWidth(300)
            frame.setMaximumWidth(420)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)

        self.left_tabs = QTabWidget()
        self.left_tabs.setDocumentMode(True)

        book_page = QWidget()
        book_layout = QVBoxLayout(book_page)
        book_layout.setContentsMargins(2, 2, 2, 2)
        book_layout.setSpacing(6)

        book_header = QHBoxLayout()
        title = QLabel("Estructura del libro")
        title.setObjectName("SectionTitle")

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.setToolTip("Nuevo capítulo")
        add_btn.clicked.connect(self._new_chapter)

        book_header.addWidget(title)
        book_header.addStretch(1)
        book_header.addWidget(add_btn)
        book_layout.addLayout(book_header)

        self.book_tree = QTreeWidget()
        self.book_tree.setHeaderHidden(True)
        self.book_tree.itemClicked.connect(self._tree_item_clicked)
        book_layout.addWidget(self.book_tree, 1)

        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        files_layout.setContentsMargins(2, 2, 2, 2)
        files_layout.setSpacing(6)

        file_header = QHBoxLayout()
        self.files_path_label = QLabel(str(Path.home()))
        self.files_path_label.setObjectName("Muted")
        self.files_path_label.setToolTip(str(Path.home()))

        home_btn = QPushButton("Home")
        home_btn.setFixedWidth(52)
        home_btn.clicked.connect(self._show_home_files)

        project_btn = QPushButton("Proyecto")
        project_btn.setFixedWidth(65)
        project_btn.clicked.connect(self._show_project_files)

        file_header.addWidget(self.files_path_label, 1)
        file_header.addWidget(home_btn)
        file_header.addWidget(project_btn)
        files_layout.addLayout(file_header)

        self.file_model = QFileSystemModel(self)
        self.file_model.setReadOnly(True)
        self.file_model.setRootPath(str(Path.home()))

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(Path.home())))
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setIndentation(16)
        for column in range(1, 4):
            self.file_tree.hideColumn(column)
        self.file_tree.doubleClicked.connect(self._file_tree_double_clicked)
        files_layout.addWidget(self.file_tree, 1)

        self.left_tabs.addTab(book_page, "Libro")
        self.left_tabs.addTab(files_page, "Archivos")
        layout.addWidget(self.left_tabs, 1)

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

    def _build_overlay(self, parent: QWidget) -> None:
        self.overlay_host = QFrame(parent)
        self.overlay_host.setObjectName("OverlayBackdrop")
        self.overlay_host.hide()

        host_layout = QVBoxLayout(self.overlay_host)
        host_layout.setContentsMargins(
            42 if self.compact else 70,
            48 if self.compact else 70,
            42 if self.compact else 70,
            38 if self.compact else 60,
        )

        self.overlay_card = QFrame()
        self.overlay_card.setObjectName("OverlayCard")
        card_layout = QVBoxLayout(self.overlay_card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        self.overlay_title = QLabel("Herramienta")
        self.overlay_title.setObjectName("OverlayTitle")

        close_btn = QPushButton("✕ Cerrar")
        close_btn.setObjectName("OverlayClose")
        close_btn.clicked.connect(self._hide_overlay)

        header.addWidget(self.overlay_title)
        header.addStretch(1)
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        self.overlay_stack = QStackedWidget()
        card_layout.addWidget(self.overlay_stack, 1)

        self.preview_page = self._build_preview_page()
        self.bibliography_page = self._build_bibliography_page()
        self.logs_page = self._build_logs_page()
        self.terminal_page = self._build_terminal_page()

        self.overlay_stack.addWidget(self.preview_page)
        self.overlay_stack.addWidget(self.bibliography_page)
        self.overlay_stack.addWidget(self.logs_page)
        self.overlay_stack.addWidget(self.terminal_page)

        host_layout.addWidget(self.overlay_card, 1)

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        toolbar = QHBoxLayout()
        self.preview_overlay_state = QLabel("● Preview detenido")
        self.preview_overlay_state.setObjectName("PreviewOff")

        reload_btn = QPushButton("↻ Recargar")
        reload_btn.clicked.connect(self.preview_view.reload if hasattr(self, "preview_view") else lambda: None)

        toolbar.addWidget(self.preview_overlay_state)
        toolbar.addStretch(1)
        toolbar.addWidget(reload_btn)
        layout.addLayout(toolbar)

        self.preview_view = QWebEngineView()
        self.preview_view.setZoomFactor(0.90 if self.compact else 1.0)
        self.preview_view.setHtml(
            "<html><body style='font-family:sans-serif;padding:32px;color:#64748b'>"
            "<h2>Vista previa de Quarto</h2>"
            "<p>Activa Auto Preview o pulsa Preview para iniciar.</p>"
            "</body></html>"
        )
        reload_btn.clicked.disconnect()
        reload_btn.clicked.connect(self.preview_view.reload)
        layout.addWidget(self.preview_view, 1)
        return page

    def _build_bibliography_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        info = QHBoxLayout()
        self.bib_count = QLabel("0 referencias")
        self.bib_count.setObjectName("Muted")

        refresh_btn = QPushButton("↻ Actualizar")
        refresh_btn.clicked.connect(self._populate_bibliography_table)

        info.addWidget(self.bib_count)
        info.addStretch(1)
        info.addWidget(refresh_btn)
        layout.addLayout(info)

        self.bib_table = QTableWidget(0, 5)
        self.bib_table.setHorizontalHeaderLabels(
            ["Clave", "Autor", "Título", "Año", "Tipo"]
        )
        self.bib_table.horizontalHeader().setStretchLastSection(True)
        self.bib_table.verticalHeader().setVisible(False)
        layout.addWidget(self.bib_table, 1)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        toolbar = QHBoxLayout()
        clear_btn = QPushButton("Limpiar")
        clear_btn.clicked.connect(self._clear_logs)
        toolbar.addStretch(1)
        toolbar.addWidget(clear_btn)
        layout.addLayout(toolbar)

        self.logs_view = QPlainTextEdit()
        self.logs_view.setReadOnly(True)
        self.logs_view.setMaximumBlockCount(1500)
        layout.addWidget(self.logs_view, 1)
        return page

    def _build_terminal_page(self) -> QWidget:
        page = QWidget()
        self.terminal_layout = QVBoxLayout(page)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)

        self.terminal_placeholder = QLabel(
            "La terminal se inicia cuando abras esta sección por primera vez."
        )
        self.terminal_placeholder.setObjectName("Muted")
        self.terminal_placeholder.setAlignment(Qt.AlignCenter)
        self.terminal_layout.addWidget(self.terminal_placeholder, 1)
        return page

    def _show_overlay(self, name: str) -> None:
        if name == "preview":
            if not self.book.is_book():
                QMessageBox.information(self, "Preview", "Abre primero un proyecto Quarto Book.")
                return

            if not self.quarto.is_preview_running():
                if not self.auto_btn.isChecked():
                    self.auto_btn.blockSignals(True)
                    self.auto_btn.setChecked(True)
                    self.auto_btn.blockSignals(False)
                if not self._ensure_preview():
                    return

            self.overlay_title.setText("Vista previa del libro")
            self.overlay_stack.setCurrentWidget(self.preview_page)
            self._sync_preview_url()

        elif name == "bibliography":
            self.overlay_title.setText("Bibliografía")
            self._populate_bibliography_table()
            self.overlay_stack.setCurrentWidget(self.bibliography_page)

        elif name == "logs":
            self.overlay_title.setText("Logs de Quarto / ArchiTecQuart")
            self.overlay_stack.setCurrentWidget(self.logs_page)

        elif name == "terminal":
            self.overlay_title.setText("Terminal")
            self._ensure_terminal_widget()
            self.overlay_stack.setCurrentWidget(self.terminal_page)

        else:
            return

        self.overlay_host.show()
        self.overlay_host.raise_()
        self.overlay_host.setFocus()

    def _hide_overlay(self) -> None:
        if hasattr(self, "overlay_host"):
            self.overlay_host.hide()

    def _resize_overlay(self) -> None:
        if hasattr(self, "overlay_host") and self.centralWidget():
            self.overlay_host.setGeometry(self.centralWidget().rect())
            if self.overlay_host.isVisible():
                self.overlay_host.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_overlay()

    def _ensure_terminal_widget(self) -> None:
        if self.terminal_widget is not None:
            return
        self.terminal_placeholder.hide()
        self.terminal_widget = TerminalWidget(str(self.project_root))
        self.terminal_layout.addWidget(self.terminal_widget, 1)

    def _reset_terminal_widget(self) -> None:
        if self.terminal_widget is None:
            return
        try:
            self.terminal_widget.shutdown()
        except AttributeError:
            pass
        self.terminal_widget.deleteLater()
        self.terminal_widget = None
        self.terminal_placeholder.show()

    def _new_book(self) -> None:
        parent = QFileDialog.getExistingDirectory(
            self,
            "Dónde crear el nuevo libro",
            str(Path.home()),
        )
        if not parent:
            return

        title, ok = QInputDialog.getText(
            self,
            "Nuevo libro Quarto",
            "Título del libro:",
        )
        if not ok or not title.strip():
            return

        default_folder = BookModel.slugify(title.strip()) or "mi-libro-quarto"
        folder_name, ok = QInputDialog.getText(
            self,
            "Carpeta del libro",
            "Nombre de la carpeta:",
            QLineEdit.Normal,
            default_folder,
        )
        if not ok or not folder_name.strip():
            return

        author, ok = QInputDialog.getText(
            self,
            "Autor",
            "Autor (opcional):",
        )
        if not ok:
            return

        try:
            root = BookModel.create_book(
                parent=parent,
                title=title.strip(),
                author=author.strip(),
                folder_name=folder_name.strip(),
            )
        except FileExistsError as exc:
            QMessageBox.warning(self, "La carpeta ya existe", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo crear el libro", str(exc))
            return

        self._load_project(root)
        self.left_tabs.setCurrentIndex(0)

        intro = root / "01-introduccion.qmd"
        if intro.exists():
            self._open_file(intro)

        self._append_log(f"Libro creado: {root}")
        QMessageBox.information(
            self,
            "Libro creado",
            f"Tu libro Quarto fue creado en:\n{root}",
        )

    def _show_files_root(self, root: Path) -> None:
        root = root.expanduser().resolve()
        if not root.exists():
            return
        self.file_model.setRootPath(str(root))
        self.file_tree.setRootIndex(self.file_model.index(str(root)))
        display = str(root)
        home = str(Path.home())
        if display == home:
            display = "~"
        elif display.startswith(home + "/"):
            display = "~" + display[len(home):]
        self.files_path_label.setText(display)
        self.files_path_label.setToolTip(str(root))

    def _show_home_files(self) -> None:
        self._show_files_root(Path.home())
        self.left_tabs.setCurrentIndex(1)

    def _show_project_files(self) -> None:
        self._show_files_root(self.project_root)
        self.left_tabs.setCurrentIndex(1)

    def _find_book_root(self, path: Path) -> Path | None:
        candidate = path if path.is_dir() else path.parent
        home = Path.home().resolve()

        while True:
            if (candidate / "_quarto.yml").exists():
                return candidate
            if candidate == candidate.parent:
                break
            if candidate == home.parent:
                break
            candidate = candidate.parent

        return None

    def _file_tree_double_clicked(self, index) -> None:
        path = Path(self.file_model.filePath(index))
        if path.is_dir():
            return

        if path.name == "_quarto.yml":
            self._load_project(path.parent)
            self.left_tabs.setCurrentIndex(0)
            return

        if path.suffix.lower() != ".qmd":
            return

        root = self._find_book_root(path)
        if root and root != self.project_root:
            self._load_project(root)

        self._open_file(path)

    def _load_project(self, root: Path) -> None:
        self._save_current(silent=True)
        self._hide_overlay()
        self.quarto.stop_preview()
        self._set_preview_state(False)
        self._reset_terminal_widget()

        self.project_root = root.expanduser().resolve()
        self.book = BookModel(self.project_root)
        self.current_file = None

        self._loading_editor = True
        self.editor.clear()
        self._loading_editor = False

        self.file_label.setText("Selecciona un capítulo")

        if self.book.is_book():
            self.project_label.setText(self.book.title())
            self.project_label.setToolTip(str(self.project_root))
            self.left_tabs.setCurrentIndex(0)
        else:
            display = str(self.project_root)
            home = str(Path.home())
            if display == home:
                display = "~"
            elif display.startswith(home + "/"):
                display = "~" + display[len(home):]
            self.project_label.setText(display)
            self.project_label.setToolTip(str(self.project_root))
            self.left_tabs.setCurrentIndex(1)

        self._show_files_root(
            self.project_root if self.book.is_book() else Path.home()
        )
        self._refresh_tree()
        self._refresh_bibliography()

        version = self.quarto.quarto_version()
        self.right_status.setText(f"Quarto {version}  •  UTF-8")

        if self.book.is_book() and self.auto_btn.isChecked():
            QTimer.singleShot(350, self._ensure_preview)

    def _refresh_tree(self) -> None:
        self.book_tree.clear()

        if not self.book.is_book():
            create_item = QTreeWidgetItem(["+ Crear un libro Quarto"])
            create_item.setData(0, Qt.UserRole, "__new_book__")
            self.book_tree.addTopLevelItem(create_item)

            help_item = QTreeWidgetItem(["Usa Archivos para navegar tu sistema"])
            help_item.setFlags(Qt.NoItemFlags)
            self.book_tree.addTopLevelItem(help_item)
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
        if value == "__new_book__":
            self._new_book()
            return
        if value == "__bibliography__":
            self._show_overlay("bibliography")
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
            self.left_status.setText(str(path.relative_to(self.project_root)))
        except ValueError:
            self.left_status.setText(path.name)

        if self.quarto.base_url:
            QTimer.singleShot(250, self._sync_preview_url)

    def _editor_changed(self) -> None:
        if self._loading_editor or not self.current_file:
            return
        self.dirty = True
        self.left_status.setText(f"{self.current_file.name}  •  escribiendo…")
        self.autosave_timer.start()

    def _autosave(self) -> None:
        self._save_current(silent=True)
        if self.auto_btn.isChecked() and not self.quarto.is_preview_running():
            self._ensure_preview()

    def _save_current(self, _checked=False, silent: bool = False) -> None:
        if not self.current_file or not self.dirty:
            return
        try:
            self.current_file.write_text(self.editor.toPlainText(), encoding="utf-8")
            self.dirty = False
            self.editor.document().setModified(False)
            self.left_status.setText(f"{self.current_file.name}  •  guardado")
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
        self.preview_view.setHtml(
            "<html><body style='font-family:sans-serif;padding:32px;color:#64748b'>"
            "<h2>Preview detenido</h2>"
            "<p>Activa Auto o pulsa Preview para volver a iniciar Quarto.</p>"
            "</body></html>"
        )

    def _set_preview_state(self, running: bool) -> None:
        text = "● Preview activo" if running else "● Preview detenido"
        object_name = "PreviewOn" if running else "PreviewOff"
        for label in (self.preview_state, self.preview_overlay_state):
            label.setText(text)
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    def _toggle_auto_preview(self, enabled: bool) -> None:
        if enabled:
            self._ensure_preview()
            return
        self.quarto.stop_preview()
        self._set_preview_state(False)
        self._set_status("Auto Preview pausado")

    def _sync_preview_url(self) -> None:
        if not self.quarto.base_url:
            return
        desired = self.quarto.url_for_source(self.current_file)
        if desired and self.preview_view.url().toString() != desired:
            self.preview_view.setUrl(QUrl(desired))

    def _refresh_bibliography(self) -> None:
        entries: list[dict[str, str]] = []
        for path in self.book.bibliography_files():
            entries.extend(parse_bib_file(path))
        self.bib_entries = entries

    def _populate_bibliography_table(self) -> None:
        self._refresh_bibliography()
        self.bib_count.setText(f"{len(self.bib_entries)} referencias")
        self.bib_table.setRowCount(0)
        for entry in self.bib_entries:
            row = self.bib_table.rowCount()
            self.bib_table.insertRow(row)
            for col, key in enumerate(["key", "author", "title", "year", "type"]):
                self.bib_table.setItem(row, col, QTableWidgetItem(entry.get(key, "")))

    def _append_log(self, text: str) -> None:
        self.log_lines.append(text)
        if len(self.log_lines) > 1500:
            self.log_lines = self.log_lines[-1500:]
        if hasattr(self, "logs_view"):
            self.logs_view.appendPlainText(text)

    def _clear_logs(self) -> None:
        self.log_lines.clear()
        self.logs_view.clear()

    def _render(self, target: str | None) -> None:
        if not self.book.is_book():
            QMessageBox.information(self, "Render", "Abre primero un proyecto Quarto Book.")
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
        folder = QFileDialog.getExistingDirectory(self, "Abrir libro Quarto", str(self.project_root))
        if folder:
            self._load_project(Path(folder))

    def _new_chapter(self) -> None:
        if not self.book.is_book():
            QMessageBox.information(self, "Nuevo capítulo", "Abre primero un proyecto Quarto Book.")
            return

        title, ok = QInputDialog.getText(self, "Nuevo capítulo", "Título del capítulo:")
        if not ok or not title.strip():
            return

        try:
            path = self.book.add_chapter(title.strip())
            self._refresh_tree()
            self._open_file(path)
            self._append_log(f"Capítulo creado: {path.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Nuevo capítulo", str(exc))

    def _set_status(self, text: str) -> None:
        self.left_status.setText(text)

    def closeEvent(self, event) -> None:
        self._save_current(silent=True)
        if self.terminal_widget is not None:
            try:
                self.terminal_widget.shutdown()
            except AttributeError:
                pass
        self.quarto.shutdown()
        super().closeEvent(event)
