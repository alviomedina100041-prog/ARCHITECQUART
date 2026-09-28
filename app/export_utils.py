from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import TypeAlias

import yaml


Signature: TypeAlias = tuple[int, int]
Snapshot: TypeAlias = dict[str, Signature]


def configured_output_dir(root: str | Path) -> Path:
    root_path = Path(root).expanduser().resolve()
    config_path = root_path / "_quarto.yml"
    output_dir = "_book"

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        project = data.get("project") or {}
        configured = project.get("output-dir")
        if isinstance(configured, str) and configured.strip():
            output_dir = configured.strip()
    except Exception:
        pass

    candidate = Path(output_dir).expanduser()
    if not candidate.is_absolute():
        candidate = root_path / candidate
    return candidate.resolve()


def _signature(path: Path) -> Signature:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def _candidate_files(root: Path, target_format: str | None) -> list[Path]:
    output_dir = configured_output_dir(root)
    candidates: list[Path] = []

    if target_format == "html":
        index = output_dir / "index.html"
        if index.is_file():
            candidates.append(index)
        return candidates

    if target_format in {"pdf", "epub"}:
        extension = f".{target_format}"
        if output_dir.exists():
            candidates.extend(
                path for path in output_dir.rglob(f"*{extension}") if path.is_file()
            )
        candidates.extend(
            path for path in root.glob(f"*{extension}") if path.is_file()
        )
        return list(dict.fromkeys(path.resolve() for path in candidates))

    index = output_dir / "index.html"
    if index.is_file():
        candidates.append(index)

    if output_dir.exists():
        for extension in ("*.pdf", "*.epub"):
            candidates.extend(
                path for path in output_dir.rglob(extension) if path.is_file()
            )

    return list(dict.fromkeys(path.resolve() for path in candidates))


def snapshot_outputs(
    root: str | Path,
    target_format: str | None,
) -> Snapshot:
    root_path = Path(root).expanduser().resolve()
    snapshot: Snapshot = {}

    for path in _candidate_files(root_path, target_format):
        try:
            snapshot[str(path.resolve())] = _signature(path)
        except OSError:
            continue

    return snapshot


def detect_fresh_output(
    root: str | Path,
    target_format: str | None,
    before: Snapshot,
) -> Path | None:
    root_path = Path(root).expanduser().resolve()
    output_dir = configured_output_dir(root_path)
    changed: list[Path] = []

    for path in _candidate_files(root_path, target_format):
        try:
            signature = _signature(path)
        except OSError:
            continue

        key = str(path.resolve())
        if before.get(key) != signature:
            changed.append(path.resolve())

    if not changed:
        return None

    if target_format == "html":
        index = (output_dir / "index.html").resolve()
        if index in changed:
            return output_dir
        return None

    if target_format in {"pdf", "epub"}:
        return max(changed, key=lambda path: path.stat().st_mtime_ns)

    return output_dir if output_dir.exists() else max(
        changed,
        key=lambda path: path.stat().st_mtime_ns,
    )


def verify_export(path: str | Path, target_format: str) -> tuple[bool, str]:
    output = Path(path).expanduser().resolve()

    if target_format == "html":
        index = output / "index.html"
        if not output.is_dir():
            return False, "La exportación HTML no es una carpeta."
        if not index.is_file() or index.stat().st_size == 0:
            return False, "La exportación HTML no contiene un index.html válido."
        return True, ""

    if target_format == "pdf":
        if not output.is_file() or output.stat().st_size < 5:
            return False, "El archivo PDF no existe o está vacío."
        try:
            with output.open("rb") as handle:
                if handle.read(5) != b"%PDF-":
                    return False, "El archivo generado no tiene una cabecera PDF válida."
        except OSError as exc:
            return False, f"No se pudo verificar el PDF: {exc}"
        return True, ""

    if target_format == "epub":
        if not output.is_file() or output.stat().st_size == 0:
            return False, "El archivo EPUB no existe o está vacío."
        if not zipfile.is_zipfile(output):
            return False, "El archivo generado no es un contenedor EPUB válido."
        try:
            with zipfile.ZipFile(output) as archive:
                if "mimetype" not in archive.namelist():
                    return False, "El EPUB no contiene el campo mimetype."
                mimetype = archive.read("mimetype").decode(
                    "utf-8",
                    errors="ignore",
                ).strip()
        except (OSError, zipfile.BadZipFile) as exc:
            return False, f"No se pudo verificar el EPUB: {exc}"

        if mimetype != "application/epub+zip":
            return False, "El mimetype del EPUB no es válido."
        return True, ""

    return False, f"Formato de exportación no soportado: {target_format}"


def copy_verified_export(
    source: str | Path,
    target_format: str,
    destination: str | Path,
) -> Path:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()

    valid, reason = verify_export(source_path, target_format)
    if not valid:
        raise RuntimeError(reason)

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if target_format == "html":
        try:
            destination_path.relative_to(source_path)
        except ValueError:
            pass
        else:
            raise RuntimeError(
                "La carpeta de destino no puede estar dentro de la salida "
                "temporal de Quarto."
            )

        temporary = destination_path.with_name(
            destination_path.name + ".architecquart-tmp"
        )
        if temporary.exists():
            shutil.rmtree(temporary)

        shutil.copytree(source_path, temporary)
        valid, reason = verify_export(temporary, "html")
        if not valid:
            shutil.rmtree(temporary, ignore_errors=True)
            raise RuntimeError(reason)

        if destination_path.exists():
            shutil.rmtree(destination_path)
        temporary.rename(destination_path)
        return destination_path

    temporary = destination_path.with_name(
        destination_path.name + ".architecquart-tmp"
    )
    if temporary.exists():
        temporary.unlink()

    shutil.copy2(source_path, temporary)
    valid, reason = verify_export(temporary, target_format)
    if not valid:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(reason)

    os.replace(temporary, destination_path)

    valid, reason = verify_export(destination_path, target_format)
    if not valid:
        raise RuntimeError(reason)

    return destination_path
