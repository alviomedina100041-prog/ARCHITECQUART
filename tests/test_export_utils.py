from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from app.export_utils import (
    copy_verified_export,
    detect_fresh_output,
    snapshot_outputs,
    verify_export,
)


class ExportUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "_quarto.yml").write_text(
            "project:\n  type: book\n  output-dir: _book\n",
            encoding="utf-8",
        )
        (self.root / "_book").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_stale_html_is_not_reported_as_new(self) -> None:
        index = self.root / "_book" / "index.html"
        index.write_text("<html>old</html>", encoding="utf-8")

        before = snapshot_outputs(self.root, "html")
        detected = detect_fresh_output(self.root, "html", before)

        self.assertIsNone(detected)

    def test_changed_html_is_detected_and_copied(self) -> None:
        index = self.root / "_book" / "index.html"
        index.write_text("<html>old</html>", encoding="utf-8")

        before = snapshot_outputs(self.root, "html")
        index.write_text("<html>new content</html>", encoding="utf-8")

        detected = detect_fresh_output(self.root, "html", before)
        self.assertEqual(detected, self.root / "_book")

        destination = self.root / "exports" / "book-html"
        copied = copy_verified_export(detected, "html", destination)
        self.assertEqual(copied, destination.resolve())
        self.assertTrue((destination / "index.html").is_file())

    def test_pdf_requires_pdf_header(self) -> None:
        bad = self.root / "_book" / "bad.pdf"
        bad.write_bytes(b"not a pdf")

        valid, _reason = verify_export(bad, "pdf")
        self.assertFalse(valid)

        good = self.root / "_book" / "good.pdf"
        good.write_bytes(b"%PDF-1.7\nbody")
        valid, reason = verify_export(good, "pdf")
        self.assertTrue(valid, reason)

    def test_epub_requires_valid_mimetype(self) -> None:
        epub = self.root / "_book" / "book.epub"
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", "<container/>")

        valid, reason = verify_export(epub, "epub")
        self.assertTrue(valid, reason)

    def test_changed_pdf_is_detected(self) -> None:
        pdf = self.root / "_book" / "book.pdf"
        pdf.write_bytes(b"%PDF-1.4\nold")
        before = snapshot_outputs(self.root, "pdf")

        pdf.write_bytes(b"%PDF-1.7\nnew content")
        detected = detect_fresh_output(self.root, "pdf", before)

        self.assertEqual(detected, pdf.resolve())


if __name__ == "__main__":
    unittest.main()
