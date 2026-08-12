"""Assembling the agent: a model, the coordinator's tools, and the gate.

The gate goes on as a hook rather than into the system prompt on purpose. A
system prompt is advice -- it survives until the model is having an off day, or
until a tool arrives whose name nobody thought to mention. A hook on
`BeforeToolCallEvent` runs on every tool call there is, including tools loaded
from an MCP server that this file has never seen.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from strands import Agent

from .charter import Charter
from .gate import CharterGate
from .ledger import Ledger
from .tools import COORDINATOR_TOOLS

ROOT = Path(__file__).resolve().parents[1]
CHARTER_PATH = ROOT / "charter.md"

#: What the judges see. Bedrock is the default in code and stays the default.
BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

#: Local development, so the whole loop can be exercised for $0.00.
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:4b"

#: Layers to put on the GPU locally. Zero, because this machine's GPUs are
#: already full of other services, and a model that cannot load looks exactly
#: like a broken agent from the outside. A 4B on 16 CPU threads answers slowly
#: and calls tools correctly, which is the half that is being tested here.
OLLAMA_OPTIONS = {"num_gpu": 0, "num_ctx": 16384}

SYSTEM_PROMPT = """\
You are Understudy. You do the repetitive half of a volunteer coordinator's job
for {org}: reading the signup sheet, working out who is free, remembering who
carried the last shift, and writing the messages. Today is {today}.

You are not the coordinator. Some of this job is theirs and always will be:
deciding to ask a particular person to give up a Saturday, changing what
somebody agreed to, saying anything in public. Those actions stop and wait for
them. When one stops, do not go around it, do not find a different tool that
gets the same result, and do not ask twice. Say what you would have done, and
carry on with the part that is yours.

How to work:

- Read first. Find the shift that is short and by how many.
- Ask the people who have been left alone longest. Somebody who worked last
  weekend gets a rest, unless the coordinator says otherwise.
- Write each message to that one person, in plain words, short, and mention
  when you last saw them. No exclamation marks and no fundraising voice.
- Ask a couple more people than the number of places, because some will say no.
- When you finish, tell the coordinator in a short paragraph: what you did,
  what is waiting on them, and what you were stopped from doing.
"""


def build_agent(
    local: bool = False,
    charter_path: str | Path = CHARTER_PATH,
    ledger_path: str | Path = "ledger.jsonl",
    now: Callable[[], datetime] = datetime.now,
    model: Any | None = None,
    org: Any | None = None,
) -> tuple[Agent, CharterGate]:
    """Build the agent and hand back the gate beside it.

    The gate is returned rather than hidden because the caller needs to read
    it: the demo renders `gate.asked`, and a deployment would show the same
    queue in whatever interface the coordinator already has open.
    """
    from . import org as org_module

    the_org = org or org_module.current()
    charter = Charter.load(charter_path)
    gate = CharterGate(charter, Ledger(ledger_path), now=now)

    if model is None:
        model = _ollama() if local else BEDROCK_MODEL

    agent = Agent(
        model=model,
        tools=COORDINATOR_TOOLS,
        hooks=[gate],
        system_prompt=SYSTEM_PROMPT.format(org=the_org.name, today=the_org.today.isoformat()),
        callback_handler=None,
    )
    return agent, gate


def _ollama() -> Any:
    from strands.models.ollama import OllamaModel

    return OllamaModel(host=OLLAMA_HOST, model_id=OLLAMA_MODEL, options=dict(OLLAMA_OPTIONS))
