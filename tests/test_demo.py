"""The demo, run end to end, with no model and no network.

The scenario is the submission. If it stops showing all four verdicts, or the
gate stops refusing the public post, the entry is worse and nobody would
notice until the recording. So the take is a test.

The model here is `ScriptedModel`, which replays a fixed sequence of tool calls
through the real event loop. Everything below the model is genuine: the same
`Agent`, the same `BeforeToolCallEvent`, the same interrupt, the same gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from understudy.charter import ASK, LOG, NEVER  # noqa: E402
from understudy.demo import run  # noqa: E402
from understudy.rehearsal import SATURDAY_TWO_SHORT, ScriptedModel  # noqa: E402

SHIFT = "s-2026-08-15-foodbank"


@pytest.fixture
def take(tmp_path):
    """Approve the first text, reword the second, approve the assignment."""
    return run(
        model=ScriptedModel(SATURDAY_TWO_SHORT, name="test"),
        scripted=["y", "e", "Hi Priya - Saturday 9 to 1 is short. Free at all?", "y"],
        ledger_path=tmp_path / "ledger.jsonl",
        plain=True,
    )


def test_the_demo_shows_all_four_verdicts(take):
    verdicts = {row["verdict"] for row in take["gate"].seen}
    assert verdicts == {"allow", LOG, ASK, NEVER}


def test_the_agent_is_stopped_from_posting_in_public(take):
    refusals = [row for row in take["gate"].seen if row["tool"] == "post_public"]
    assert len(refusals) == 1
    assert "board decision" in refusals[0]["refused"]
    assert not any(m["to"].startswith("public:") for m in take["org"].sent)


def test_the_coordinators_wording_is_what_goes_out(take):
    priya = [m for m in take["org"].sent if m["to"] == "Priya Raman"]
    assert len(priya) == 1
    assert priya[0]["body"] == "Hi Priya - Saturday 9 to 1 is short. Free at all?"
    assert "we could use the van" not in priya[0]["body"], "the agent's draft, not theirs"


def test_nothing_reaches_a_person_without_a_yes(take):
    asked = {question["tool"] for question in take["gate"].asked}
    assert asked == {"send_sms", "assign_shift"}
    assert len(take["org"].sent) == 2, "two texts, two approvals"


def test_the_saturday_is_less_short_than_it_was(take):
    shift = take["org"].shift(SHIFT)
    assert shift.short_by == 1, "Nadia was assigned; Priya has been asked and has not replied"


def test_dana_is_not_asked_because_she_worked_last_weekend(take):
    assert not any(m["to"] == "Dana Okonkwo" for m in take["org"].sent)


def test_every_ledger_line_carries_an_undo_and_is_closed_out(take):
    lines = take["gate"].ledger.entries()
    assert lines, "something happened"
    assert all(line.undo for line in lines)
    opened = [line.id for line in lines if line.outcome == "pending"]
    closed = [line.id for line in lines if line.outcome != "pending"]
    assert sorted(opened) == sorted(closed), "every action that started also finished"


def test_declining_everything_sends_nothing(tmp_path):
    take = run(
        model=ScriptedModel(SATURDAY_TWO_SHORT, name="test"),
        scripted=["n", "", "n", "", "n", ""],
        ledger_path=tmp_path / "ledger.jsonl",
        plain=True,
    )
    assert take["org"].sent == []
    assert take["org"].shift(SHIFT).short_by == 2
    # The drafts survive, so a no costs the coordinator the sending and not the writing.
    assert take["org"].drafts


def test_quiet_hours_hold_the_texts_and_let_the_paperwork_through(tmp_path):
    from datetime import datetime

    take = run(
        model=ScriptedModel(SATURDAY_TWO_SHORT, name="test"),
        scripted=["y", "y", "y"],
        ledger_path=tmp_path / "ledger.jsonl",
        plain=True,
        now=datetime(2026, 8, 12, 22, 30),
    )
    assert take["org"].sent == [], "nobody's phone goes off at half ten"
    assert take["org"].drafts, "the drafting still happened, ready for the morning"
    assert any(row["tool"] == "update_roster" and not row["refused"] for row in take["gate"].seen)
