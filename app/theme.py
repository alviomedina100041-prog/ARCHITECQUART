APP_STYLE = r"""
QWidget {
    background: #ffffff;
    color: #172033;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 11px;
}
QMainWindow { background: #f5f7fb; }

QFrame#TopBar,
QFrame#SidePanel,
QFrame#EditorPanel,
QFrame#PreviewPanel,
QFrame#StatusBar {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 9px;
}

QLabel#AppTitle {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
}
QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #1e293b;
}
QLabel#Muted {
    color: #708096;
    font-size: 10px;
}

QLabel#PreviewOn {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
    border-radius: 8px;
    padding: 4px 9px;
    font-weight: 700;
}

QLabel#PreviewOff {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
    border-radius: 8px;
    padding: 4px 9px;
    font-weight: 700;
}

QPushButton, QToolButton {
    background: #ffffff;
    color: #263449;
    border: 1px solid #d5dde8;
    border-radius: 7px;
    padding: 5px 9px;
    min-height: 20px;
}
QPushButton:hover, QToolButton:hover {
    background: #f6f9fd;
    border-color: #60a5fa;
}
QPushButton#Primary, QToolButton#Primary {
    background: #1489f5;
    color: white;
    border-color: #1489f5;
    font-weight: 600;
}
QPushButton#Primary:hover, QToolButton#Primary:hover {
    background: #0877dd;
}
QPushButton:checked {
    background: #dcfce7;
    color: #137333;
    border-color: #86d79d;
}

QTreeWidget, QTableWidget, QPlainTextEdit, QLineEdit {
    background: #ffffff;
    border: 1px solid #e0e6ef;
    border-radius: 7px;
    selection-background-color: #ddebff;
    selection-color: #0f4f9a;
}
QTreeWidget {
    outline: none;
    padding: 3px;
}
QTreeWidget::item {
    min-height: 25px;
    padding: 2px 3px;
}
QTreeWidget::item:selected {
    background: #ddebff;
    color: #0d55a5;
    border-radius: 5px;
}

QTabWidget::pane {
    border: 1px solid #e0e6ef;
    background: #ffffff;
    border-radius: 7px;
}
QTabBar::tab {
    background: #f8fafc;
    border: 1px solid #e0e6ef;
    padding: 5px 13px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0b6bd3;
    border-bottom-color: #ffffff;
}

QHeaderView::section {
    background: #f7f9fc;
    color: #475569;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    padding: 4px;
}

QSplitter::handle {
    background: #e6ebf2;
    width: 3px;
    height: 3px;
}
QSplitter::handle:hover { background: #75b7f8; }

QScrollBar:vertical {
    width: 8px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #c9d3df;
    border-radius: 4px;
    min-height: 25px;
}
QScrollBar:horizontal {
    height: 8px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: #c9d3df;
    border-radius: 4px;
    min-width: 25px;
}
"""
