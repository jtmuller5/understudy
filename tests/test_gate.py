"""The gate is the safety claim, so it is the part that gets tested hardest.

These run with no model and no network. A boundary you can only exercise by
paying an API bill is one that stops being exercised.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookRegistry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from understudy.charter import ALLOW, ASK, LOG, NEVER, Charter  # noqa: E402
from understudy.gate import CharterGate, CharterViolation, undo  # noqa: E402
from understudy.ledger import Ledger  # noqa: E402

CHARTER = """
## never
- refund_*: money that has already moved is not the agent's to move

## ask
- send_sms: a text arrives on a real phone

## log
- update_roster: reversible, but the coordinator must see it

## limits
- outward_actions_per_run: 2
- quiet_hours: 21:00-08:00
"""


@undo("send_sms")
def _undo_sms(args):
    return f"send a retraction to {args.get('to')}"


@undo("update_roster")
def _undo_roster(args):
    return f"set shift {args.get('shift')} back to its previous volunteer"


@pytest.fixture
def charter():
    return Charter.parse(CHARTER)


@pytest.fixture
def agent():
    # Constructed, never invoked: the gate runs before any model call.
    return Agent(model="us.anthropic.claude-sonnet-4-5-20250929-v1:0")


def fire(gate, agent, name, **arguments):
    registry = HookRegistry()
    gate.register_hooks(registry)
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": name, "input": arguments, "toolUseId": "t1"},
        invocation_state={},
    )
    # Strands collects interrupts rather than letting them propagate: the run is
    # suspended and handed out, not crashed.
    event, interrupts = registry.invoke_callbacks(event)
    return event, interrupts


def test_charter_parses_every_section(charter):
    assert charter.verdict("refund_payment")[0] == NEVER
    assert charter.verdict("send_sms")[0] == ASK
    assert charter.verdict("update_roster")[0] == LOG
    assert charter.verdict("read_calendar")[0] == ALLOW
    assert charter.outward_actions_per_run == 2


def test_the_strictest_rule_wins():
    both = Charter.parse("## ask\n- send_sms: a phone\n## never\n- send_*: no\n")
    assert both.verdict("send_sms")[0] == NEVER


def test_reading_is_never_gated(charter, agent, tmp_path):
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"))
    event, _ = fire(gate, agent, "read_signup_sheet")
    assert event.cancel_tool is False
    assert gate.ledger.entries() == []


def test_a_forbidden_tool_is_cancelled_with_the_charters_reason(charter, agent, tmp_path):
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"))
    event, _ = fire(gate, agent, "refund_payment", amount=40)
    assert "money that has already moved" in event.cancel_tool


def test_a_logged_action_writes_its_undo_before_it_runs(charter, agent, tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    gate = CharterGate(charter, ledger)
    event, _ = fire(gate, agent, "update_roster", shift="sat-am", volunteer="Dana")
    assert event.cancel_tool is False
    (row,) = ledger.entries()
    assert row.outcome == "pending"
    assert row.undo == "set shift sat-am back to its previous volunteer"


def test_a_gated_tool_with_no_undo_refuses_to_run(agent, tmp_path):
    charter = Charter.parse("## log\n- wire_money: reversible, allegedly\n")
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"))
    with pytest.raises(CharterViolation):
        fire(gate, agent, "wire_money", amount=1)


def test_ask_suspends_the_run_until_a_human_answers(charter, agent, tmp_path):
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"))
    event, interrupts = fire(gate, agent, "send_sms", to="+15551234567", body="Cover Saturday?")
    assert [i.name for i in interrupts] == ["charter-gate"]
    assert interrupts[0].reason["tool"] == "send_sms"
    assert gate.asked[-1]["undo_if_you_say_yes"] == "send a retraction to +15551234567"
    assert gate.ledger.entries() == [], "nothing is logged until the human says yes"


def test_a_declined_ask_cancels_the_tool(charter, agent, tmp_path):
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"))
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": "send_sms", "input": {"to": "+1555"}, "toolUseId": "t9"},
        invocation_state={},
    )
    interrupt_id = event._interrupt_id("charter-gate")
    _seed(agent, interrupt_id, {"approved": False, "note": "Dana is away"})
    registry = HookRegistry()
    gate.register_hooks(registry)
    registry.invoke_callbacks(event)
    assert "Dana is away" in event.cancel_tool


def test_an_approved_ask_runs_and_records_who_approved_it(charter, agent, tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    gate = CharterGate(charter, ledger)
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": "send_sms", "input": {"to": "+1555"}, "toolUseId": "t9"},
        invocation_state={},
    )
    _seed(agent, event._interrupt_id("charter-gate"), {"approved": True, "by": "Priya"})
    registry = HookRegistry()
    gate.register_hooks(registry)
    registry.invoke_callbacks(event)
    assert event.cancel_tool is False
    assert ledger.entries()[0].approved_by == "Priya"


def test_the_blast_radius_holds(charter, agent, tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    gate = CharterGate(charter, ledger)
    for shift in ("sat-am", "sat-pm"):
        assert fire(gate, agent, "update_roster", shift=shift)[0].cancel_tool is False
    third, _ = fire(gate, agent, "update_roster", shift="sun-am")
    assert "limit" in str(third.cancel_tool)


def test_quiet_hours_stop_a_message_and_not_a_roster_edit(charter, agent, tmp_path):
    at_2300 = lambda: datetime(2026, 8, 12, 23, 0)  # noqa: E731
    gate = CharterGate(charter, Ledger(tmp_path / "l.jsonl"), now=at_2300)
    assert "quiet hours" in str(fire(gate, agent, "send_sms", to="+1555")[0].cancel_tool)
    assert fire(gate, agent, "update_roster", shift="sat-am")[0].cancel_tool is False


def test_the_ledger_redacts_values_that_look_like_secrets(charter, agent, tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    gate = CharterGate(charter, ledger)
    fire(gate, agent, "update_roster", shift="sat-am", api_key="sk-live-real")
    assert ledger.entries()[0].arguments["api_key"] == "<redacted>"


def _seed(agent, interrupt_id, response):
    from strands.types.interrupt import Interrupt

    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "charter-gate", None, response
    )
