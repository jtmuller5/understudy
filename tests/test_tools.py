"""The tools, and the two claims made about them.

The first is behavioural: `find_available_volunteers` remembers who carried the
last shift. That is the whole reason a coordinator would hand this over, so it
is worth a test rather than a sentence in a README.

The second is structural: every tool the shipped charter gates declares an
undo. The gate raises when one does not, but it only raises when that tool is
actually called, which could be the day it matters. The test below asks the
question about the whole tool set at once, before anything runs.

No model and no network.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookRegistry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from understudy import org as org_module  # noqa: E402
from understudy import tools  # noqa: E402
from understudy.charter import ALLOW, ASK, LOG, NEVER, Charter  # noqa: E402
from understudy.coordinator import CHARTER_PATH  # noqa: E402
from understudy.demo import DecisionQueue  # noqa: E402
from understudy.gate import CharterGate, _UNDO  # noqa: E402
from understudy.ledger import Ledger  # noqa: E402

SHIFT = "s-2026-08-15-foodbank"


@pytest.fixture(autouse=True)
def org():
    return org_module.reset()


@pytest.fixture
def agent():
    return Agent(model="us.anthropic.claude-sonnet-4-5-20250929-v1:0")


def call(tool, **arguments):
    """Call a decorated tool the way the agent would, and unwrap the result."""
    result = tool(**arguments)
    return result


# --------------------------------------------------------------------------
# The structural claim.
# --------------------------------------------------------------------------


def test_every_gated_tool_in_the_shipped_charter_declares_an_undo():
    charter = Charter.load(CHARTER_PATH)
    missing = []
    for tool in tools.COORDINATOR_TOOLS:
        name = tool.tool_name
        verdict, _ = charter.verdict(name)
        if verdict in (LOG, ASK) and name not in _UNDO:
            missing.append(name)
    assert not missing, f"gated with no undo: {missing}"


def test_the_shipped_charter_gates_the_tools_it_means_to():
    charter = Charter.load(CHARTER_PATH)
    assert charter.verdict("send_sms")[0] == ASK
    assert charter.verdict("assign_shift")[0] == ASK
    assert charter.verdict("record_hours")[0] == LOG
    assert charter.verdict("post_public")[0] == NEVER
    assert charter.verdict("refund_payment")[0] == NEVER
    assert charter.verdict("read_signup_sheet")[0] == ALLOW
    assert charter.verdict("find_available_volunteers")[0] == ALLOW


# --------------------------------------------------------------------------
# The behavioural claim.
# --------------------------------------------------------------------------


def test_the_signup_sheet_finds_the_shift_that_is_short():
    sheet = call(tools.read_signup_sheet)
    assert sheet["shift_id"] == SHIFT
    assert sheet["short_by"] == 2
    assert len(sheet["signed_up"]) == 4


def test_somebody_who_worked_last_week_is_held_back_not_dropped():
    found = call(tools.find_available_volunteers, shift_id=SHIFT)
    asked = [row["name"] for row in found["ask_in_this_order"]]
    resting = {row["name"]: row["reason"] for row in found["resting"]}

    assert "Dana Okonkwo" in resting, "Dana worked four days ago"
    assert "Rita Lindqvist" in resting
    assert "Dana Okonkwo" not in asked
    # Held back, with the reason attached, so the coordinator can overrule it.
    assert "3 days ago" in resting["Rita Lindqvist"]


def test_people_who_are_not_free_that_day_are_separated_from_people_resting():
    found = call(tools.find_available_volunteers, shift_id=SHIFT)
    unavailable = {row["name"] for row in found["unavailable"]}
    assert "Owen Marsh" in unavailable, "Owen is not free on a Saturday"
    assert "Owen Marsh" not in {row["name"] for row in found["resting"]}


def test_the_longest_rested_person_is_asked_first():
    found = call(tools.find_available_volunteers, shift_id=SHIFT)
    order = [row["name"] for row in found["ask_in_this_order"]]
    # Nadia has never served, so nobody has been left alone longer.
    assert order[0] == "Nadia Farouk"
    assert order.index("Priya Raman") < order.index("Marcus Bell")


def test_the_rest_rule_is_the_coordinators_to_relax():
    strict = call(tools.find_available_volunteers, shift_id=SHIFT, rest_days=7)
    relaxed = call(tools.find_available_volunteers, shift_id=SHIFT, rest_days=2)
    assert "Rita Lindqvist" in {r["name"] for r in relaxed["ask_in_this_order"]}
    assert "Rita Lindqvist" not in {r["name"] for r in strict["ask_in_this_order"]}


def test_a_draft_is_kept_and_nothing_is_sent(org):
    call(tools.draft_message, volunteer="Marcus", body="Any chance you are free Saturday?")
    assert len(org.drafts) == 1
    assert org.sent == []


def test_hours_land_on_the_record(org):
    before = org.volunteer("Tomas").hours_this_year
    call(tools.record_hours, volunteer="Tomas", shift_id=SHIFT, hours=4)
    assert org.volunteer("Tomas").hours_this_year == before + 4


def test_assigning_somebody_closes_the_gap():
    call(tools.assign_shift, volunteer="Nadia", shift_id=SHIFT)
    assert call(tools.read_signup_sheet)["short_by"] == 1


# --------------------------------------------------------------------------
# The gate, over the real tools and the real charter.
# --------------------------------------------------------------------------


def _fire(gate, agent, name, tool_use_id="t1", **arguments):
    registry = HookRegistry()
    gate.register_hooks(registry)
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": name, "input": arguments, "toolUseId": tool_use_id},
        invocation_state={},
    )
    return registry.invoke_callbacks(event)


def _fired_gate(tmp_path, now=None):
    charter = Charter.load(CHARTER_PATH)
    return CharterGate(charter, Ledger(tmp_path / "l.jsonl"), now=now or datetime.now)


def test_the_public_post_is_refused_in_the_charters_own_words(agent, tmp_path):
    gate = _fired_gate(tmp_path)
    event, _ = _fire(gate, agent, "post_public", where="the neighbourhood group", body="hello")
    assert "board decision" in event.cancel_tool
    assert gate.ledger.entries() == [], "a refused action is not an action"


def test_the_gate_records_the_reads_it_allowed(agent, tmp_path):
    gate = _fired_gate(tmp_path)
    _fire(gate, agent, "read_signup_sheet", tool_use_id="r1")
    _fire(gate, agent, "find_available_volunteers", tool_use_id="r2", shift_id=SHIFT)
    assert [row["verdict"] for row in gate.seen] == [ALLOW, ALLOW]


def test_a_suspended_call_is_one_decision_and_not_two(agent, tmp_path):
    """`ask` runs the callback twice: once to raise, once to resume."""
    from strands.types.interrupt import Interrupt

    gate = _fired_gate(tmp_path)
    _fire(gate, agent, "send_sms", tool_use_id="t5", to="Marcus", body="Free Saturday?")
    assert len(gate.seen) == 1 and len(gate.asked) == 1

    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": "send_sms", "input": {"to": "Marcus", "body": "Free Saturday?"}, "toolUseId": "t5"},
        invocation_state={},
    )
    interrupt_id = event._interrupt_id("charter-gate")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "charter-gate", None, {"approved": True, "by": "coordinator"}
    )
    registry = HookRegistry()
    gate.register_hooks(registry)
    registry.invoke_callbacks(event)

    assert len(gate.seen) == 1, "one call, one row"
    assert len(gate.asked) == 1, "the coordinator was asked once"


def test_an_edited_approval_sends_the_humans_words(agent, tmp_path):
    from strands.types.interrupt import Interrupt

    gate = _fired_gate(tmp_path)
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={
            "name": "send_sms",
            "input": {"to": "Marcus", "body": "Greetings valued volunteer!"},
            "toolUseId": "t4",
        },
        invocation_state={},
    )
    interrupt_id = event._interrupt_id("charter-gate")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id,
        "charter-gate",
        None,
        {"approved": True, "by": "coordinator", "edit": {"body": "Hi Marcus - free Saturday?"}},
    )
    registry = HookRegistry()
    gate.register_hooks(registry)
    registry.invoke_callbacks(event)

    assert event.cancel_tool is False
    assert event.tool_use["input"]["body"] == "Hi Marcus - free Saturday?"
    assert gate.ledger.entries()[0].arguments["body"] == "Hi Marcus - free Saturday?"


def test_the_ledger_line_is_closed_out_after_the_call(agent, tmp_path):
    gate = _fired_gate(tmp_path)
    _fire(gate, agent, "record_hours", tool_use_id="t7", volunteer="Tomas", shift_id=SHIFT, hours=4)

    registry = HookRegistry()
    gate.register_hooks(registry)
    registry.invoke_callbacks(
        AfterToolCallEvent(
            agent=agent,
            selected_tool=None,
            tool_use={"name": "record_hours", "input": {}, "toolUseId": "t7"},
            invocation_state={},
            result={"status": "success", "content": []},
        )
    )
    lines = gate.ledger.entries()
    assert [line.outcome for line in lines] == ["pending", "success"]
    assert gate.ledger.outward_count(("log",)) == 1, "one action, written twice, counted once"


def test_a_run_that_half_happened_is_still_findable(agent, tmp_path):
    """The line the ledger exists for: started, and never closed out."""
    gate = _fired_gate(tmp_path)
    _fire(gate, agent, "update_roster", tool_use_id="t8", volunteer="Dana", field="note", value="x")
    (line,) = gate.ledger.entries()
    assert line.outcome == "pending"


# --------------------------------------------------------------------------
# The decision queue the coordinator answers.
# --------------------------------------------------------------------------


QUESTION = {
    "tool": "send_sms",
    "arguments": {"to": "Marcus", "body": "Free Saturday?"},
    "why_you_are_being_asked": "a text arrives on a real phone",
    "undo_if_you_say_yes": "send a retraction",
}


@pytest.mark.parametrize(
    "answers,approved",
    [(["y"], True), ([""], True), (["n", ""], False), (["q"], False)],
)
def test_the_queue_reads_the_four_answers(answers, approved):
    reply = DecisionQueue(scripted=answers, plain=True).ask(QUESTION, 1)
    assert reply["approved"] is approved


def test_editing_the_wording_returns_it_as_an_edit():
    reply = DecisionQueue(scripted=["e", "Hi Marcus, any chance?"], plain=True).ask(QUESTION, 1)
    assert reply == {"approved": True, "by": "coordinator", "edit": {"body": "Hi Marcus, any chance?"}}
