from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from backend.app.domain import AgentEvent


class TraceWriter:
    """Append-only JSONL trace used for audit export and frontend replay."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _path(self, package_id: str, run_id: str) -> Path:
        target = (self.root / package_id / run_id / "trace.jsonl").resolve()
        if self.root not in target.parents:
            raise ValueError("trace path escapes configured root")
        return target

    def append(self, package_id: str, event: AgentEvent) -> Path:
        target = self._path(package_id, event.run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self._lock, target.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.write("\n")
            stream.flush()
        return target

    def read(self, package_id: str, run_id: str) -> list[AgentEvent]:
        target = self._path(package_id, run_id)
        if not target.exists():
            return []
        events: list[AgentEvent] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(AgentEvent.model_validate_json(line))
        return events
