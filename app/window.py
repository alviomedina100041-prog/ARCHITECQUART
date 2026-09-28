from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
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
from .export_utils import copy_verified_export
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
        self.pending_export: tuple[str, Path] | None = None
        self.resume_preview_after_render = False
        self._shutting_down = False

        self.settings = QSettings("EduardoMedinaLabs", "ArchiTecQuart")
        self.recent_books: list[str] = self._read_recent_books()

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

        self.preview_panel = self._build_preview_panel()
        self.main_splitter.addWidget(self.preview_panel)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 1)

        if self.compact:
            self.main_splitter.setSizes([250, 625, 455])
        else:
            self.main_splitter.setSizes([285, 780, 500])

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
        new_book_btn.clicked.connect(lambda: self._show_overlay("new_book"))

        open_btn = QPushButton("Abrir")
        open_btn.clicked.connect(self._choose_project)

        new_btn = QPushButton("+ Cap.")
        new_btn.setToolTip("Crear un capítulo nuevo")
        new_btn.clicked.connect(lambda: self._show_overlay("new_chapter"))

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

        self.preview_btn = QPushButton("Preview ✓")
        self.preview_btn.setToolTip("Mostrar u ocultar la vista previa de la derecha")
        self.preview_btn.clicked.connect(self._toggle_preview_panel)

        bib_btn = QPushButton("Biblio")
        bib_btn.setToolTip("Bibliografía")
        bib_btn.clicked.connect(lambda: self._show_overlay("bibliography"))

        logs_btn = QPushButton("Logs")
        logs_btn.clicked.connect(lambda: self._show_overlay("logs"))

        terminal_btn = QPushButton("Terminal")
        terminal_btn.clicked.connect(lambda: self._show_overlay("terminal"))

        self.render_btn = QPushButton("▶ Render")
        self.render_btn.setObjectName("Primary")
        self.render_btn.clicked.connect(lambda: self._render(None))

        self.export_btn = QToolButton()
        self.export_btn.setText("Exportar ▾")
        export_menu = QMenu(self.export_btn)

        for label, target in [
            ("HTML", "html"),
            ("PDF", "pdf"),
            ("EPUB", "epub"),
        ]:
            action = QAction(label, export_menu)
            action.triggered.connect(
                lambda _checked=False, fmt=target: self._export(fmt)
            )
            export_menu.addAction(action)

        self.export_btn.setMenu(export_menu)
        self.export_btn.setPopupMode(QToolButton.InstantPopup)

        for widget in [
            new_book_btn,
            open_btn,
            new_btn,
            save_btn,
            self.auto_btn,
            self.preview_btn,
            bib_btn,
            logs_btn,
            terminal_btn,
            self.render_btn,
            self.export_btn,
        ]:
            layout.addWidget(widget)

        return frame

    def _build_book_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SidePanel")

        if self.compact:
            frame.setMinimumWidth(225)
            frame.setMaximumWidth(300)
        else:
            frame.setMinimumWidth(250)
            frame.setMaximumWidth(340)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)

        books_header = QHBoxLayout()
        books_title = QLabel("Mis libros")
        books_title.setObjectName("SectionTitle")

        new_book_btn = QPushButton("+ Nuevo")
        new_book_btn.setObjectName("SoftPrimary")
        new_book_btn.setToolTip("Crear un libro Quarto")
        new_book_btn.clicked.connect(lambda: self._show_overlay("new_book"))

        open_book_btn = QPushButton("Abrir")
        open_book_btn.setToolTip("Abrir un libro Quarto existente")
        open_book_btn.clicked.connect(self._choose_project)

        books_header.addWidget(books_title)
        books_header.addStretch(1)
        books_header.addWidget(new_book_btn)
        books_header.addWidget(open_book_btn)
        layout.addLayout(books_header)

        self.books_list = QListWidget()
        self.books_list.setObjectName("BooksList")
        self.books_list.setMaximumHeight(185 if self.compact else 220)
        self.books_list.itemActivated.connect(self._recent_book_activated)
        layout.addWidget(self.books_list)

        books_hint = QLabel("Doble clic o Enter para abrir un libro")
        books_hint.setObjectName("FieldHint")
        layout.addWidget(books_hint)

        chapters_header = QHBoxLayout()
        chapters_title = QLabel("Capítulos")
        chapters_title.setObjectName("SectionTitle")

        add_chapter_btn = QPushButton("+")
        add_chapter_btn.setFixedWidth(30)
        add_chapter_btn.setToolTip("Nuevo capítulo")
        add_chapter_btn.clicked.connect(lambda: self._show_overlay("new_chapter"))

        chapters_header.addWidget(chapters_title)
        chapters_header.addStretch(1)
        chapters_header.addWidget(add_chapter_btn)
        layout.addLayout(chapters_header)

        self.book_tree = QTreeWidget()
        self.book_tree.setHeaderHidden(True)
        self.book_tree.itemClicked.connect(self._tree_item_clicked)
        layout.addWidget(self.book_tree, 1)

        self._refresh_recent_books()
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
            button.setObjectName("EditorTool")
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
        frame.setMinimumWidth(330 if self.compact else 390)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Vista previa")
        title.setObjectName("SectionTitle")

        self.preview_panel_state = QLabel("● detenido")
        self.preview_panel_state.setObjectName("PreviewOff")

        reload_btn = QPushButton("↻")
        reload_btn.setObjectName("IconButton")
        reload_btn.setFixedWidth(32)
        reload_btn.setToolTip("Recargar la vista previa")
        reload_btn.clicked.connect(lambda: self.preview_view.reload())

        hide_btn = QPushButton("×")
        hide_btn.setObjectName("IconButton")
        hide_btn.setFixedWidth(32)
        hide_btn.setToolTip("Ocultar vista previa")
        hide_btn.clicked.connect(self._toggle_preview_panel)

        header.addWidget(title)
        header.addWidget(self.preview_panel_state)
        header.addStretch(1)
        header.addWidget(reload_btn)
        header.addWidget(hide_btn)
        layout.addLayout(header)

        self.preview_view = QWebEngineView()
        self.preview_view.setZoomFactor(0.82 if self.compact else 0.95)
        self.preview_view.setHtml(
            "<html><body style='font-family:sans-serif;padding:28px;color:#64748b'>"
            "<h2>Vista previa del libro</h2>"
            "<p>Crea o abre un libro Quarto para verlo aquí.</p>"
            "</body></html>"
        )
        layout.addWidget(self.preview_view, 1)
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
        overlay_heading = QVBoxLayout()
        overlay_heading.setSpacing(1)

        self.overlay_title = QLabel("Herramienta")
        self.overlay_title.setObjectName("OverlayTitle")

        self.overlay_subtitle = QLabel("")
        self.overlay_subtitle.setObjectName("OverlaySubtitle")

        overlay_heading.addWidget(self.overlay_title)
        overlay_heading.addWidget(self.overlay_subtitle)

        close_btn = QPushButton("✕ Cerrar")
        close_btn.setObjectName("OverlayClose")
        close_btn.clicked.connect(self._hide_overlay)

        header.addLayout(overlay_heading)
        header.addStretch(1)
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        self.overlay_stack = QStackedWidget()
        card_layout.addWidget(self.overlay_stack, 1)

        self.new_book_page = self._build_new_book_page()
        self.new_chapter_page = self._build_new_chapter_page()
        self.bibliography_page = self._build_bibliography_page()
        self.logs_page = self._build_logs_page()
        self.terminal_page = self._build_terminal_page()

        self.overlay_stack.addWidget(self.new_book_page)
        self.overlay_stack.addWidget(self.new_chapter_page)
        self.overlay_stack.addWidget(self.bibliography_page)
        self.overlay_stack.addWidget(self.logs_page)
        self.overlay_stack.addWidget(self.terminal_page)

        host_layout.addWidget(self.overlay_card, 1)

    def _build_new_book_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(22, 18, 22, 22)
        page_layout.addStretch(1)

        surface = QFrame()
        surface.setObjectName("FormSurface")
        surface.setMaximumWidth(720)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(10)

        title = QLabel("Crea tu libro")
        title.setObjectName("FormTitle")
        subtitle = QLabel(
            "ArchiTecQuart preparará un proyecto Quarto listo para escribir, "
            "previsualizar y exportar."
        )
        subtitle.setObjectName("FormSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        title_label = QLabel("Título del libro")
        title_label.setObjectName("FieldLabel")
        self.new_book_title = QLineEdit()
        self.new_book_title.setObjectName("FormInput")
        self.new_book_title.setPlaceholderText("Ej. Reporte de residencia profesional")
        self.new_book_title.textChanged.connect(self._suggest_book_folder)

        title_hint = QLabel("Este será el título principal que mostrará Quarto.")
        title_hint.setObjectName("FieldHint")

        author_label = QLabel("Autor")
        author_label.setObjectName("FieldLabel")
        self.new_book_author = QLineEdit()
        self.new_book_author.setObjectName("FormInput")
        self.new_book_author.setPlaceholderText("Nombre del autor (opcional)")

        folder_label = QLabel("Nombre interno")
        folder_label.setObjectName("FieldLabel")
        self.new_book_folder = QLineEdit()
        self.new_book_folder.setObjectName("FormInput")
        self.new_book_folder.setPlaceholderText("mi-libro")
        folder_hint = QLabel(
            "Se usa únicamente como nombre de la carpeta del proyecto."
        )
        folder_hint.setObjectName("FieldHint")

        location_label = QLabel("Ubicación")
        location_label.setObjectName("FieldLabel")

        location_row = QHBoxLayout()
        location_row.setSpacing(8)
        default_parent = Path.home() / "Documents"
        if not default_parent.exists():
            default_parent = Path.home()
        self.new_book_parent = default_parent

        self.new_book_location = QLineEdit(str(self.new_book_parent))
        self.new_book_location.setObjectName("FormInput")
        self.new_book_location.setReadOnly(True)

        choose_location = QPushButton("Elegir carpeta…")
        choose_location.setObjectName("Secondary")
        choose_location.clicked.connect(self._choose_new_book_parent)

        location_row.addWidget(self.new_book_location, 1)
        location_row.addWidget(choose_location)

        structure = QFrame()
        structure.setObjectName("InfoCard")
        structure_layout = QVBoxLayout(structure)
        structure_layout.setContentsMargins(12, 10, 12, 10)
        structure_layout.setSpacing(2)

        structure_title = QLabel("Se creará automáticamente")
        structure_title.setObjectName("InfoTitle")
        structure_text = QLabel(
            "Portada, capítulo de Introducción, archivo de Referencias y carpeta de imágenes."
        )
        structure_text.setObjectName("FieldHint")
        structure_text.setWordWrap(True)

        structure_layout.addWidget(structure_title)
        structure_layout.addWidget(structure_text)

        for widget in (
            title_label,
            self.new_book_title,
            title_hint,
            author_label,
            self.new_book_author,
            folder_label,
            self.new_book_folder,
            folder_hint,
            location_label,
        ):
            layout.addWidget(widget)

        layout.addLayout(location_row)
        layout.addSpacing(6)
        layout.addWidget(structure)
        layout.addSpacing(8)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.clicked.connect(self._hide_overlay)

        create_btn = QPushButton("Crear libro")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self._new_book)

        actions.addStretch(1)
        actions.addWidget(cancel_btn)
        actions.addWidget(create_btn)
        layout.addLayout(actions)

        page_layout.addWidget(surface, 0, Qt.AlignHCenter)
        page_layout.addStretch(1)
        return page

    def _build_new_chapter_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(22, 18, 22, 22)
        page_layout.addStretch(1)

        surface = QFrame()
        surface.setObjectName("FormSurface")
        surface.setMaximumWidth(620)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(10)

        title = QLabel("Nuevo capítulo")
        title.setObjectName("FormTitle")

        subtitle = QLabel(
            "Agrega un capítulo al libro activo. ArchiTecQuart lo incluirá "
            "automáticamente en la estructura de Quarto."
        )
        subtitle.setObjectName("FormSubtitle")
        subtitle.setWordWrap(True)

        field_label = QLabel("Título del capítulo")
        field_label.setObjectName("FieldLabel")

        self.new_chapter_title = QLineEdit()
        self.new_chapter_title.setObjectName("FormInput")
        self.new_chapter_title.setPlaceholderText("Ej. Marco teórico")
        self.new_chapter_title.textChanged.connect(self._update_chapter_preview)
        self.new_chapter_title.returnPressed.connect(self._new_chapter)

        self.new_chapter_preview = QLabel("Archivo: —")
        self.new_chapter_preview.setObjectName("PathPreview")

        info = QLabel(
            "El capítulo se creará como archivo .qmd y aparecerá en la lista "
            "de capítulos del libro."
        )
        info.setObjectName("FieldHint")
        info.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.clicked.connect(self._hide_overlay)

        create_btn = QPushButton("Crear capítulo")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self._new_chapter)

        actions.addStretch(1)
        actions.addWidget(cancel_btn)
        actions.addWidget(create_btn)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(field_label)
        layout.addWidget(self.new_chapter_title)
        layout.addWidget(self.new_chapter_preview)
        layout.addWidget(info)
        layout.addSpacing(8)
        layout.addLayout(actions)

        page_layout.addWidget(surface, 0, Qt.AlignHCenter)
        page_layout.addStretch(1)
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
        refresh_btn.setObjectName("Secondary")
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
        self.bib_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.bib_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.bib_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.bib_table.verticalHeader().setVisible(False)
        self.bib_table.setAlternatingRowColors(True)
        self.bib_table.setShowGrid(False)
        layout.addWidget(self.bib_table, 1)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        toolbar = QHBoxLayout()
        clear_btn = QPushButton("Limpiar")
        clear_btn.setObjectName("Secondary")
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
        if name == "new_book":
            self.overlay_title.setText("Nuevo libro Quarto")
            self.overlay_subtitle.setText("Configura un proyecto nuevo sin salir de ArchiTecQuart")
            self._reset_new_book_form()
            self.overlay_stack.setCurrentWidget(self.new_book_page)

        elif name == "new_chapter":
            if not self.book.is_book():
                QMessageBox.information(
                    self,
                    "Nuevo capítulo",
                    "Crea o abre un libro Quarto primero.",
                )
                return
            self.overlay_title.setText("Nuevo capítulo")
            self.overlay_subtitle.setText(self.book.title())
            self._reset_new_chapter_form()
            self.overlay_stack.setCurrentWidget(self.new_chapter_page)

        elif name == "bibliography":
            self.overlay_title.setText("Bibliografía")
            self.overlay_subtitle.setText("Referencias detectadas en el libro activo")
            self._populate_bibliography_table()
            self.overlay_stack.setCurrentWidget(self.bibliography_page)

        elif name == "logs":
            self.overlay_title.setText("Logs de Quarto / ArchiTecQuart")
            self.overlay_subtitle.setText("Actividad técnica, renders y mensajes de diagnóstico")
            self.overlay_stack.setCurrentWidget(self.logs_page)

        elif name == "terminal":
            self.overlay_title.setText("Terminal")
            self.overlay_subtitle.setText("Consola del proyecto actual")
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

    def _reset_new_book_form(self) -> None:
        self.new_book_title.clear()
        self.new_book_author.clear()
        self.new_book_folder.clear()

        default_parent = Path.home() / "Documents"
        if not default_parent.exists():
            default_parent = Path.home()

        self.new_book_parent = default_parent
        self.new_book_location.setText(str(default_parent))
        self.new_book_title.setFocus()

    def _reset_new_chapter_form(self) -> None:
        self.new_chapter_title.clear()
        self.new_chapter_preview.setText("Archivo: —")
        self.new_chapter_title.setFocus()

    def _update_chapter_preview(self, title: str) -> None:
        if not title.strip():
            self.new_chapter_preview.setText("Archivo: —")
            return

        filename = self.book.next_chapter_filename(title.strip())
        self.new_chapter_preview.setText(f"Archivo: {filename}")

    def _suggest_book_folder(self, title: str) -> None:
        if not title.strip():
            if not self.new_book_folder.hasFocus():
                self.new_book_folder.clear()
            return

        suggestion = BookModel.slugify(title.strip()) or "mi-libro-quarto"

        # Update the folder automatically until the user edits it manually.
        current = self.new_book_folder.text().strip()
        if (
            not current
            or current == "mi-libro-quarto"
            or not self.new_book_folder.isModified()
        ):
            self.new_book_folder.setText(suggestion)
            self.new_book_folder.setModified(False)

    def _choose_directory(self, caption: str, start: Path) -> str:
        return QFileDialog.getExistingDirectory(
            self,
            caption,
            str(start),
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontUseNativeDialog,
        )

    def _choose_save_file(
        self,
        caption: str,
        suggested: Path,
        file_filter: str,
    ) -> str:
        selected, _selected_filter = QFileDialog.getSaveFileName(
            self,
            caption,
            str(suggested),
            file_filter,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return selected

    def _choose_new_book_parent(self) -> None:
        selected = self._choose_directory(
            "Elegir dónde guardar el nuevo libro",
            self.new_book_parent,
        )
        if not selected:
            return

        self.new_book_parent = Path(selected).expanduser().resolve()
        self.new_book_location.setText(str(self.new_book_parent))

    def _new_book(self) -> None:
        title = self.new_book_title.text().strip()
        author = self.new_book_author.text().strip()
        folder_name = self.new_book_folder.text().strip()

        if not title:
            QMessageBox.information(
                self,
                "Falta el título",
                "Escribe un título para crear el libro.",
            )
            self.new_book_title.setFocus()
            return

        if not folder_name:
            folder_name = BookModel.slugify(title) or "mi-libro-quarto"
            self.new_book_folder.setText(folder_name)

        try:
            root = BookModel.create_book(
                parent=self.new_book_parent,
                title=title,
                author=author,
                folder_name=folder_name,
            )
        except FileExistsError as exc:
            QMessageBox.warning(self, "La carpeta ya existe", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo crear el libro", str(exc))
            return

        self._hide_overlay()
        self._load_project(root)
        intro = root / "01-introduccion.qmd"
        if intro.exists():
            self._open_file(intro)

        self._append_log(f"Libro creado: {root}")
        self._set_status(f"Libro creado: {root.name}")

        QMessageBox.information(
            self,
            "Libro creado",
            f"Tu libro Quarto fue creado correctamente en:\n{root}",
        )

    def _read_recent_books(self) -> list[str]:
        value = self.settings.value("recent_books", [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            return []

        books: list[str] = []
        for raw in value:
            path = Path(str(raw)).expanduser()
            if (path / "_quarto.yml").exists():
                resolved = str(path.resolve())
                if resolved not in books:
                    books.append(resolved)
        return books[:12]

    def _refresh_recent_books(self) -> None:
        if not hasattr(self, "books_list"):
            return

        self.books_list.clear()

        valid: list[str] = []
        for raw in self.recent_books:
            root = Path(raw)
            if not (root / "_quarto.yml").exists():
                continue

            model = BookModel(root)
            item = QListWidgetItem(model.title())
            item.setData(Qt.UserRole, str(root))
            self.books_list.addItem(item)
            valid.append(str(root))

        self.recent_books = valid[:12]
        self.settings.setValue("recent_books", self.recent_books)

        if not self.recent_books:
            item = QListWidgetItem("Aún no hay libros")
            item.setFlags(Qt.NoItemFlags)
            self.books_list.addItem(item)

    def _remember_book(self, root: Path) -> None:
        root = root.expanduser().resolve()
        if not (root / "_quarto.yml").exists():
            return

        value = str(root)
        self.recent_books = [
            existing for existing in self.recent_books
            if existing != value
        ]
        self.recent_books.insert(0, value)
        self.recent_books = self.recent_books[:12]
        self.settings.setValue("recent_books", self.recent_books)
        self._refresh_recent_books()

    def _recent_book_activated(self, item: QListWidgetItem) -> None:
        raw = item.data(Qt.UserRole)
        if not raw:
            return

        root = Path(str(raw))
        if not (root / "_quarto.yml").exists():
            self.recent_books = [
                existing for existing in self.recent_books
                if existing != str(root)
            ]
            self._refresh_recent_books()
            QMessageBox.information(
                self,
                "Libro no encontrado",
                "Ese libro ya no está disponible en su ubicación original.",
            )
            return

        self._load_project(root)

    def _toggle_preview_panel(self) -> None:
        if not hasattr(self, "preview_panel"):
            return

        if self.preview_panel.isVisible():
            self.preview_panel.hide()
            self.preview_btn.setText("Preview")
            return

        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Vista previa",
                "Crea o abre un libro Quarto primero.",
            )
            return

        self.preview_panel.show()
        self.preview_btn.setText("Preview ✓")
        if not self.quarto.is_preview_running() and self.auto_btn.isChecked():
            self._ensure_preview()
        self._sync_preview_url()

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
            self.project_label.setToolTip(self.book.title())
            self._remember_book(self.project_root)
        else:
            self.project_label.setText("Sin libro")
            self.project_label.setToolTip("Crea o abre un libro Quarto")

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

            help_item = QTreeWidgetItem(["Crea o abre un libro para ver sus capítulos"])
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
            self._show_overlay("new_book")
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
            "<p>Activa Auto para volver a iniciar Quarto Preview.</p>"
            "</body></html>"
        )

    def _set_preview_state(self, running: bool) -> None:
        object_name = "PreviewOn" if running else "PreviewOff"

        self.preview_state.setText(
            "● Preview activo" if running else "● Preview detenido"
        )
        self.preview_state.setObjectName(object_name)

        self.preview_panel_state.setText(
            "● activo" if running else "● detenido"
        )
        self.preview_panel_state.setObjectName(object_name)

        for label in (self.preview_state, self.preview_panel_state):
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

    def _export(self, target: str) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Exportar",
                "Crea o abre un libro Quarto primero.",
            )
            return

        title_slug = BookModel.slugify(self.book.title()) or "libro"
        documents = Path.home() / "Documents"
        if not documents.exists():
            documents = Path.home()

        destination: Path | None = None

        if target == "html":
            parent = self._choose_directory(
                "Selecciona dónde guardar la exportación HTML",
                documents,
            )
            if not parent:
                return

            destination = Path(parent) / f"{title_slug}-html"

            if destination.exists():
                answer = QMessageBox.question(
                    self,
                    "La exportación ya existe",
                    (
                        f"Ya existe:\n{destination}\n\n"
                        "¿Quieres reemplazar esa carpeta cuando termine el render?"
                    ),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

        elif target in {"pdf", "epub"}:
            extension = target
            filter_name = (
                "Documento PDF (*.pdf)"
                if target == "pdf"
                else "Libro EPUB (*.epub)"
            )
            selected = self._choose_save_file(
                f"Guardar libro como {target.upper()}",
                documents / f"{title_slug}.{extension}",
                filter_name,
            )
            if not selected:
                return

            destination = Path(selected)
            if destination.suffix.lower() != f".{extension}":
                destination = destination.with_suffix(f".{extension}")

        else:
            QMessageBox.warning(
                self,
                "Exportar",
                f"Formato no soportado: {target}",
            )
            return

        self._render(target, export_destination=destination)

    def _set_render_busy(
        self,
        busy: bool,
        label: str = "",
    ) -> None:
        self.render_btn.setEnabled(not busy)
        self.export_btn.setEnabled(not busy)
        self.render_btn.setText(
            f"⏳ {label}" if busy and label else "▶ Render"
        )

    def _resume_preview_if_needed(self) -> None:
        should_resume = self.resume_preview_after_render
        self.resume_preview_after_render = False

        if (
            should_resume
            and not self._shutting_down
            and self.book.is_book()
            and self.auto_btn.isChecked()
        ):
            QTimer.singleShot(300, self._ensure_preview)

    def _render(
        self,
        target: str | None,
        export_destination: Path | None = None,
    ) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Render",
                "Abre primero un proyecto Quarto Book.",
            )
            return

        self.pending_export = (
            (target, export_destination)
            if target and export_destination
            else None
        )

        label = target.upper() if target else "proyecto"

        try:
            self._save_current(silent=True)

            # Quarto Preview and Quarto Render should not write to the same
            # book output at the same time. Pause Preview during the render
            # and restore it afterwards when Auto is enabled.
            self.resume_preview_after_render = (
                self.auto_btn.isChecked()
                and self.quarto.is_preview_running()
            )
            if self.quarto.is_preview_running():
                self.quarto.stop_preview()

            self._set_render_busy(True, f"{label}…")
            self.quarto.render(self.project_root, target)

            if self.pending_export:
                self._set_status(f"Exportando {label}…")
            else:
                self._set_status(f"Renderizando {label}…")

        except Exception as exc:
            self.pending_export = None
            self._set_render_busy(False)
            self._resume_preview_if_needed()
            QMessageBox.warning(self, "Render", str(exc))

    def _copy_export_output(
        self,
        source: Path,
        target: str,
        destination: Path,
    ) -> Path:
        return copy_verified_export(
            source,
            target,
            destination,
        )

    def _show_output_location(
        self,
        title: str,
        message: str,
        output: Path,
    ) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setInformativeText(f"Guardado en:\n{output}")

        open_button = box.addButton(
            "Abrir carpeta",
            QMessageBox.ButtonRole.ActionRole,
        )
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()

        if box.clickedButton() is open_button:
            folder = output if output.is_dir() else output.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _render_finished(
        self,
        ok: bool,
        message: str,
        output_path: str,
    ) -> None:
        pending = self.pending_export
        self.pending_export = None
        self._set_render_busy(False)
        self._resume_preview_if_needed()

        if not ok:
            self._set_status(
                "Exportación fallida" if pending else "Render fallido"
            )
            QMessageBox.critical(
                self,
                "No se pudo exportar" if pending else "Render fallido",
                message,
            )
            return

        if pending:
            if not output_path:
                self._set_status("Exportación sin archivo")
                QMessageBox.critical(
                    self,
                    "No se generó la exportación",
                    (
                        "Quarto terminó, pero no produjo un archivo nuevo "
                        "para esta exportación. No se guardó nada."
                    ),
                )
                return

            target, destination = pending
            source = Path(output_path)

            try:
                final_output = self._copy_export_output(
                    source,
                    target,
                    destination,
                )
            except Exception as exc:
                self._set_status("No se pudo verificar la exportación")
                QMessageBox.critical(
                    self,
                    "No se pudo guardar la exportación",
                    (
                        "ArchiTecQuart no marcó la operación como exitosa "
                        "porque el resultado no pasó la verificación.\n\n"
                        f"{exc}"
                    ),
                )
                return

            self._set_status(
                f"{target.upper()} exportado: {final_output.name}"
            )
            self._show_output_location(
                "Exportación verificada",
                (
                    f"El libro se generó y verificó correctamente "
                    f"como {target.upper()}."
                ),
                final_output,
            )
            return

        self._set_status(message)

        if output_path:
            self._show_output_location(
                "Render completado",
                message,
                Path(output_path),
            )
        else:
            QMessageBox.information(
                self,
                "Render completado",
                message,
            )

    def _choose_project(self) -> None:
        start = self.project_root if self.book.is_book() else Path.home()
        folder = self._choose_directory(
            "Abrir libro Quarto",
            start,
        )
        if not folder:
            return

        root = Path(folder)
        if not (root / "_quarto.yml").exists():
            QMessageBox.information(
                self,
                "No es un libro Quarto",
                "La carpeta seleccionada no contiene un archivo _quarto.yml.",
            )
            return

        self._load_project(root)

    def _new_chapter(self) -> None:
        if not self.book.is_book():
            QMessageBox.information(
                self,
                "Nuevo capítulo",
                "Crea o abre un libro Quarto primero.",
            )
            return

        title = self.new_chapter_title.text().strip()
        if not title:
            self.new_chapter_title.setFocus()
            return

        try:
            path = self.book.add_chapter(title)
            self._hide_overlay()
            self._refresh_tree()
            self._open_file(path)
            self._append_log(f"Capítulo creado: {path.name}")
            self._set_status(f"Capítulo creado: {path.name}")
        except Exception as exc:
            QMessageBox.warning(self, "Nuevo capítulo", str(exc))

    def _set_status(self, text: str) -> None:
        self.left_status.setText(text)

    def shutdown(self) -> None:
        if self._shutting_down:
            return

        self._shutting_down = True
        self.autosave_timer.stop()
        self.resume_preview_after_render = False

        if hasattr(self, "preview_view"):
            self.preview_view.stop()

        if self.terminal_widget is not None:
            try:
                self.terminal_widget.shutdown()
            except AttributeError:
                pass
            self.terminal_widget = None

        self.quarto.shutdown()

    def closeEvent(self, event) -> None:
        self._save_current(silent=True)
        self.shutdown()
        super().closeEvent(event)
