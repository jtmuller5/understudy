"""The charter: a plain-text file a non-programmer writes, compiled into a gate.

The charter is the whole idea. An agent that can act in the world needs a
boundary, and the boundary must be legible to the person who carries the
consequences. So it is a file they can read, in their words, and every rule
in it has a reason attached -- because a rule without a reason is one that
gets argued away the first time it is inconvenient.

Format (charter.md):

    ## never
    - refund_payment: money that has already moved is not the agent's to move
    - delete_*: a deletion cannot be undone by writing another line

    ## ask
    - send_sms: a text arrives on a real phone, so a human chooses to send it
    - post_public: anything a stranger reads

    ## log
    - update_roster: reversible, but the coordinator must be able to see it

    ## limits
    - outward_actions_per_run: 3
    - quiet_hours: 21:00-08:00

Anything not named is `allow` -- reading, drafting, thinking. Internal work is
free and outward action is gated; that asymmetry is the design.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

#: Verdicts, from most to least permissive.
ALLOW = "allow"
LOG = "log"
ASK = "ask"
NEVER = "never"

_SECTIONS = {NEVER, ASK, LOG}
_HEADING = re.compile(r"^#{1,6}\s*(\w+)\s*$")
_RULE = re.compile(r"^[-*]\s*([^:]+?)\s*:\s*(.+?)\s*$")
_QUIET = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


@dataclass(frozen=True)
class Rule:
    """One line of the charter."""

    pattern: str
    verdict: str
    reason: str

    def matches(self, tool_name: str) -> bool:
        return fnmatch.fnmatchcase(tool_name, self.pattern)


@dataclass
class Charter:
    """A parsed charter. Read-only at runtime -- the agent never edits its own."""

    rules: list[Rule] = field(default_factory=list)
    outward_actions_per_run: int = 3
    quiet_hours: tuple[time, time] | None = None
    source: Path | None = None

    @classmethod
    def parse(cls, text: str, source: Path | None = None) -> "Charter":
        charter = cls(source=source)
        section = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("<!--"):
                continue
            heading = _HEADING.match(line)
            if heading:
                section = heading.group(1).lower()
                continue
            rule = _RULE.match(line)
            if not rule:
                continue
            key, value = rule.group(1).strip(), rule.group(2).strip()
            if section in _SECTIONS:
                charter.rules.append(Rule(key, section, value))
            elif section == "limits":
                charter._limit(key, value)
        return charter

    @classmethod
    def load(cls, path: str | Path) -> "Charter":
        path = Path(path)
        return cls.parse(path.read_text(encoding="utf-8"), source=path)

    def _limit(self, key: str, value: str) -> None:
        if key == "outward_actions_per_run":
            self.outward_actions_per_run = int(value)
        elif key == "quiet_hours":
            window = _QUIET.match(value)
            if window:
                start_h, start_m, end_h, end_m = (int(g) for g in window.groups())
                self.quiet_hours = (time(start_h, start_m), time(end_h, end_m))

    def verdict(self, tool_name: str) -> tuple[str, str]:
        """Return (verdict, reason) for a tool.

        The strictest matching rule wins. A charter that says both "ask" and
        "never" about the same action means the person wrote it twice and meant
        the careful one; guessing the permissive reading is how an agent talks
        its way past a boundary.
        """
        best = (ALLOW, "not named in the charter, so it is ordinary internal work")
        for verdict in (LOG, ASK, NEVER):
            for rule in self.rules:
                if rule.verdict == verdict and rule.matches(tool_name):
                    best = (verdict, rule.reason)
        return best

    def in_quiet_hours(self, now: time) -> bool:
        if not self.quiet_hours:
            return False
        start, end = self.quiet_hours
        if start <= end:
            return start <= now < end
        return now >= start or now < end
