from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class PackageManifest(BaseModel):
    package_id: str
    original_filename: str
    sha256: str
    file_count: int = Field(ge=1)
    uncompressed_bytes: int = Field(ge=0)
    root_path: str
    files: list[str]
    created_at: datetime = Field(default_factory=utc_now)


class PackageLimits(BaseModel):
    max_archive_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_uncompressed_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_files: int = Field(default=2_000, gt=0)
    max_single_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
