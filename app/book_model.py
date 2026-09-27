from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml


class BookModel:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.config_path = self.root / "_quarto.yml"

    def is_book(self) -> bool:
        if not self.config_path.exists():
            return False
        data = self.load_config()
        return isinstance(data.get("book"), dict)

    def load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def title(self) -> str:
        data = self.load_config()
        book = data.get("book") or {}
        project = data.get("project") or {}
        return str(book.get("title") or project.get("title") or self.root.name)

    def chapters(self) -> list[dict[str, Any]]:
        data = self.load_config()
        book = data.get("book") or {}
        return self._normalize_entries(book.get("chapters") or [])

    def _normalize_entries(self, entries: list[Any]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, str):
                output.append({
                    "path": entry,
                    "title": self.file_title(entry),
                    "children": [],
                })
                continue

            if not isinstance(entry, dict):
                continue

            if "part" in entry:
                output.append({
                    "path": None,
                    "title": str(entry.get("part") or "Parte"),
                    "children": self._normalize_entries(entry.get("chapters") or []),
                })
                continue

            path = entry.get("href") or entry.get("file")
            if path:
                output.append({
                    "path": str(path),
                    "title": str(entry.get("text") or self.file_title(str(path))),
                    "children": self._normalize_entries(entry.get("chapters") or []),
                })

        return output

    def file_title(self, relative: str) -> str:
        path = self.root / relative
        if path.exists() and path.suffix.lower() == ".qmd":
            try:
                text = path.read_text(encoding="utf-8")
                match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                if match:
                    return match.group(1).strip()
            except Exception:
                pass
        return Path(relative).stem.replace("-", " ").replace("_", " ").title()

    def bibliography_files(self) -> list[Path]:
        data = self.load_config()
        bibliography = data.get("bibliography", [])
        if isinstance(bibliography, str):
            bibliography = [bibliography]
        return [
            (self.root / value).resolve()
            for value in bibliography
            if isinstance(value, str)
        ]

    def add_chapter(self, title: str) -> Path:
        data = self.load_config()
        if not data:
            raise RuntimeError("No se encontró _quarto.yml")

        book = data.setdefault("book", {})
        chapters = book.setdefault("chapters", [])

        number = self._next_chapter_number(chapters)
        slug = self.slugify(title) or "capitulo"
        filename = f"{number:02d}-{slug}.qmd"
        path = self.root / filename

        counter = 2
        while path.exists():
            filename = f"{number:02d}-{slug}-{counter}.qmd"
            path = self.root / filename
            counter += 1

        path.write_text(
            f"# {title}\n\nEscribe aquí el contenido de este capítulo.\n",
            encoding="utf-8",
        )
        chapters.append(filename)

        self.config_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def slugify(value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")

    @staticmethod
    def _next_chapter_number(chapters: list[Any]) -> int:
        count = 0
        for entry in chapters:
            if isinstance(entry, str):
                count += 1
            elif isinstance(entry, dict) and "chapters" in entry:
                count += len(entry.get("chapters") or [])
        return max(1, count + 1)


def parse_bib_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8", errors="ignore")
    entries: list[dict[str, str]] = []
    pattern = re.compile(
        r"@(\w+)\s*\{\s*([^,]+),(.*?)(?=\n@|\Z)",
        re.DOTALL,
    )

    def field(body: str, name: str) -> str:
        match = re.search(
            rf"{name}\s*=\s*[{{\"]([^}}\"]+)",
            body,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""

    for match in pattern.finditer(text):
        kind, key, body = match.groups()
        entries.append({
            "key": key.strip(),
            "author": field(body, "author"),
            "title": field(body, "title"),
            "year": field(body, "year"),
            "type": kind,
        })

    return entries
