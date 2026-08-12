"""A model that does not think, for rehearsing the demo.

Recording a five-minute video against a live model means recording it several
times, and the agent picks a slightly different order every take. That is fine
in the product and useless on camera: the take that shows the gate stopping the
public post is the take where the model happened to try it.

`ScriptedModel` replays a fixed sequence of tool calls through the real event
loop. Everything downstream is genuine -- the same `Agent`, the same
`BeforeToolCallEvent`, the same interrupt, the same gate, the same ledger. Only
the choosing is fixed.

It is a rehearsal harness and a test fixture, and it is labelled as one
wherever it is used. The submitted demo runs on Bedrock.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, AsyncIterable

from strands.models.model import Model


class ScriptedModel(Model):
    """Replay a fixed list of turns.

    Each turn is either a string (the agent says it and stops) or a list of
    `(tool_name, arguments)` pairs (the agent calls those tools). A turn is
    consumed per model call, so a cancelled or interrupted tool still advances
    the script exactly as a real model's next turn would.
    """

    def __init__(self, turns: list[Any], name: str = "scripted") -> None:
        self.turns = list(turns)
        self.name = name
        self.calls = 0
        self._config: dict[str, Any] = {"model_id": f"scripted::{name}"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    async def structured_output(
        self, output_model: type, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise NotImplementedError("the rehearsal harness does not do structured output")

    async def stream(self, *args: Any, **kwargs: Any) -> AsyncIterable[dict]:
        turn = self.turns[self.calls] if self.calls < len(self.turns) else _CLOSING
        self.calls += 1

        yield {"messageStart": {"role": "assistant"}}
        if isinstance(turn, str):
            async for event in _text(turn):
                yield event
            yield {"messageStop": {"stopReason": "end_turn"}}
        else:
            for index, (tool_name, arguments) in enumerate(turn):
                # The id must be unique across the whole run, not within the
                # turn: the gate keys a decision by it, and two calls sharing
                # an id read as one call that resumed.
                async for event in _tool_call(index, f"{tool_name}-{self.calls}", tool_name, arguments):
                    yield event
            yield {"messageStop": {"stopReason": "tool_use"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }


_CLOSING = (
    "That is everything I can do on my own. What is waiting on you is in the "
    "decision queue, and what I was stopped from doing is in the ledger."
)


async def _text(body: str):
    yield {"contentBlockStart": {"start": {}}}
    yield {"contentBlockDelta": {"delta": {"text": body}}}
    yield {"contentBlockStop": {}}


async def _tool_call(index: int, use_id: str, name: str, arguments: dict[str, Any]):
    import json

    yield {
        "contentBlockStart": {
            "start": {"toolUse": {"name": name, "toolUseId": use_id}},
            "contentBlockIndex": index,
        }
    }
    yield {
        "contentBlockDelta": {
            "delta": {"toolUse": {"input": json.dumps(arguments)}},
            "contentBlockIndex": index,
        }
    }
    yield {"contentBlockStop": {"contentBlockIndex": index}}


SHIFT = "s-2026-08-15-foodbank"

#: The take. One tool per turn, so each decision lands on its own and the
#: person watching can read it -- which is also how it behaves in real use,
#: because the gate suspends the run on the first one it has to ask about.
SATURDAY_TWO_SHORT: list[Any] = [
    [("read_signup_sheet", {})],
    [("find_available_volunteers", {"shift_id": SHIFT, "rest_days": 7})],
    [("volunteer_history", {"volunteer": "Dana Okonkwo"})],
    [
        (
            "draft_message",
            {
                "volunteer": "Nadia Farouk",
                "body": (
                    "Hi Nadia, it is Riverside Mutual Aid. Saturday's food bank sort is two "
                    "people short, 9 to 1. You signed up at the summer fair and we have not "
                    "given you a shift yet. Any chance you are free? No problem if not."
                ),
            },
        )
    ],
    [
        (
            "send_sms",
            {
                "to": "Nadia Farouk",
                "body": (
                    "Hi Nadia, it is Riverside Mutual Aid. Saturday's food bank sort is two "
                    "people short, 9 to 1. Any chance you are free? No problem if not."
                ),
            },
        )
    ],
    [
        (
            "send_sms",
            {
                "to": "Priya Raman",
                "body": (
                    "Hi Priya, Saturday 9 to 1 is short and we could use the van. Last time "
                    "we saw you was June. Free at all?"
                ),
            },
        )
    ],
    [("assign_shift", {"volunteer": "Nadia Farouk", "shift_id": SHIFT})],
    [
        (
            "post_public",
            {
                "where": "the neighbourhood group",
                "body": "Riverside Mutual Aid needs Saturday volunteers. Message us to join.",
            },
        )
    ],
    [("update_roster", {"volunteer": "Nadia Farouk", "field": "note", "value": "first shift 2026-08-15"})],
    (
        "Saturday is one short rather than two. Nadia is on it and Priya has been asked.\n\n"
        "Waiting on you: Priya has not replied yet.\n\n"
        "I was stopped from posting to the neighbourhood group -- the charter says our name "
        "in public is a board decision, so that one is yours. Dana is free on Saturday and I "
        "did not ask her: she worked four days ago and asked for a lighter couple of months."
    ),
]
