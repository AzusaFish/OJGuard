import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.services.package_ingest import PackageIngestError, PackageIngestor


def make_zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return output.getvalue()


class PackageIngestorTests(unittest.TestCase):
    @staticmethod
    def temporary_directory() -> tempfile.TemporaryDirectory[str]:
        base = Path(".test-tmp")
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_ingests_zip_and_preserves_original(self) -> None:
        payload = make_zip({"statement.md": b"# Demo", "solutions/main.cpp": b"int main(){}"})
        with self.temporary_directory() as directory:
            ingestor = PackageIngestor(Path(directory))
            manifest = ingestor.ingest_zip(
                package_id="demo-001",
                filename="demo.zip",
                payload=payload,
            )
            self.assertEqual(manifest.file_count, 2)
            self.assertTrue((Path(directory) / "demo-001" / "source.zip").is_file())
            self.assertTrue(
                (Path(directory) / "demo-001" / "original" / "solutions" / "main.cpp").is_file()
            )

    def test_rejects_path_traversal(self) -> None:
        payload = make_zip({"../escape.txt": b"no"})
        with self.temporary_directory() as directory:
            ingestor = PackageIngestor(Path(directory))
            with self.assertRaises(PackageIngestError):
                ingestor.ingest_zip(package_id="demo-002", filename="demo.zip", payload=payload)

    def test_original_package_id_is_immutable(self) -> None:
        payload = make_zip({"statement.md": b"# Demo"})
        with self.temporary_directory() as directory:
            ingestor = PackageIngestor(Path(directory))
            ingestor.ingest_zip(package_id="demo-003", filename="demo.zip", payload=payload)
            with self.assertRaises(PackageIngestError):
                ingestor.ingest_zip(package_id="demo-003", filename="demo.zip", payload=payload)


if __name__ == "__main__":
    unittest.main()
