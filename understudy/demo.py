"""The Saturday-two-short scenario, end to end, in a terminal.

    python -m understudy.demo --local

Riverside Mutual Aid runs a food bank sort every Saturday. It needs six people
and four have signed up. It is Wednesday evening. Somebody has to work out who
is free, remember who carried last Saturday, write four messages, and send
them.

Understudy does the first three. The fourth stops and waits, because a text
arriving on somebody's phone at 9pm asking them to give up their Saturday is
not a thing an agent should decide on its own -- and the coordinator answering
it takes four seconds instead of forty minutes.

Nothing here reaches anybody. `send_sms` appends to a list; the numbers are in
the 555 range, which does not connect.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import org as org_module
from .coordinator import build_agent

TASK = """\
Saturday's food bank shift is short. Work out how short, find the people who
could cover it and have not been asked recently, write each of them a short
message, and send them.

While you are there, the neighbourhood group has been quiet -- put up a public
post asking for new volunteers as well.
"""

DIM = "\033[2m"
BOLD = "\033[1m"
OFF = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"


def _c(text: str, colour: str, plain: bool) -> str:
    return text if plain else f"{colour}{text}{OFF}"


class DecisionQueue:
    """What the coordinator sees. In a deployment this is a phone notification.

    It renders one decision at a time and takes four answers: send it, skip it,
    change the wording first, or stop the agent. The third is the one that
    matters. "Yes, but say it like this" is the commonest real answer, and an
    approve/deny pair cannot express it, so the person ends up denying and
    doing it by hand -- at which point the agent has saved them nothing.
    """

    def __init__(self, scripted: list[str] | None = None, plain: bool = False) -> None:
        self.scripted = list(scripted or [])
        self.plain = plain

    def ask(self, question: dict[str, Any], number: int) -> dict[str, Any] | str:
        args = question.get("arguments", {})
        print()
        print(_c(f"┌─ decision {number} ─ {question['tool']}", BOLD, self.plain))
        for key, value in args.items():
            text = str(value)
            if "\n" in text:
                print(f"│ {key}:")
                for line in text.splitlines():
                    print(f"│     {line}")
            else:
                print(f"│ {key}: {text}")
        print(_c(f"│ why you: {question['why_you_are_being_asked']}", DIM, self.plain))
        print(_c(f"│ undo:    {question['undo_if_you_say_yes']}", DIM, self.plain))
        print("└" + "─" * 60)

        while True:
            answer = self._read("   [y] send  [n] skip  [e] edit the wording  [q] stop > ")
            choice = answer.strip().lower()
            if choice in {"y", "yes", ""}:
                return {"approved": True, "by": "coordinator"}
            if choice in {"n", "no"}:
                note = self._read("   why not (optional) > ").strip()
                return {"approved": False, "note": note or "the coordinator said no"}
            if choice in {"q", "quit"}:
                return {"approved": False, "note": "the coordinator stopped the run"}
            if choice.startswith("e"):
                field = "body" if "body" in args else next(iter(args), "body")
                edited = choice[1:].lstrip("= ").strip() or self._read(f"   new {field} > ").strip()
                if edited:
                    return {"approved": True, "by": "coordinator", "edit": {field: edited}}
            print("   y, n, e or q.")

    def _read(self, prompt: str) -> str:
        if self.scripted:
            answer = self.scripted.pop(0)
            print(f"{prompt}{answer}")
            return answer
        if not sys.stdin.isatty():
            print(f"{prompt}n   (no terminal, so nothing is approved)")
            return "n"
        return input(prompt)


def run(
    local: bool = False,
    scripted: list[str] | None = None,
    ledger_path: str | Path = "ledger.jsonl",
    plain: bool = False,
    now: datetime | None = None,
    model: Any = None,
) -> dict[str, Any]:
    org = org_module.reset()
    Path(ledger_path).unlink(missing_ok=True)
    agent, gate = build_agent(
        local=local,
        ledger_path=ledger_path,
        now=(lambda: now) if now else datetime.now,
        model=model,
        org=org,
    )
    queue = DecisionQueue(scripted=scripted, plain=plain)

    print(_c(f"\n{org.name} — {org.today.isoformat()}", BOLD, plain))
    print(_c("charter: charter.md · ledger: " + str(ledger_path), DIM, plain))
    if type(model).__name__ == "ScriptedModel":
        print(_c("rehearsal: the tool calls are a fixed take. The gate is the real one.", DIM, plain))

    result = agent(TASK)
    number = 0
    while getattr(result, "stop_reason", None) == "interrupt":
        responses = []
        for interrupt in result.interrupts:
            number += 1
            responses.append(
                {
                    "interruptResponse": {
                        "interruptId": interrupt.id,
                        "response": queue.ask(interrupt.reason, number),
                    }
                }
            )
        result = agent(responses)

    _report(gate, org, result, plain)
    return {"org": org, "gate": gate, "result": result}


def _report(gate: Any, org: Any, result: Any, plain: bool) -> None:
    colour = {"allow": GREEN, "log": YELLOW, "ask": YELLOW, "never": RED}
    print(_c("\nWhat the gate decided\n", BOLD, plain))
    for row in gate.seen:
        mark = _c(f"{row['verdict']:<6}", colour.get(row["verdict"], DIM), plain)
        print(f"  {mark} {row['tool']:<26} {_c(row['reason'], DIM, plain)}")
        if row.get("refused"):
            print(f"         {_c('stopped: ' + row['refused'], RED, plain)}")

    print(_c("\nWhat went out\n", BOLD, plain))
    for message in org.sent:
        print(f"  → {message['to']} ({message['phone']})")
        print(f"    {message['body']}")
    if not org.sent:
        print("  nothing")

    print(_c("\nThe ledger\n", BOLD, plain))
    for entry in gate.ledger.entries():
        print(f"  {entry.at}  {entry.tool:<16} {entry.verdict:<5} {entry.outcome}")
        if entry.outcome == "pending":
            print(f"     undo: {_c(entry.undo, DIM, plain)}")

    print(_c("\nWhere the Saturday stands\n", BOLD, plain))
    shift = org.shift("s-2026-08-15-foodbank")
    print(f"  on the shift:   {len(shift.assigned)} of {shift.needed}")
    print(f"  still short by: {shift.short_by}")
    print(f"  drafts kept:    {len(org.drafts)}")
    print()
    print(_c(str(result), "", True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Run against Ollama instead of Bedrock.")
    parser.add_argument(
        "--rehearse",
        action="store_true",
        help="Replay a fixed take through the real gate. No model. For practising the recording.",
    )
    parser.add_argument("--answers", default="", help="Comma-separated canned answers, for a rehearsal.")
    parser.add_argument("--ledger", default="ledger.jsonl")
    parser.add_argument("--plain", action="store_true", help="No colour, for recording.")
    parser.add_argument("--at", default="", help="Pretend the clock says this, e.g. 22:30, to show quiet hours.")
    args = parser.parse_args(argv)

    now = None
    if args.at:
        hour, minute = (int(part) for part in args.at.split(":"))
        now = datetime.now().replace(hour=hour, minute=minute)

    model = None
    if args.rehearse:
        from .rehearsal import SATURDAY_TWO_SHORT, ScriptedModel

        model = ScriptedModel(SATURDAY_TWO_SHORT, name="saturday-two-short")

    run(
        local=args.local,
        scripted=[a for a in args.answers.split(",") if a] or None,
        ledger_path=args.ledger,
        plain=args.plain,
        now=now,
        model=model,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
