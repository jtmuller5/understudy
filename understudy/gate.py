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

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from .charter import ALLOW, ASK, LOG, NEVER, Charter
from .ledger import Entry, Ledger

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
        self.seen: list[dict[str, Any]] = []
        self._pending: dict[str, Entry] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.on_tool)
        registry.add_callback(AfterToolCallEvent, self.on_tool_done)

    # The gate itself. Kept in one function on purpose: a boundary spread over
    # several places is one nobody can read in full, and this one has to be
    # readable by the person it protects.
    def on_tool(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        arguments = dict(event.tool_use.get("input") or {})
        verdict, reason = self.charter.verdict(name)
        # Every decision, including the ones that let the agent through. The
        # ledger is for actions; this is for showing a person that the boundary
        # was consulted on the reads too, and said yes.
        #
        # Keyed by tool use, because an `ask` runs this callback twice: once to
        # raise the interrupt and once when the run resumes with the answer.
        # That is one decision, and counting it twice makes the gate look busier
        # than it is.
        decision = self._decision(event, name, verdict, reason)

        if verdict == ALLOW:
            return

        if verdict == NEVER:
            event.cancel_tool = f"The charter forbids {name}: {reason}"
            decision["refused"] = event.cancel_tool
            return

        # The radius is checked against the same test it counts: actions that
        # reach a person. Applying it to a logged write meant the agent used up
        # its allowance keeping records and then could not do the work.
        reaches_a_person = verdict != LOG
        if reaches_a_person and self.ledger.outward_count() >= self.charter.outward_actions_per_run:
            event.cancel_tool = (
                f"This run has already reached {self.charter.outward_actions_per_run} "
                "people, which is its limit. Report what is left instead."
            )
            decision["refused"] = event.cancel_tool
            return

        if reaches_a_person and self.charter.in_quiet_hours(self._now().time()):
            event.cancel_tool = (
                f"{name} reaches a person and it is quiet hours. "
                "Draft it and leave it for the morning."
            )
            decision["refused"] = event.cancel_tool
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
            if not any(q is decision.get("question") for q in self.asked):
                decision["question"] = question
                self.asked.append(question)
            answer = event.interrupt("charter-gate", reason=question)
            if not _is_yes(answer):
                event.cancel_tool = f"The coordinator declined: {_text(answer) or 'no reason given'}"
                decision["refused"] = event.cancel_tool
                return
            approver = _approver(answer)
            # "Yes, but say it like this." The commonest real answer, and the
            # one an approve/deny button cannot express -- so the person ends up
            # denying and doing it by hand, and the agent has saved nobody
            # anything. An edit is applied to the call itself, so what goes out
            # is their words, and the ledger records the arguments as sent.
            edits = _edits(answer)
            if edits:
                arguments.update(edits)
                event.tool_use["input"] = arguments
                how_to_undo = self._undo_for(name, arguments)

        # Written before the call, never after.
        entry = self.ledger.record(
            tool=name,
            verdict=verdict,
            reason=reason,
            arguments=arguments,
            undo=how_to_undo,
            approved_by=approver,
        )
        self._pending[event.tool_use.get("toolUseId", "")] = entry

    def on_tool_done(self, event: AfterToolCallEvent) -> None:
        """Close the ledger line out.

        The first line said an action was about to be taken and how to undo it.
        This one says how it ended. Both are kept: an action that was started
        and never finished is the one worth being able to find.
        """
        entry = self._pending.pop(event.tool_use.get("toolUseId", ""), None)
        if entry is None:
            return
        if event.exception is not None:
            self.ledger.settle(entry, f"failed: {type(event.exception).__name__}")
        elif event.cancel_message:
            self.ledger.settle(entry, f"cancelled: {event.cancel_message}")
        else:
            self.ledger.settle(entry, str((event.result or {}).get("status", "done")))

    def _decision(self, event: BeforeToolCallEvent, name: str, verdict: str, reason: str) -> dict[str, Any]:
        """One row per tool call, reused when a suspended call resumes."""
        key = event.tool_use.get("toolUseId") or f"{name}-{len(self.seen)}"
        for row in self.seen:
            if row["id"] == key:
                return row
        row = {"id": key, "tool": name, "verdict": verdict, "reason": reason, "refused": None}
        self.seen.append(row)
        return row

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


def _edits(answer: Any) -> dict[str, Any]:
    """Argument changes the human made while approving. Only theirs are applied."""
    if isinstance(answer, dict) and isinstance(answer.get("edit"), dict):
        return dict(answer["edit"])
    return {}


def _approver(answer: Any) -> str | None:
    if isinstance(answer, dict):
        value = answer.get("by") or answer.get("approved_by")
        return str(value) if value else "human"
    return "human"
