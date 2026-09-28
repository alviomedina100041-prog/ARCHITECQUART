from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.book_model import BookModel
from app.quarto_manager import QuartoManager


@unittest.skipUnless(shutil.which("quarto"), "Quarto CLI no está instalado")
class QuartoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_manager_renders_fresh_html_book(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = BookModel.create_book(
                temp,
                "Integration Book",
                "CI",
                "integration-book",
            )

            manager = QuartoManager()
            loop = QEventLoop()
            result: dict[str, object] = {"timed_out": True}

            def finished(ok: bool, message: str, output_path: str) -> None:
                result.update(
                    ok=ok,
                    message=message,
                    output_path=output_path,
                    timed_out=False,
                )
                loop.quit()

            manager.render_finished.connect(finished)
            manager.render(root, "html")

            QTimer.singleShot(60000, loop.quit)
            loop.exec()

            try:
                self.assertFalse(
                    result["timed_out"],
                    "Quarto render excedió el tiempo de prueba",
                )
                self.assertTrue(result.get("ok"), result.get("message"))

                output = Path(str(result.get("output_path", "")))
                self.assertTrue(output.is_dir())
                self.assertTrue((output / "index.html").is_file())
                self.assertGreater((output / "index.html").stat().st_size, 0)
            finally:
                manager.shutdown()


if __name__ == "__main__":
    unittest.main()
