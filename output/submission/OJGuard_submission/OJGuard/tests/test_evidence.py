import tempfile
import unittest
from pathlib import Path

from backend.app.services.evidence import EvidenceStore, UnsafeArtifactPathError


class EvidenceStoreTests(unittest.TestCase):
    @staticmethod
    def temporary_directory() -> tempfile.TemporaryDirectory[str]:
        base = Path(".test-tmp")
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_write_and_verify_json_evidence(self) -> None:
        with self.temporary_directory() as directory:
            store = EvidenceStore(Path(directory))
            evidence = store.write_json(
                evidence_id="EV-001",
                package_id="PKG-001",
                run_id="RUN-001",
                evidence_type="unit_test",
                producer="test",
                relative_path="executions/EV-001.json",
                payload={"actual": 1, "expected": 2},
                tool_version="0.1.0",
            )
            self.assertTrue(store.verify(evidence))

    def test_rejects_path_traversal(self) -> None:
        with self.temporary_directory() as directory:
            store = EvidenceStore(Path(directory))
            with self.assertRaises(UnsafeArtifactPathError):
                store.write_json(
                    evidence_id="EV-002",
                    package_id="PKG-001",
                    run_id="RUN-001",
                    evidence_type="unit_test",
                    producer="test",
                    relative_path="../../../outside.json",
                    payload={},
                    tool_version="0.1.0",
                )


if __name__ == "__main__":
    unittest.main()
