from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from backend.app.domain.package import PackageLimits, PackageManifest


class PackageIngestError(ValueError):
    """Raised when an uploaded package violates the ingestion policy."""


SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


class PackageIngestor:
    def __init__(self, root: Path, limits: PackageLimits | None = None) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.limits = limits or PackageLimits()

    @staticmethod
    def _safe_package_id(package_id: str) -> str:
        normalized = SAFE_ID.sub("-", package_id.strip()).strip(".-")
        if not normalized or normalized != package_id:
            raise PackageIngestError("package_id may only contain letters, digits, dot, dash and underscore")
        return normalized

    @staticmethod
    def _validate_member(info: zipfile.ZipInfo) -> PurePosixPath:
        normalized_name = info.filename.replace("\\", "/")
        path = PurePosixPath(normalized_name)
        if not normalized_name or path.is_absolute() or ".." in path.parts:
            raise PackageIngestError(f"unsafe archive path: {info.filename!r}")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise PackageIngestError(f"symbolic links are not allowed: {info.filename!r}")
        return path

    def ingest_zip(self, *, package_id: str, filename: str, payload: bytes) -> PackageManifest:
        package_id = self._safe_package_id(package_id)
        if not filename.lower().endswith(".zip"):
            raise PackageIngestError("only .zip problem packages are supported")
        if not payload:
            raise PackageIngestError("archive is empty")
        if len(payload) > self.limits.max_archive_bytes:
            raise PackageIngestError("archive exceeds compressed size limit")

        digest = hashlib.sha256(payload).hexdigest()
        package_root = (self.root / package_id).resolve()
        if self.root not in package_root.parents:
            raise PackageIngestError("package path escapes storage root")
        if package_root.exists():
            raise PackageIngestError("package_id already exists; original packages are immutable")

        try:
            archive = zipfile.ZipFile(BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise PackageIngestError("invalid zip archive") from exc

        with archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if not infos:
                raise PackageIngestError("archive contains no files")
            if len(infos) > self.limits.max_files:
                raise PackageIngestError("archive exceeds file count limit")

            paths: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            total_size = 0
            seen: set[str] = set()
            for info in infos:
                path = self._validate_member(info)
                canonical = path.as_posix().casefold()
                if canonical in seen:
                    raise PackageIngestError(f"duplicate archive path: {path.as_posix()}")
                seen.add(canonical)
                if info.file_size > self.limits.max_single_file_bytes:
                    raise PackageIngestError(f"file exceeds size limit: {path.as_posix()}")
                total_size += info.file_size
                if total_size > self.limits.max_uncompressed_bytes:
                    raise PackageIngestError("archive exceeds uncompressed size limit")
                paths.append((info, path))

            original_root = package_root / "original"
            try:
                original_root.mkdir(parents=True)
                archive_path = package_root / "source.zip"
                archive_path.write_bytes(payload)
                for info, relative in paths:
                    target = (original_root / Path(*relative.parts)).resolve()
                    if original_root.resolve() not in target.parents:
                        raise PackageIngestError(f"unsafe extraction target: {relative.as_posix()}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
            except Exception:
                shutil.rmtree(package_root, ignore_errors=True)
                raise

        files = sorted(path.as_posix() for _, path in paths)
        manifest = PackageManifest(
            package_id=package_id,
            original_filename=Path(filename).name,
            sha256=digest,
            file_count=len(files),
            uncompressed_bytes=total_size,
            root_path=(Path(package_id) / "original").as_posix(),
            files=files,
        )
        (package_root / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest
