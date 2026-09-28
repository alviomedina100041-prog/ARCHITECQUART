APP_STYLE = r"""
QWidget {
    background: #ffffff;
    color: #172033;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 11px;
}

QMainWindow {
    background: #f4f7fb;
}

QFrame#TopBar,
QFrame#SidePanel,
QFrame#EditorPanel,
QFrame#PreviewPanel,
QFrame#StatusBar,
QFrame#OverlayCard {
    background: #ffffff;
    border: 1px solid #dbe3ee;
    border-radius: 10px;
}

QFrame#TopBar {
    background: #fbfdff;
}

QFrame#StatusBar {
    background: #f8fafc;
}

QLabel#AppTitle {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
}

QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #1e293b;
}

QLabel#Muted {
    color: #718096;
    font-size: 10px;
}

QLabel#FieldLabel {
    color: #243248;
    font-size: 11px;
    font-weight: 700;
    padding-top: 3px;
}

QLabel#FieldHint {
    color: #7a8a9f;
    font-size: 10px;
}

QLabel#FormTitle {
    color: #0f172a;
    font-size: 20px;
    font-weight: 700;
}

QLabel#FormSubtitle {
    color: #64748b;
    font-size: 11px;
}

QLabel#PathPreview {
    background: #f8fafc;
    color: #52637a;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    padding: 7px 9px;
    font-family: "JetBrains Mono", "Noto Sans Mono", "DejaVu Sans Mono", monospace;
    font-size: 10px;
}

QLabel#InfoTitle {
    color: #334155;
    font-weight: 700;
    font-size: 11px;
}

QFrame#InfoCard {
    background: #f8fafc;
    border: 1px solid #dce4ee;
    border-radius: 9px;
}

QFrame#FormSurface {
    background: #ffffff;
    border: 1px solid #d8e1ec;
    border-radius: 14px;
}

QFrame#OverlayBackdrop {
    background-color: rgba(15, 23, 42, 118);
    border: none;
}

QFrame#OverlayCard {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 15px;
}

QLabel#OverlayTitle {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
}

QLabel#OverlaySubtitle {
    color: #7a8a9f;
    font-size: 10px;
}

QPushButton,
QToolButton {
    background: #ffffff;
    color: #263449;
    border: 1px solid #d3dce8;
    border-radius: 7px;
    padding: 5px 9px;
    min-height: 21px;
}

QPushButton:hover,
QToolButton:hover {
    background: #f3f8ff;
    border-color: #79b8f7;
    color: #0b65bd;
}

QPushButton:pressed,
QToolButton:pressed {
    background: #e8f2ff;
    border-color: #4d9de8;
}

QPushButton:disabled,
QToolButton:disabled {
    background: #f8fafc;
    color: #a7b2c2;
    border-color: #e5eaf0;
}

QPushButton#Primary,
QToolButton#Primary {
    background: #1489f5;
    color: #ffffff;
    border-color: #1489f5;
    font-weight: 700;
    padding-left: 13px;
    padding-right: 13px;
}

QPushButton#Primary:hover,
QToolButton#Primary:hover {
    background: #0877dd;
    border-color: #0877dd;
    color: #ffffff;
}

QPushButton#SoftPrimary {
    background: #eff6ff;
    color: #0b6bd3;
    border-color: #bfdbfe;
    font-weight: 700;
}

QPushButton#SoftPrimary:hover {
    background: #dbeafe;
    border-color: #93c5fd;
}

QPushButton#Secondary {
    background: #f8fafc;
    color: #475569;
    border-color: #d7e0ea;
}

QPushButton#Secondary:hover {
    background: #f1f5f9;
    color: #1e3a5f;
    border-color: #b9c7d7;
}

QPushButton#EditorTool {
    background: #f8fafc;
    color: #42526a;
    border-color: #e0e7ef;
    padding: 4px 7px;
    min-height: 18px;
}

QPushButton#EditorTool:hover {
    background: #eef6ff;
    color: #0b6bd3;
    border-color: #b7d7f8;
}

QPushButton#IconButton {
    background: #f8fafc;
    color: #52637a;
    border-color: #e0e7ef;
    padding: 3px;
    min-height: 21px;
}

QPushButton#IconButton:hover {
    background: #eef6ff;
    color: #0b6bd3;
    border-color: #b7d7f8;
}

QPushButton#OverlayClose {
    background: #ffffff;
    color: #64748b;
    border: 1px solid #d7e0ea;
    padding: 5px 10px;
}

QPushButton#OverlayClose:hover {
    background: #fff1f2;
    color: #be123c;
    border-color: #fecdd3;
}

QPushButton:checked {
    background: #eaf4ff;
    color: #0b6bd3;
    border-color: #93c5fd;
    font-weight: 700;
}

QLabel#PreviewOn {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
    border-radius: 8px;
    padding: 4px 8px;
    font-weight: 700;
}

QLabel#PreviewOff {
    background: #fff1f2;
    color: #9f1239;
    border: 1px solid #fecdd3;
    border-radius: 8px;
    padding: 4px 8px;
    font-weight: 700;
}

QLineEdit,
QPlainTextEdit,
QTreeWidget,
QListWidget,
QTableWidget {
    background: #ffffff;
    border: 1px solid #dce4ee;
    border-radius: 8px;
    selection-background-color: #ddebff;
    selection-color: #0f4f9a;
}

QLineEdit {
    padding: 7px 9px;
    min-height: 22px;
}

QLineEdit#FormInput {
    font-size: 11px;
    min-height: 24px;
}

QLineEdit:focus,
QPlainTextEdit:focus,
QTreeWidget:focus,
QListWidget:focus,
QTableWidget:focus {
    border: 1px solid #60a5fa;
}

QLineEdit[readOnly="true"] {
    background: #f8fafc;
    color: #64748b;
}

QTreeWidget,
QListWidget {
    outline: none;
    padding: 4px;
}

QListWidget#BooksList {
    background: #fbfdff;
}

QListWidget#BooksList::item {
    min-height: 28px;
    padding: 4px 7px;
    margin: 1px 0;
    border-radius: 6px;
}

QListWidget#BooksList::item:hover {
    background: #f1f7ff;
}

QListWidget#BooksList::item:selected {
    background: #ddebff;
    color: #0d55a5;
}

QTreeWidget::item {
    min-height: 26px;
    padding: 2px 4px;
    margin: 1px 0;
}

QTreeWidget::item:hover {
    background: #f4f8fc;
}

QTreeWidget::item:selected {
    background: #ddebff;
    color: #0d55a5;
    border-radius: 5px;
}

QTableWidget {
    gridline-color: #edf1f5;
    alternate-background-color: #f8fafc;
}

QHeaderView::section {
    background: #f4f7fb;
    color: #52637a;
    border: none;
    border-bottom: 1px solid #dce4ee;
    padding: 7px 6px;
    font-weight: 700;
}

QMenu {
    background: #ffffff;
    color: #263449;
    border: 1px solid #d8e1ec;
    border-radius: 8px;
    padding: 5px;
}

QMenu::item {
    padding: 7px 24px 7px 10px;
    border-radius: 5px;
}

QMenu::item:selected {
    background: #eaf4ff;
    color: #0b6bd3;
}

QToolTip {
    background: #172033;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 7px;
}

QMessageBox {
    background: #ffffff;
}

QMessageBox QLabel {
    color: #243248;
    min-width: 220px;
}

QSplitter::handle {
    background: #e7edf4;
    width: 3px;
    height: 3px;
}

QSplitter::handle:hover {
    background: #86bdf2;
}

QScrollBar:vertical {
    width: 9px;
    background: transparent;
    margin: 1px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #aebccc;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 9px;
    background: transparent;
    margin: 1px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 4px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background: #aebccc;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
"""
