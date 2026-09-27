from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.paint_line_numbers(event)


class QuartoHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        def fmt(color: str, bold: bool = False, italic: bool = False):
            value = QTextCharFormat()
            value.setForeground(QColor(color))
            value.setFontWeight(QFont.Bold if bold else QFont.Normal)
            value.setFontItalic(italic)
            return value

        self.rules.extend([
            (QRegularExpression(r"^#{1,6}\s+.*$"), fmt("#075fd1", True)),
            (QRegularExpression(r"\[@[^\]]+\]"), fmt("#7c3aed")),
            (QRegularExpression(r"!\[[^\]]*\]\([^\)]+\)"), fmt("#b45309")),
            (QRegularExpression(r"\[[^\]]+\]\([^\)]+\)"), fmt("#2563eb")),
            (QRegularExpression(r"\*\*[^*]+\*\*"), fmt("#111827", True)),
            (QRegularExpression(r"^\s*[-*+]\s+"), fmt("#d97706", True)),
            (QRegularExpression(r"^\s*\d+\.\s+"), fmt("#d97706", True)),
            (QRegularExpression(r"^:::\s*.*$"), fmt("#0f766e", True)),
            (QRegularExpression(r"^\x60\x60\x60.*$"), fmt("#047857", True)),
            (QRegularExpression(r"^#\|.*$"), fmt("#64748b", False, True)),
        ])

    def highlightBlock(self, text: str) -> None:
        for pattern, style in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), style)


class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.line_area = LineNumberArea(self)
        self.highlighter = QuartoHighlighter(self.document())

        font = QFont("JetBrains Mono")
        if not font.exactMatch():
            font = QFont("Noto Sans Mono")
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width()
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, *_args) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#f8fafc"))

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(
                    0,
                    top,
                    self.line_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#f6f9ff"))
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])
