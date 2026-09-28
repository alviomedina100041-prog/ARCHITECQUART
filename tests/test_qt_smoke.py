from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-gpu-compositing --no-sandbox",
)

from PySide6.QtWidgets import QApplication

from app.book_model import BookModel
from app.window import MainWindow


class QtSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_builds_for_real_book(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = BookModel.create_book(
                temp,
                "Smoke Book",
                "Test Author",
                "smoke-book",
            )

            window = MainWindow(str(root))
            try:
                self.assertTrue(window.book.is_book())
                self.assertEqual(window.project_label.text(), "Smoke Book")
                self.assertIsNotNone(window.preview_view)
                self.assertIsNotNone(window.books_list)
                self.assertIsNotNone(window.book_tree)
                self.assertTrue(window.render_btn.isEnabled())
                self.assertTrue(window.export_btn.isEnabled())
            finally:
                window.shutdown()
                window.close()


if __name__ == "__main__":
    unittest.main()
