"""The organisation the agent works for, held in memory.

A real deployment would put a database, a texting provider and a spreadsheet
behind these same names. Nothing about the gate changes when it does: the
charter names actions, not back ends, so swapping the store for Airtable and
the sender for Twilio moves no line of `charter.md`.

Everything in `examples/riverside.json` is invented. The 555 number range and
the example.org domain are both reserved, so no data here can reach a person.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SEED = Path(__file__).resolve().parents[1] / "examples" / "riverside.json"


@dataclass
class Volunteer:
    id: str
    name: str
    phone: str
    email: str
    available: list[str]
    last_served: str | None
    hours_this_year: float
    note: str = ""

    def days_since_served(self, today: date) -> int | None:
        if not self.last_served:
            return None
        return (today - date.fromisoformat(self.last_served)).days


@dataclass
class Shift:
    id: str
    date: str
    weekday: str
    name: str
    start: str
    end: str
    needed: int
    assigned: list[str] = field(default_factory=list)

    @property
    def short_by(self) -> int:
        return max(0, self.needed - len(self.assigned))


@dataclass
class Org:
    name: str
    today: date
    volunteers: dict[str, Volunteer] = field(default_factory=dict)
    shifts: dict[str, Shift] = field(default_factory=dict)
    signups: list[dict[str, Any]] = field(default_factory=list)

    # What the agent did, so the demo can show it and the tests can assert it.
    drafts: list[dict[str, Any]] = field(default_factory=list)
    sent: list[dict[str, Any]] = field(default_factory=list)
    roster_changes: list[dict[str, Any]] = field(default_factory=list)
    hours_logged: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path = SEED) -> "Org":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        org = cls(name=raw["org"], today=date.fromisoformat(raw["today"]))
        for row in raw["volunteers"]:
            org.volunteers[row["id"]] = Volunteer(**row)
        for row in raw["shifts"]:
            org.shifts[row["id"]] = Shift(**row)
        org.signups = list(raw["signups"])
        return org

    def volunteer(self, key: str) -> Volunteer:
        """Find a volunteer by id or by name. The model will use either."""
        if key in self.volunteers:
            return self.volunteers[key]
        wanted = key.strip().lower()
        for person in self.volunteers.values():
            if person.name.lower() == wanted or person.name.split()[0].lower() == wanted:
                return person
        raise KeyError(f"no volunteer called {key!r}")

    def shift(self, key: str) -> Shift:
        if key in self.shifts:
            return self.shifts[key]
        wanted = key.strip().lower()
        for shift in self.shifts.values():
            if wanted in shift.name.lower() or wanted == shift.date:
                return shift
        raise KeyError(f"no shift called {key!r}")

    def rested_since(self, person: Volunteer, days: int) -> bool:
        """True when this person has not worked inside the last `days` days.

        The coordinator's own rule, and the reason the agent is worth having:
        remembering who carried last Saturday is exactly the work a tired
        person does badly at 11pm.
        """
        gap = person.days_since_served(self.today)
        return gap is None or gap >= days

    def next_shift_needing_people(self) -> Shift | None:
        upcoming = [s for s in self.shifts.values() if date.fromisoformat(s.date) >= self.today]
        short = [s for s in upcoming if s.short_by]
        return min(short, key=lambda s: s.date) if short else None


#: The org the tools act on. `demo.py` and the tests replace it deliberately.
_current: Org | None = None


def current() -> Org:
    global _current
    if _current is None:
        _current = Org.load()
    return _current


def use(org: Org) -> Org:
    global _current
    _current = org
    return org


def reset() -> Org:
    return use(Org.load())


def business_days_away(org: Org, iso_date: str) -> int:
    return (date.fromisoformat(iso_date) - org.today).days


__all__ = [
    "Org",
    "Shift",
    "Volunteer",
    "business_days_away",
    "current",
    "reset",
    "use",
    "SEED",
    "timedelta",
]
