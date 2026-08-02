from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.domain import Evidence


class UnsafeArtifactPathError(ValueError):
    """Raised when an artifact path escapes the configured root."""


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, package_id: str, run_id: str, relative_path: str) -> Path:
        if not package_id or not run_id:
            raise UnsafeArtifactPathError("package_id and run_id are required")
        candidate = (self.root / package_id / run_id / relative_path).resolve()
        if self.root not in candidate.parents:
            raise UnsafeArtifactPathError("artifact path escapes evidence root")
        return candidate

    @staticmethod
    def sha256_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def write_json(
        self,
        *,
        evidence_id: str,
        package_id: str,
        run_id: str,
        evidence_type: str,
        producer: str,
        relative_path: str,
        payload: dict[str, Any],
        tool_version: str,
        seed: int | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
    ) -> Evidence:
        target = self._safe_path(package_id, run_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        target.write_bytes(encoded)
        relative_to_root = target.relative_to(self.root).as_posix()
        return Evidence(
            id=evidence_id,
            package_id=package_id,
            run_id=run_id,
            type=evidence_type,
            producer=producer,
            artifact_path=relative_to_root,
            sha256=self.sha256_bytes(encoded),
            tool_version=tool_version,
            seed=seed,
            inputs=inputs or [],
            outputs=outputs or [],
        )

    def write_bytes(
        self,
        *,
        evidence_id: str,
        package_id: str,
        run_id: str,
        evidence_type: str,
        producer: str,
        relative_path: str,
        payload: bytes,
        tool_version: str,
        seed: int | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
    ) -> Evidence:
        """Persist an arbitrary replay artifact with the same integrity metadata as JSON."""
        target = self._safe_path(package_id, run_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return Evidence(
            id=evidence_id,
            package_id=package_id,
            run_id=run_id,
            type=evidence_type,
            producer=producer,
            artifact_path=target.relative_to(self.root).as_posix(),
            sha256=self.sha256_bytes(payload),
            tool_version=tool_version,
            seed=seed,
            inputs=inputs or [],
            outputs=outputs or [],
        )

    def verify(self, evidence: Evidence) -> bool:
        path = (self.root / evidence.artifact_path).resolve()
        if self.root not in path.parents or not path.is_file():
            return False
        return self.sha256_bytes(path.read_bytes()) == evidence.sha256
