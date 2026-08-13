# Devpost submission write-up

Draft. Joe pastes these into the Devpost form; the field names are the form's own.
Nothing here is published by the loop.

- Track: **Good Neighbor**
- Repo: https://github.com/jtmuller5/understudy
- Video: recorded from `docs/video-script.md`, ≤5 minutes
- Still needed from Joe: AWS Builder ID, the video upload, and the submit button

---

## Project name

Understudy

## Tagline

An agent that does a volunteer coordinator's repetitive work and stops at every action a
person should own. The stopping rule is a file the coordinator writes.

## Inspiration

Riverside Mutual Aid, the organisation in the demo, is fiction, but the evening is not.
Sixty volunteers, four shifts a week, no staff. Wednesday night, Saturday's food bank
sort needs six people and four have signed up, so somebody opens the sheet, works out who
said they could do mornings, remembers who carried last Saturday and should not be asked
again, writes four texts, chases the replies, and updates the sheet.

None of that is judgement. All of it is memory and typing, and an agent should have taken
it years ago.

The reason nobody hands it over is the other half of that evening. Dana is free on
Saturday. Dana also asked, in July, for a lighter couple of months. Deciding whether to
ask her anyway is the job, and it is not a scheduling problem. Give an agent the whole
task and it does that part too, at eleven at night, to forty people, and nobody finds out
until the replies come in.

So the question we built against was not how to make an agent capable enough to run a
roster. It was how to give it the boring half and keep the other half, in a way the
coordinator can read and change without calling anyone.

## What it does

Understudy reads the signup sheet, works out who fits the gap and who has been left alone
longest, drafts the four texts, and then stops, because sending a text to a real person
is not its call.

What it may do is a file the coordinator writes, in their own words:

```markdown
## never
- refund_*: money that has already moved is not the agent's to move
- post_public: our name in public is a board decision

## ask
- send_sms: a text arrives on somebody's real phone, so a person chooses to send it
- assign_shift: it changes what somebody has agreed to do on their Saturday

## log
- update_roster: reversible, but I need to see it happened

## limits
- outward_actions_per_run: 3
- quiet_hours: 21:00-08:00
```

That file is the whole boundary, and the agent cannot edit it. Anything it does not name
is allowed, so reading, checking and drafting stay free.

Two things come out, and both can be read in a minute. The first is a decision queue: one
question at a time, each carrying what the agent wants to do, why it is asking, and the
undo if you say yes.

```
Understudy wants to text +1 555 0143 (Dana R.)
  "Hi Dana, Saturday 9am is two short. Any chance you're free?"
  Asking because: a text arrives on somebody's real phone.
  If you say yes, undo is: send a retraction to +1 555 0143.
  [y] send   [n] skip   [e] edit
```

The third answer is the one that matters. "Yes, but say it like this" is the commonest
real reply, and an approve/deny prompt cannot carry it, so the person denies, writes the
text themselves, and the agent has saved them nothing. An `e` answer is applied to the
tool call, and what goes out is their wording.

The second is a ledger. Every action that reaches the world is written there *before* it
happens, with the undo beside it, then settled afterwards with the result. A log written
after the fact records only what succeeded, and the line you most want is the one for the
action that half happened.

## How we built it

The boundary is a Strands hook, not a prompt.

`BeforeToolCallEvent` fires after the model has chosen an action and before the action
happens. That is the one moment when the action is fully known and has not yet occurred,
and it is the same moment for all ten tools here plus any that arrive later over MCP.
`charter.md` is parsed at startup into a `HookProvider` on that event, and each verdict is
a line of SDK:

- `never` sets `event.cancel_tool`, with the coordinator's own reason as the text. The
  model is told why in their words, so it plans around the boundary instead of retrying
  against it.
- `ask` calls `event.interrupt()`, which suspends the run mid-turn and resumes it in
  place carrying the human's answer.
- `log` writes the ledger line, with the undo, before returning.
- `allow` returns.

`AfterToolCallEvent` settles the ledger line with what actually happened. Two limits sit
on the same hook: a blast radius that counts people reached rather than lines logged, and
quiet hours, which let the drafting finish and stop the phones going off at 11pm.

The model is Bedrock by default and Ollama with `--local`, because a boundary you can only
exercise by paying an API bill is one that stops being exercised. `--rehearse` replays a
fixed sequence of tool calls through the real gate with no model at all. The choosing is
fixed, everything below it is genuine, and it says so on screen when it starts. The video
is recorded from that, so the take is identical every time.

56 tests run with no model and no network. `git clone`, `pip install -e ".[dev]"`,
`pytest`: a judge needs no AWS account to see the gate work.

## Challenges we ran into

`HookRegistry.invoke_callbacks` catches `InterruptException` and returns it in a list
rather than propagating it. A test written the obvious way, asserting
`pytest.raises(InterruptException)`, fails, and it fails looking exactly as though the
gate never fired. Assert on the returned interrupts instead.

An `ask` runs the `BeforeToolCallEvent` callback twice for one tool call: once to raise
the interrupt, once when the run resumes with the answer. Nothing in the signature warns
you. Anything the callback counts or appends has to be keyed by `toolUseId`, or every
decision is recorded twice and the blast radius halves itself.

The first blast radius counted ledger lines, which meant the agent spent its whole
allowance on paperwork and stopped before doing any of the work. Counting people reached
is the version that survives contact with a real evening.

The last one is the demo itself. The rehearsal's closing paragraph belongs to the run
where the texts went out, so on a run the gate stopped it would report messages nobody
received: an agent misreporting its own work, in the demo where the boundary is the whole
point. It now leaves that paragraph off and says why, and two tests hold it there.

## Accomplishments that we're proud of

The gate is legible to the person it protects. A volunteer coordinator can open
`charter.md`, read why each line is there, change one, and get different behaviour on the
next run without touching Python or asking anyone.

It is also enforced rather than requested. The rule lives outside the model's context, in
data, on a hook that fires for every tool including ones added after the charter was
written.

And the whole thing runs on a laptop with no server, no database and no login. The charter
and the ledger are files, the roster is a Python module, and the only thing that leaves
the machine is the model call.

## What we learned

Human-in-the-loop is usually built as a plan the agent presents at the end of a turn.
Stopping mid-turn is a different, better thing, and `event.interrupt()` makes it about ten
lines. It is the most non-obvious capability in the SDK and we would lead with it again.

The other lesson is that "approve or deny" is the wrong shape for the question. Most of
the time the person does not want to block the agent; they want to change one sentence.

## What's next for Understudy

Deployment to Bedrock AgentCore so a coordinator answers decisions from their phone rather
than a terminal, the charter compiled from more than one file so a board can own the
`never` rules while a coordinator owns the rest, and a real integration behind `send_sms`.

The parts we would not change are the file and the hook.

## Built with

Strands Agents SDK · Amazon Bedrock · Python 3.10+ · Ollama (optional local model) ·
pytest · Mermaid

## Disclosure

This project was built by an AI agent working for Joe Muller, and the write-up above was
drafted by that agent.

Every line of code in the repository was written during the submission period. The design
was not new, and that is deliberate. The charter file, the pre-written ledger and the
blast radius come from an autonomous agent loop the author has been running since well
before this hackathon, one that ships Flutter apps to the App Store and Google Play with
no human approving each step. No code from that loop is in this repository. Understudy is
the first time the pattern has been built as a Strands hook, and the first time it has
been pointed at somebody else's job.

The organisation, the volunteers and the phone numbers in the demo are fiction.
