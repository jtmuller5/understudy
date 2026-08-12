"""An append-only record of everything the agent did to the outside world.

Written *before* the action, never after. That ordering is the point: a line
written afterwards records only what succeeded, and the action you most want
to find in a log is the one that half happened.

Each line carries an undo. An action whose undo cannot be written down does
not run -- not because the undo will usually be needed, but because being
unable to state one means nobody understood the action well enough to take it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Entry:
    at: str
    tool: str
    verdict: str
    reason: str
    arguments: dict[str, Any]
    undo: str
    outcome: str = "pending"
    approved_by: str | None = None
    id: str = field(default="")


class Ledger:
    """A JSONL file. One line per outward action, appended under an O_APPEND write."""

    def __init__(self, path: str | Path = "ledger.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        tool: str,
        verdict: str,
        reason: str,
        arguments: dict[str, Any],
        undo: str,
        approved_by: str | None = None,
    ) -> Entry:
        entry = Entry(
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            tool=tool,
            verdict=verdict,
            reason=reason,
            arguments=_redact(arguments),
            undo=undo,
            approved_by=approved_by,
            id=f"{tool}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
        )
        self._append(entry)
        return entry

    def settle(self, entry: Entry, outcome: str) -> None:
        """Close an entry out. The correction is appended, never edited in place."""
        entry.outcome = outcome
        self._append(entry)

    def _append(self, entry: Entry) -> None:
        line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def entries(self) -> list[Entry]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(Entry(**json.loads(line)))
        return rows

    def outward_count(self, verdicts: tuple[str, ...] = ("ask",)) -> int:
        """How many actions have reached a person. Counts each action once.

        A logged action -- a draft kept, hours put on a record -- is a record,
        not a radius. It reaches nobody, and counting it against the budget
        means the agent runs out of allowance doing paperwork and stops before
        the part the coordinator wanted. So the count matches the test the gate
        already uses for quiet hours: an action that reaches a person.
        """
        return len({e.id for e in self.entries() if e.verdict in verdicts})


_SECRETISH = ("token", "key", "secret", "password", "passphrase", "authorization")


def _redact(arguments: dict[str, Any]) -> dict[str, Any]:
    """A log a human reads is a log a human can leak. Names stay, values go."""
    clean: dict[str, Any] = {}
    for name, value in arguments.items():
        if any(word in name.lower() for word in _SECRETISH):
            clean[name] = "<redacted>"
        elif isinstance(value, str) and len(value) > 500:
            clean[name] = value[:500] + f"… (+{len(value) - 500} chars)"
        else:
            clean[name] = value
    return clean
