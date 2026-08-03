from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

REQUIRED_ENTRIES = {
    "OJGuard/README.md",
    "OJGuard/OJGuard_项目方案.md",
    "OJGuard/benchmark/cases.yaml",
    "OJGuard/benchmark/results/baseline_report.json",
    "OJGuard/materials/Agent_Identity_清单.md",
    "OJGuard/materials/MCP_工具契约与迁移说明.md",
    "OJGuard/materials/上下文与可观测性说明.md",
    "OJGuard/output/evidence/agentteams/agentteams-demo-result.json",
    "OJGuard/output/submission/OJGuard_DeepSeek最终验收报告.md",
}
FORBIDDEN_SEGMENTS = {
    ".env",
    ".git",
    ".runtime",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".ts",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}")


def verify(zip_path: Path) -> dict[str, object]:
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = {info.filename for info in infos if not info.is_dir()}

        missing = sorted(REQUIRED_ENTRIES - names)
        if missing:
            errors.append(f"missing required entries: {missing}")

        backslash_names = sorted(name for name in names if "\\" in name)
        if backslash_names:
            errors.append(f"non-portable ZIP separators: {backslash_names[:5]}")

        escaped_unicode = sorted(name for name in names if "#U" in name or "_U" in name)
        if escaped_unicode:
            errors.append(f"escaped Unicode filenames: {escaped_unicode[:5]}")

        for name in names:
            parts = set(PurePosixPath(name).parts)
            if parts & FORBIDDEN_SEGMENTS:
                errors.append(f"forbidden path in ZIP: {name}")

        for info in infos:
            if info.is_dir() or not any(ord(character) > 127 for character in info.filename):
                continue
            if not info.flag_bits & 0x800:
                errors.append(f"Unicode entry lacks UTF-8 flag: {info.filename}")

        readme_name = "OJGuard/README.md"
        if readme_name in names:
            readme = archive.read(readme_name).decode("utf-8-sig")
            readme_root = PurePosixPath(readme_name).parent
            for raw_target in LOCAL_LINK.findall(readme):
                target = unquote(raw_target.split("#", 1)[0]).strip()
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = str(readme_root / PurePosixPath(target))
                if resolved not in names:
                    errors.append(f"broken README link: {raw_target} -> {resolved}")

        secret_hits: list[str] = []
        for name in sorted(names):
            if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = archive.read(name).decode("utf-8-sig", errors="replace")
            if SECRET.search(text):
                secret_hits.append(name)
        if secret_hits:
            errors.append(f"secret-like values found in: {secret_hits}")

    result: dict[str, object] = {
        "zip": str(zip_path.resolve()),
        "entry_count": len(names),
        "required_entry_count": len(REQUIRED_ENTRIES),
        "readme_links_checked": True,
        "unicode_names_checked": True,
        "secret_scan_checked": True,
        "errors": errors,
        "passed": not errors,
    }
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    zip_path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/submission/OJGuard_submission.zip")
    if not zip_path.is_file():
        raise SystemExit(f"submission ZIP not found: {zip_path}")
    result = verify(zip_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
