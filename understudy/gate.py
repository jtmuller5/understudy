"""CharterGate -- the charter, enforced on every tool call the agent makes.

This is a Strands `HookProvider`. It subscribes to `BeforeToolCallEvent`, which
fires between the model choosing an action and the action happening, and is the
only place in an agent's life where the action is fully known and has not yet
occurred. Everything else -- a system prompt that asks nicely, a check inside
each tool -- is either advice the model may ignore or a rule that has to be
written again for every tool somebody adds later.

Four outcomes:

    allow  the agent acts. Reading, drafting, calculating: internal work is free.
    log    the agent acts, and the ledger line is written first, with its undo.
    ask    the agent stops and the human answers. Strands' interrupt suspends
           the run, hands the question out, and resumes with the answer in place
           -- so the agent does not lose its place while a person decides.
    never  the tool is cancelled and the model is told why, in the charter's own
           words, so it plans around the boundary instead of retrying against it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from .charter import ALLOW, ASK, LOG, NEVER, Charter
from .ledger import Ledger

#: tool name -> a function that renders the undo instruction from the arguments.
_UNDO: dict[str, Callable[[dict[str, Any]], str]] = {}


def undo(tool_name: str) -> Callable[[Callable[[dict[str, Any]], str]], Callable]:
    """Declare how to undo a tool. A gated tool without one cannot run.

        @undo("send_sms")
        def _(args): return f"reply to {args['to']} retracting the message"
    """

    def register(fn: Callable[[dict[str, Any]], str]) -> Callable:
        _UNDO[tool_name] = fn
        return fn

    return register


class CharterViolation(RuntimeError):
    pass


class CharterGate(HookProvider):
    def __init__(
        self,
        charter: Charter,
        ledger: Ledger | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.charter = charter
        self.ledger = ledger or Ledger()
        self._now = now
        self.asked: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.on_tool)

    # The gate itself. Kept in one function on purpose: a boundary spread over
    # several places is one nobody can read in full, and this one has to be
    # readable by the person it protects.
    def on_tool(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        arguments = dict(event.tool_use.get("input") or {})
        verdict, reason = self.charter.verdict(name)

        if verdict == ALLOW:
            return

        if verdict == NEVER:
            event.cancel_tool = f"The charter forbids {name}: {reason}"
            return

        if self.ledger.outward_count() >= self.charter.outward_actions_per_run:
            event.cancel_tool = (
                f"This run has already taken {self.charter.outward_actions_per_run} "
                "outward actions, which is its limit. Report what is left instead."
            )
            return

        if self.charter.in_quiet_hours(self._now().time()) and verdict != LOG:
            event.cancel_tool = (
                f"{name} reaches a person and it is quiet hours. "
                "Draft it and leave it for the morning."
            )
            return

        how_to_undo = self._undo_for(name, arguments)

        approver = None
        if verdict == ASK:
            question = {
                "tool": name,
                "arguments": arguments,
                "why_you_are_being_asked": reason,
                "undo_if_you_say_yes": how_to_undo,
            }
            self.asked.append(question)
            answer = event.interrupt("charter-gate", reason=question)
            if not _is_yes(answer):
                event.cancel_tool = f"The coordinator declined: {_text(answer) or 'no reason given'}"
                return
            approver = _approver(answer)

        # Written before the call, never after.
        self.ledger.record(
            tool=name,
            verdict=verdict,
            reason=reason,
            arguments=arguments,
            undo=how_to_undo,
            approved_by=approver,
        )

    def _undo_for(self, name: str, arguments: dict[str, Any]) -> str:
        render = _UNDO.get(name)
        if render is None:
            raise CharterViolation(
                f"{name} is gated by the charter but declares no undo. "
                f"Add @undo({name!r}) beside the tool, or move it to 'never'."
            )
        return render(arguments)


def _is_yes(answer: Any) -> bool:
    if isinstance(answer, bool):
        return answer
    if isinstance(answer, dict):
        if "approved" in answer:
            return bool(answer["approved"])
        return _is_yes(answer.get("response"))
    return str(answer).strip().lower() in {"y", "yes", "ok", "approve", "approved", "send"}


def _text(answer: Any) -> str:
    if isinstance(answer, dict):
        return str(answer.get("note") or answer.get("response") or "")
    return str(answer or "")


def _approver(answer: Any) -> str | None:
    if isinstance(answer, dict):
        value = answer.get("by") or answer.get("approved_by")
        return str(value) if value else "human"
    return "human"
