# Understudy

An agent that does a volunteer coordinator's repetitive work and stops at every
action a person should own.

Built with the [Strands Agents SDK](https://strandsagents.com) for the AWS
**Agents for Humans** hackathon — Good Neighbor track.

> Written by an AI agent working for Joe Muller.

## The problem

Small community organisations run on one exhausted person with a spreadsheet.
Riverside Mutual Aid has 60 volunteers, four shifts a week and no staff. The
coordinator's evening looks like this: open the signup sheet, see Saturday
morning is two people short, remember who said they could do mornings, remember
who did it last week and shouldn't be asked again, write four texts, chase two
replies, update the sheet.

None of that is judgement. All of it is memory and typing. It is exactly the
work an agent should take.

The reason nobody hands it over is the other half of the evening: the part where
you decide to text Dana, who is having a hard month, and ask her to give up a
Saturday. Hand the whole job to an agent and it will do that part too, at 11pm,
to forty people, and no one will find out until the replies arrive.

## What this does

Understudy does the memory and the typing. It reads the sheet, works out who
fits, drafts the messages — and then stops, because sending a text to a real
person is not its call.

What it may do is written by the coordinator, in a file, in their words:

```markdown
## never
- refund_*: money that has already moved is not the agent's to move

## ask
- send_sms: a text arrives on somebody's real phone, so a person chooses to send it

## log
- update_roster: reversible, but I need to see it happened

## limits
- outward_actions_per_run: 3
- quiet_hours: 21:00-08:00
```

That file is the whole boundary. It is not a prompt the model may argue with —
it is compiled into a hook that runs before every tool call, including tools
added later and tools that arrive over MCP.

## What comes out

Two things, and the coordinator can read both in a minute.

**A decision queue** — the questions, one at a time, each with what the agent
wants to do, why it is asking, and what happens if you say no:

```
Understudy wants to text +1 555 0143 (Dana R.)
  "Hi Dana — Saturday 9am is two short. Any chance you're free?"
  Asking because: a text arrives on somebody's real phone.
  If you say yes, undo is: send a retraction to +1 555 0143.
  [y] send   [n] skip   [e] edit
```

**A ledger** — every action that reached the world, written *before* it
happened, with the undo beside it. A log written afterwards records only what
succeeded, and the action you most want to find is the one that half happened.

## Run it

```bash
pip install -e ".[dev]"
pytest                    # the gate, with no model and no network
python -m understudy.demo # the full scenario
```

The demo runs against Amazon Bedrock by default and against a local Ollama model
with `--local`, because a boundary you can only exercise by paying an API bill
is one that stops being exercised.

## Architecture

See [`docs/architecture.md`](docs/architecture.md).

## Licence

MIT. See [`LICENSE`](LICENSE).
