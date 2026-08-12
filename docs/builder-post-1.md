# builder.aws post 1: the interrupt

Draft. Not published. Publishing is an outward action: log line first, and it
counts against the cycle's public-action budget.

- Venue: builder.aws
- Tag: `#AgentsforHumans` (worth 0.2 of the bonus, up to three posts)
- Length: about 700 words, which is a five-minute read
- Undo: delete the post from the author's builder.aws profile
- Publish after the repo is public, so the code links resolve

---

**Title: The most useful thing in the Strands SDK is the part that stops the agent**

Small community organisations run on one exhausted person with a spreadsheet.
Sixty volunteers, four shifts a week, no staff. Wednesday night, Saturday's food
bank sort needs six people and four have signed up, so somebody opens the sheet,
works out who said they could do mornings, remembers who carried last Saturday
and should not be asked again, writes four texts, chases the replies, and updates
the sheet.

None of that is judgement. All of it is memory and typing, and an agent should
have taken it years ago.

The reason nobody hands it over is the other half of that evening. Dana is free
on Saturday. Dana also asked, in July, for a lighter couple of months. Deciding
whether to ask her anyway is the whole job, and it is not a scheduling problem.
Give an agent the full task and it does that part too, at eleven at night, to
forty people, and nobody finds out until the replies come in.

So the interesting question is not how to make an agent capable enough to run
the roster. It is how to give it the boring half and keep the other half, in a
way the coordinator can read and change without calling anyone.

## A file, not a prompt

Here is the whole boundary for the agent I built. The volunteer coordinator
writes it. The agent cannot edit it.

```markdown
## never
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

Every line carries its reason, because the reason is what a person needs when
they come back in six months to change it.

The obvious way to enforce this is to paste it into the system prompt and hope.
The second most obvious way is a check at the top of every tool, which works
until somebody adds tool number eleven and forgets, or until a tool arrives over
MCP and there is no function of yours to put the check in.

## `BeforeToolCallEvent`

Strands has a hook that fires after the model has chosen an action and before
the action happens. That is the only moment in an agent's life when the action is
fully known and has not yet occurred, which makes it the only honest place to put
a boundary.

```python
class CharterGate(HookProvider):
    def register_hooks(self, registry, **kwargs):
        registry.add_callback(BeforeToolCallEvent, self.on_tool)

    def on_tool(self, event):
        name = event.tool_use["name"]
        verdict, reason = self.charter.verdict(name)

        if verdict == NEVER:
            event.cancel_tool = f"The charter forbids {name}: {reason}"
            return
        ...
```

Cancelling with a message matters more than cancelling. The model is told why in
the coordinator's own words, so it plans around the boundary rather than retrying
against it. When my demo agent is told to put up a public post, it does not
retry: it finishes the work it is allowed to do and hands that one item back.

Then there is the verdict that made the project worth building.

```python
        answer = event.interrupt("charter-gate", reason={
            "tool": name,
            "arguments": arguments,
            "why_you_are_being_asked": reason,
            "undo_if_you_say_yes": self._undo_for(name, arguments),
        })
```

`event.interrupt` suspends the run, hands the question out to a person, and
resumes with their answer in place. The agent does not lose its place while
somebody decides. This is first-class human-in-the-loop in the SDK, and I think
it is the most underused thing in it.

A few things I learned putting weight on it.

**Ask for the undo at declaration time, not at approval time.** Every gated tool
in my agent has to declare how to undo itself, and a gated tool without one
refuses to run at all. It turns out this is a design test rather than a
bookkeeping chore. Writing the undo for `send_sms` gives you "send a second text
saying the first one was a mistake", and the moment you write that down you know
why this action is a question and not a log line.

**The human's answer needs a third option.** Approve and deny cannot express the
commonest real reply, which is "yes, but say it like this". Without it the person
denies and writes the message themselves, and the agent has saved them nothing.
So the response carries an edit, and the gate applies it to `event.tool_use`
before the call goes through. What arrives on the volunteer's phone is the
coordinator's wording.

**An `ask` runs your callback twice.** Once to raise the interrupt and once when
the run resumes with the answer. Anything the callback appends to has to be keyed
by `toolUseId`, or every decision is counted twice and your audit log grows a
phantom.

One more, for anyone writing tests: `HookRegistry.invoke_callbacks` catches
`InterruptException` and returns the interrupts to you. It does not propagate, so
a test built around `pytest.raises(InterruptException)` fails and it looks like
your hook did nothing. Assert on the returned list.

## Where the idea came from

I did not invent this pattern for the hackathon, and it would be dishonest to
imply it. It is lifted from an autonomous loop that has been managing my own
Flutter apps for months: a plain-text charter, an append-only ledger with an undo
on every line, a cap on how many people one run can reach. That loop ships builds
to real app stores, and the charter is the reason I let it. None of its code is
in this project. What carried over is the shape, and the shape is here because it
survived contact with something real.

The agent is Understudy, it is MIT licensed, and it runs its full scenario with
no model and no network so you can watch the boundary work before you pay for a
token.

`#AgentsforHumans`

> Written by an AI agent working for Joe Muller.
