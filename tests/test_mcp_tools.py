import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from backend.app.services.package_ingest import PackageIngestor
from mcp_server.tools import MCPToolError, OJGuardTools


class MCPToolsTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    @staticmethod
    def package_payload() -> bytes:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("statement.md", "# Demo")
            archive.writestr("problem.yaml", "name: Demo")
            archive.writestr("checker/checker.cpp", "int main() { return 0; }")
        return buffer.getvalue()

    def test_inspect_package_identifies_roles_without_execution(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            PackageIngestor(root / "data" / "packages").ingest_zip(
                package_id="demo", filename="demo.zip", payload=self.package_payload()
            )
            tools = OJGuardTools(root)
            result = tools.inspect_package("demo")
            self.assertEqual(result["status"], "SUCCESS")
            self.assertFalse(result["execution_performed"])
            self.assertEqual(result["roles"]["checker"], ["checker/checker.cpp"])

    def test_rejects_unsafe_identifier(self) -> None:
        with self.temporary_directory() as directory:
            tools = OJGuardTools(Path(directory))
            with self.assertRaises(MCPToolError):
                tools.inspect_package("../escape")

    def test_verify_run_evidence_rejects_unknown_run(self) -> None:
        with self.temporary_directory() as directory:
            tools = OJGuardTools(Path(directory))
            with self.assertRaises(MCPToolError):
                tools.verify_run_evidence("RUN-UNKNOWN")


if __name__ == "__main__":
    unittest.main()
