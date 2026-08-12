"""What the agent can actually do.

The split is the whole design, and it is visible here in one screen: the tools
that read, count and draft are ordinary functions the agent uses freely, and
the four that reach a person or change somebody's record each carry an `@undo`
beside them. The gate refuses to run a gated tool that has no undo, so the
undo cannot drift away from the action it reverses -- they are edited in the
same place, by the same person, on the same day.

None of these tools check permission themselves. That is deliberate. A rule
written inside a tool has to be written again in the next tool somebody adds,
and the twentieth one will be the one that forgets.
"""

from __future__ import annotations

from typing import Any

from strands import tool

from . import org as org_module
from .gate import undo


# --------------------------------------------------------------------------
# Reading and thinking. Not named in the charter, so the agent does these
# without asking anybody, which is the point of naming only what matters.
# --------------------------------------------------------------------------


@tool
def read_signup_sheet(shift: str = "") -> dict[str, Any]:
    """Read who has signed up for an upcoming shift.

    Args:
        shift: A shift id, date or name. Left empty, returns the next shift
            that does not yet have enough people.

    Returns:
        The shift, who is on it, and how many more people it needs.
    """
    org = org_module.current()
    target = org.shift(shift) if shift else org.next_shift_needing_people()
    if target is None:
        return {"shift": None, "message": "Every upcoming shift is fully staffed."}
    return {
        "shift_id": target.id,
        "name": target.name,
        "date": target.date,
        "weekday": target.weekday,
        "hours": f"{target.start}-{target.end}",
        "needed": target.needed,
        "signed_up": [org.volunteers[v].name for v in target.assigned],
        "short_by": target.short_by,
        "today": org.today.isoformat(),
    }


@tool
def find_available_volunteers(shift_id: str, rest_days: int = 7) -> dict[str, Any]:
    """Find people who could cover a shift, freshest first.

    Anybody who worked inside the last `rest_days` days is held back and
    reported separately rather than dropped, so the coordinator can still
    choose to ask them. The agent does not make that call on its own.

    Args:
        shift_id: The shift to staff.
        rest_days: How long somebody should be left alone after a shift.

    Returns:
        Candidates in the order they should be asked, plus who was held back
        and why.
    """
    org = org_module.current()
    shift = org.shift(shift_id)
    already = set(shift.assigned)

    candidates, resting, unavailable = [], [], []
    for person in org.volunteers.values():
        if person.id in already:
            continue
        row = {
            "id": person.id,
            "name": person.name,
            "phone": person.phone,
            "days_since_last_shift": person.days_since_served(org.today),
            "hours_this_year": person.hours_this_year,
            "note": person.note,
        }
        if shift.weekday not in person.available:
            unavailable.append({**row, "reason": f"not free on a {shift.weekday}"})
        elif not org.rested_since(person, rest_days):
            resting.append({**row, "reason": f"worked {person.days_since_served(org.today)} days ago"})
        else:
            candidates.append(row)

    candidates.sort(key=lambda r: (-(r["days_since_last_shift"] or 10_000), r["hours_this_year"]))
    return {
        "shift_id": shift.id,
        "short_by": shift.short_by,
        "ask_in_this_order": candidates,
        "resting": resting,
        "unavailable": unavailable,
    }


@tool
def volunteer_history(volunteer: str) -> dict[str, Any]:
    """Look up one person's record: what they have done and when.

    Args:
        volunteer: A volunteer id or name.
    """
    org = org_module.current()
    person = org.volunteer(volunteer)
    return {
        "id": person.id,
        "name": person.name,
        "available": person.available,
        "last_served": person.last_served,
        "days_since_last_shift": person.days_since_served(org.today),
        "hours_this_year": person.hours_this_year,
        "note": person.note,
        "signed_up_for": [s["shift_id"] for s in org.signups if s["volunteer_id"] == person.id],
    }


# --------------------------------------------------------------------------
# Writing things down. Reversible, but the coordinator has to be able to see
# it happened, so the charter says `log` and the ledger line is written first.
# --------------------------------------------------------------------------


@tool
def draft_message(volunteer: str, body: str) -> dict[str, Any]:
    """Write a message for a volunteer and keep it. Sending it is separate.

    Args:
        volunteer: Who it is for.
        body: The message, in the coordinator's ordinary voice.
    """
    org = org_module.current()
    person = org.volunteer(volunteer)
    draft = {"to": person.name, "phone": person.phone, "body": body}
    org.drafts.append(draft)
    return {"drafted": draft, "sent": False}


@undo("draft_message")
def _undo_draft(args: dict[str, Any]) -> str:
    return f"delete the draft addressed to {args.get('volunteer', 'them')}; nothing has been sent"


@tool
def update_roster(volunteer: str, field: str, value: str) -> dict[str, Any]:
    """Change one field on a volunteer's record.

    Args:
        volunteer: Who to change.
        field: One of `available`, `note`, `phone`, `email`.
        value: The new value. For `available`, a comma-separated list of days.
    """
    org = org_module.current()
    person = org.volunteer(volunteer)
    if field not in {"available", "note", "phone", "email"}:
        return {"error": f"{field} is not a field on a volunteer record"}
    before = getattr(person, field)
    setattr(person, field, [d.strip() for d in value.split(",")] if field == "available" else value)
    org.roster_changes.append({"volunteer": person.name, "field": field, "from": before, "to": value})
    return {"volunteer": person.name, "field": field, "was": before, "now": getattr(person, field)}


@undo("update_roster")
def _undo_roster(args: dict[str, Any]) -> str:
    return (
        f"set {args.get('field', 'the field')} back to its previous value on "
        f"{args.get('volunteer', 'the record')}; the old value is in this line's 'was'"
    )


@tool
def record_hours(volunteer: str, shift_id: str, hours: float) -> dict[str, Any]:
    """Put hours on a volunteer's record after they have worked.

    Args:
        volunteer: Who worked.
        shift_id: Which shift.
        hours: How many hours.
    """
    org = org_module.current()
    person = org.volunteer(volunteer)
    person.hours_this_year = round(person.hours_this_year + hours, 2)
    org.hours_logged.append({"volunteer": person.name, "shift_id": shift_id, "hours": hours})
    return {"volunteer": person.name, "added": hours, "hours_this_year": person.hours_this_year}


@undo("record_hours")
def _undo_hours(args: dict[str, Any]) -> str:
    return f"subtract {args.get('hours', '?')} hours again from {args.get('volunteer', 'the record')}"


# --------------------------------------------------------------------------
# Reaching a person. The charter says `ask`, so the agent stops here and the
# coordinator answers. This is the part nobody wants automated, and the part
# every "AI assistant for volunteers" automates first.
# --------------------------------------------------------------------------


@tool
def send_sms(to: str, body: str) -> dict[str, Any]:
    """Send a text message to a volunteer.

    Args:
        to: A phone number, or a volunteer's name or id.
        body: What to send. Keep it short and in plain words.
    """
    org = org_module.current()
    try:
        person = org.volunteer(to)
        number, name = person.phone, person.name
    except KeyError:
        number, name = to, to
    org.sent.append({"to": name, "phone": number, "body": body})
    return {"sent_to": name, "phone": number, "body": body}


@undo("send_sms")
def _undo_sms(args: dict[str, Any]) -> str:
    return (
        f"send a second text to {args.get('to', 'them')} saying the first one was a mistake. "
        "A text cannot be recalled, which is why this one is asked about rather than logged."
    )


@tool
def assign_shift(volunteer: str, shift_id: str) -> dict[str, Any]:
    """Put somebody on a shift.

    Args:
        volunteer: Who to assign.
        shift_id: Which shift.
    """
    org = org_module.current()
    person = org.volunteer(volunteer)
    shift = org.shift(shift_id)
    if person.id in shift.assigned:
        return {"shift_id": shift.id, "message": f"{person.name} is already on this shift."}
    shift.assigned.append(person.id)
    return {
        "shift_id": shift.id,
        "assigned": person.name,
        "now_on_shift": len(shift.assigned),
        "still_short_by": shift.short_by,
    }


@undo("assign_shift")
def _undo_assign(args: dict[str, Any]) -> str:
    return (
        f"take {args.get('volunteer', 'them')} off {args.get('shift_id', 'the shift')} and tell them, "
        "because by then they have rearranged a Saturday"
    )


# --------------------------------------------------------------------------
# Named in the charter's `never` section. The tool exists and works; the gate
# is what stops it. A boundary that depends on the capability being absent is
# not a boundary, it is an omission, and it lasts until somebody adds the tool.
# --------------------------------------------------------------------------


@tool
def post_public(where: str, body: str) -> dict[str, Any]:
    """Post to a public channel: the neighbourhood group, the mailing list, the noticeboard.

    Args:
        where: The channel.
        body: What to post.
    """
    org = org_module.current()
    org.sent.append({"to": f"public:{where}", "phone": "", "body": body})
    return {"posted_to": where}


@tool
def refund_payment(volunteer: str, amount: float) -> dict[str, Any]:
    """Refund money to somebody who paid the organisation.

    Args:
        volunteer: Who to refund.
        amount: How much.
    """
    return {"refunded": volunteer, "amount": amount}


COORDINATOR_TOOLS = [
    read_signup_sheet,
    find_available_volunteers,
    volunteer_history,
    draft_message,
    update_roster,
    record_hours,
    send_sms,
    assign_shift,
    post_public,
    refund_payment,
]
