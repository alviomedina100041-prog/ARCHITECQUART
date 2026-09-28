from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.book_model import BookModel


class BookModelTests(unittest.TestCase):
    def test_create_book_and_add_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = BookModel.create_book(
                parent=parent,
                title="Libro Profesional",
                author="Eduardo",
                folder_name="libro-profesional",
            )

            model = BookModel(root)
            self.assertTrue(model.is_book())
            self.assertEqual(model.title(), "Libro Profesional")
            self.assertTrue((root / "_quarto.yml").is_file())
            self.assertTrue((root / "index.qmd").is_file())
            self.assertTrue((root / "01-introduccion.qmd").is_file())
            self.assertTrue((root / "references.bib").is_file())
            self.assertTrue((root / "images").is_dir())

            chapter = model.add_chapter("Marco teórico")
            self.assertTrue(chapter.is_file())
            self.assertIn("marco-teorico", chapter.name)

            names = [
                entry.get("path")
                for entry in model.chapters()
                if entry.get("path")
            ]
            self.assertIn(chapter.name, names)

    def test_duplicate_nonempty_book_folder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "existing"
            root.mkdir()
            (root / "keep.txt").write_text("data", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                BookModel.create_book(
                    parent=parent,
                    title="Existing",
                    folder_name="existing",
                )


if __name__ == "__main__":
    unittest.main()
