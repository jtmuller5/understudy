# Understudy: the submission video

Target 4 minutes 45 seconds. The hard limit is 5:00 and a judge who runs out of
patience stops earlier than that, so the whole argument has to land by 3:30 and
the rest is proof.

Two of the five judging criteria, Design and Presentation, are settled entirely
by this recording. It is worth as much as the code.

**Joe records it.** Every command below has been run on the machine it is
recorded from.
Nothing in the demo reaches a person: the numbers are in the reserved 555 range
and the domain is example.org.

## Before you press record

```bash
cd ~/projects/understudy
git status                       # clean, and on the commit you want to show
.venv/bin/pytest -q              # 45 passed. Have this on screen for shot 9.
rm -f ledger.jsonl               # the demo deletes it too; a stale one is confusing on camera
```

Terminal: 100 columns or wider, dark background, font large enough to read on a
phone. Every demo command below carries `--plain`, which turns the colour off so
the recording compresses cleanly.

One rehearsal end to end before the take that counts. The whole thing scripts:

```bash
.venv/bin/python -m understudy.demo --rehearse --plain \
  --answer y \
  --answer e \
  --answer 'Hi Priya, no pressure at all, but is Saturday 9 to 1 possible? We could really use the van.' \
  --answer y
```

`--answer` is repeatable and takes one answer each. Use it rather than
`--answers y,e,...`, which splits on commas and will cut a reworded message in
half at the first comma.

**Record the demo with `--rehearse`.** It replays a fixed sequence of tool calls
through the real gate with no model at all, so the take is identical every time
and the recording cannot be spoiled by a model that decides to phrase something
differently on the day. The gate, the ledger, the queue and the undo text are
all genuine. Shot 9 says this out loud, because a rehearsal harness presented as
a live model is the kind of thing that loses a hackathon on the second viewing.

---

## The script, shot by shot

Voiceover is in **bold**. Everything else is what is on screen.

### Shot 1, the evening this replaces (0:00 to 0:35)

On screen: `examples/riverside.json`, scrolled slowly through the volunteer list
and stopping on the Saturday shift with `"needed": 6` and four names.

> **Riverside Mutual Aid has sixty volunteers, four shifts a week and no staff.
> It is Wednesday night. Saturday's food bank sort needs six people and four
> have signed up.**
>
> **So somebody opens the sheet, works out who said they could do mornings,
> remembers who carried last Saturday and should not be asked again, writes four
> texts, chases the replies, and updates the sheet. None of that is judgement.
> All of it is memory and typing, and it falls on one tired person every week.**

### Shot 2, the reason nobody hands it over (0:35 to 1:00)

On screen: the seed file, on Dana Okonkwo's record. Let the note sit there:
`"asked in July for a lighter couple of months"`.

> **An agent could do all of it in four seconds. The reason nobody lets it is
> the other half of the evening. Dana is free on Saturday. Dana also asked for a
> lighter couple of months. Hand the whole job over and the agent texts her at
> eleven at night, and thirty-nine other people, and nobody finds out until the
> replies arrive.**
>
> **So Understudy does the memory and the typing, and it stops at everything
> else.**

### Shot 3, the boundary is a file the coordinator wrote (1:00 to 1:35)

On screen: `charter.md`, whole, in an editor. Cursor down through `never`,
`ask`, `log`, `limits`.

> **What it may do is this file. The coordinator writes it, in their words, with
> the reason beside every line. Never post in our name, that is a board
> decision. Ask before you text somebody, because it arrives on their real
> phone. Log a roster change, because it is reversible but I want to see it.**
>
> **This is not a prompt the model can be talked out of. It compiles into a
> Strands hook that runs before every tool call the agent makes, including tools
> nobody has written yet and tools that arrive over MCP.**

### Shot 4, run it (1:35 to 1:50)

On screen: type the command and let the header print.

```bash
.venv/bin/python -m understudy.demo --rehearse --plain
```

> **One instruction: Saturday is short, find people who have not been asked
> recently, write to them. And put up a public post while you are there.**

Pause on the header line so `charter: charter.md · ledger: ledger.jsonl` is
readable.

### Shot 5, the moment the entry rests on (1:50 to 2:35)

On screen: decision 1. Do not touch the keyboard for three full seconds. The
four lines that matter are all on screen at once, so let them be read.

```
┌─ decision 1 ─ send_sms
│ to: Nadia Farouk
│ body: Hi Nadia, it is Riverside Mutual Aid. Saturday's food bank sort is two people short, 9 to 1. Any chance you are free? No problem if not.
│ why you: a text arrives on somebody's real phone, so a person chooses to send it
│ undo:    send a second text to Nadia Farouk saying the first one was a mistake. A text cannot be recalled, which is why this one is asked about rather than logged.
```

> **Here it is. The agent found that Nadia signed up at the summer fair and has
> never been given a shift, wrote her a message, and then stopped.**
>
> **It tells you what it wants to do, why it is asking, and what undoing it
> would cost. That last line is the one to read twice. Undoing this is a second
> text saying the first was a mistake. That is not really an undo, and the agent
> says so, which is exactly why this action is a question and not a log line.**

Then press `y`.

### Shot 6, yes, but say it like this (2:35 to 3:05)

On screen: decision 2, Priya. Press `e`, then type the reworded message live.
Slowly. Typing is the point of this shot.

```
Hi Priya, no pressure at all, but is Saturday 9 to 1 possible? We could really use the van.
```

> **The second question is the one every approve-and-deny button gets wrong.
> Most of the time the answer is not yes or no. It is yes, but say it like this.
> If the tool cannot carry that, the coordinator says no and writes the text
> themselves, and the agent has saved them nothing.**
>
> **So the queue has four answers, and the edit is applied to the tool call
> itself. What arrives on Priya's phone is her coordinator's wording, and the
> ledger records what was actually sent.**

Press `y` on decision 3 without comment. It keeps the pace.

### Shot 7, refused, and not asked (3:05 to 3:35)

On screen: the "What the gate decided" table, whole.

```
  allow  read_signup_sheet          not named in the charter, so it is ordinary internal work
  log    draft_message              keep the drafts so I can see what it wanted to send
  ask    send_sms                   a text arrives on somebody's real phone, so a person chooses to send it
  never  post_public                our name in public is a board decision
         stopped: The charter forbids post_public: our name in public is a board decision
```

> **Every decision the boundary made, including the reads it waved through. The
> agent was told to put up a public post. The charter says our name in public is
> a board decision, so the call was cancelled and the model was told why in the
> coordinator's own words. It planned around the boundary instead of arguing
> with it.**

Then scroll to the closing paragraph and stop on the last sentence.

> **And read the last line it wrote. Dana was free, and it did not ask her.**

### Shot 8, the ledger, and the clock (3:35 to 4:10)

On screen: the ledger block, then the quiet-hours run.

> **Every action that reached the world is written down before it happens, with
> its undo, and closed out afterwards. A log written after the fact records only
> what succeeded, and the action you most want to find later is the one that
> half happened.**

```bash
.venv/bin/python -m understudy.demo --rehearse --plain --at 22:30
```

> **Same agent, same instruction, at half past ten at night. It still reads the
> sheet and still writes the drafts. Nobody's phone goes off. The charter has
> quiet hours in it and the coordinator wrote the hours.**

Show `What went out`, and `nothing` under it.

The quiet-hours run ends with a line saying the take's closing summary has been
left off. That is deliberate: the fixed take's last paragraph describes the run
where the texts went out, and reading it over a run the gate stopped would look
like the agent misreporting its own work. Do not cut that line out.

### Shot 9, how it is built, and what is honest about it (4:10 to 4:45)

On screen: the mermaid diagram from `docs/architecture.md`, then `pytest` output.

> **All of it is one Strands hook on BeforeToolCallEvent, the point after the
> model has chosen an action and before the action happens. An ask uses the
> SDK's interrupt, which suspends the run, hands the question to a person, and
> resumes with their answer in place, so the agent does not lose its place while
> somebody decides.**
>
> **Two things in the open. What you have watched is a rehearsal harness: the
> sequence of tool calls is fixed so the recording is repeatable, and everything
> below the model is the real gate. It runs on Bedrock and on a local model
> too. And the charter pattern is not new. It comes from an autonomous loop that
> has been shipping this author's own apps to real app stores for months. No
> code came across, and the idea is here because it survived contact with
> production.**
>
> **Forty-five tests, no model and no network. An agent that does the work, and
> stops where a person should be the one deciding.**

Last frame: the repo URL and one line, `Built by an AI agent working for Joe
Muller`.

---

## The shot list as commands

| Shot | On screen | Command or file |
|---|---|---|
| 1 | signup sheet, six needed and four signed up | `examples/riverside.json` |
| 2 | Dana's record and her note | `examples/riverside.json` |
| 3 | the charter, whole | `charter.md` |
| 4 | the run starting | `.venv/bin/python -m understudy.demo --rehearse --plain` |
| 5 | decision 1, undo line | same run, answer `y` |
| 6 | decision 2, reworded live | same run, answer `e` then type the message |
| 7 | the gate table and the closing paragraph | same run |
| 8 | the ledger, then the quiet-hours run | same run, then `--at 22:30` |
| 9 | the diagram, then the tests | `docs/architecture.md`, `.venv/bin/pytest -q` |

Shots 4 to 8 are one continuous run. Record it in one take and cut inside it.

## Seed state each shot depends on

The demo calls `org.reset()` and deletes the ledger at the start, so the state
below is guaranteed on every run. It is in `examples/riverside.json` and none of
it needs setting up by hand.

- Saturday 15 August, food bank sort, 9 to 1, needs 6, has Tomas, Ellen, Joyce
  and Sam. Short by two.
- Nadia Farouk: signed up at the summer fair, never given a shift, free
  Saturdays. She is who the agent finds, and why the demo has a point.
- Priya Raman: last served in June, drives the van. The reworded message.
- Dana Okonkwo: free on Saturday, worked four days ago, asked in July for a
  lighter couple of months. She is the one the agent leaves alone.

Every name, number and note is invented, and it must stay that way. No real
volunteer goes in the seed file, the repo or the video.

## What must be in the video for the entry to be valid

- A working demo. Shots 4 to 8.
- The problem, and who has it. Shots 1 and 2.
- Why it matters. Shot 2, and the last line of shot 7.
- Under 5 minutes.
- Pre-existing work disclosed. Shot 9 says it out loud, and the README repeats
  it in writing.
