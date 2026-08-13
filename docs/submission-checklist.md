# Submission checklist

Every requirement in the Agents for Humans official rules, with what satisfies it and how
that was checked. Read from https://agentsforhumans.devpost.com/rules on 2026-08-13, at the
"Updated 8/12/26" revision.

Submission closes **2026-09-14, 5:00pm PDT**. Judging runs 2026-09-15 to 2026-10-08 and
winners are announced on or around 2026-10-14.

Status column: **done** is verified below, **Joe** is waiting on him and cannot be done by
an agent, **gap** is work still outstanding.

## Required to enter

| # | Rules say | Status | What satisfies it |
|---|---|---|---|
| 1 | Register on the hackathon website with a Devpost account | **Joe** | Task #942. Signing up and accepting rules is a legal person's act. |
| 2 | Sign up for an AWS account | **Joe** | Task #942. |
| 3 | Install the Strands Agents SDK | done | `pyproject.toml` requires `strands-agents`; 56 tests import and exercise it. |
| 4 | Provide an AWS Builder ID in the submission | **Joe** | Task #942, same sitting as the Devpost account. |
| 5 | Complete every required field on the "Enter a Submission" page | **Joe** | `docs/submission.md` holds the answers under the form's own field names. |

## Required in the project

| # | Rules say | Status | What satisfies it |
|---|---|---|---|
| 6 | Newly created during the submission period (opened 2026-08-10) | done | First commit 2026-08-12. Every line of code was written after the period opened. |
| 7 | Pre-existing work disclosed | done | `README.md` "Pre-existing work, disclosed", and the same paragraph in `docs/submission.md`. The charter and ledger pattern is borrowed; no code is. |
| 8 | Built with Strands Agents, non-trivially | done | The gate is a `HookProvider` on `BeforeToolCallEvent` using `cancel_tool` and `interrupt()`, not a `@tool` wrapper. |
| 9 | Installs and runs on its intended platform | done | Proved from an empty venv in cycle 1047 with the README's own commands: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`. |
| 10 | Functions as depicted in the video and the text description | done | `tests/test_video_script.py` runs every command in the script and matches its on-screen blocks against real output. |
| 11 | Third party SDKs used within their licence | done | Strands (Apache 2.0), pytest (MIT), Ollama optional. No API is called that needs anyone's permission. |
| 12 | Free of charge and unrestricted for judges until judging ends | done | Public repo, MIT, no login. `pytest` and `--rehearse` need no account, no key and no network. |
| 13 | All materials in English | done | Repo, README, script and write-up are English. |

## Required in the submission

| # | Rules say | Status | What satisfies it |
|---|---|---|---|
| 14 | Text description of features and functionality | done | `docs/submission.md`, in the form's field order. |
| 15 | Public repo URL on GitHub, GitLab or Bitbucket | done | https://github.com/jtmuller5/understudy. Anonymous `curl` returns 200 and the API reports `private=false`. |
| 16 | Repo holds all source, assets and instructions to make it work | done | `understudy/`, `tests/`, `examples/riverside.json`, `charter.md`, and the README's "Run it". |
| 17 | MIT or Apache licence **file**, detectable at the top of the repo page | done | `LICENSE`, MIT. GitHub's own detection agrees: `gh api repos/jtmuller5/understudy --jq .license.spdx_id` returns `MIT`, which is what puts it in the About panel. |
| 18 | README | done | `README.md`, 196 lines. |
| 19 | Architecture diagram | done | `README.md` "Architecture", a rendered mermaid flowchart. `docs/architecture.md` holds a second view, the gated `send_sms` as a sequence. |
| 20 | Video, five minutes maximum | **Joe** | `docs/video-script.md` is a 4:45 script in nine shots, each one a command. There is no screen on this machine, so he records. |
| 21 | Video shows the project working | **Joe** | Shots 4 to 8 are the demo running. |
| 22 | Pitch covers the problem, who it is for, and why it matters | **Joe** | Shot 1 the problem, shot 2 who and why, shot 7's last line why it matters. |
| 23 | Video public on YouTube or Vimeo | **Joe** | No other host qualifies. Unlisted is not public; set it public before pasting the link. |
| 24 | One track chosen | done | **Good Neighbor**. Thinnest field of the three and the one that scores Potential Impact best. |
| 25 | Live demo link | optional | Skipped. It strengthens Technical Implementation, and it costs AWS money the loop cannot spend. Joe's call if he wants it. |
| 26 | AgentCore deployment | optional | Same reasoning as 25. Named in "What's next" instead. |

## Bonus, worth up to +0.6

| # | Rules say | Status | What satisfies it |
|---|---|---|---|
| 27 | A builder.aws post about the build, published publicly, 0.2 each to a maximum of three | drafted | `docs/builder-post-1.md`. Publishing is outward and is Joe's to press, since it needs his builder.aws account. |
| 28 | "Agents for Humans" in the **title** | **gap** | The rules were changed on 2026-08-12 and the `#AgentsforHumans` tag requirement was dropped. The title now carries the bonus. Post 1's title has to be rewritten before it goes up or the 0.2 is forfeit. |

## What is left, in the order it has to happen

1. Joe registers on Devpost, creates the AWS account and gets a Builder ID (#942).
2. Joe records the video from `docs/video-script.md` at 110 columns, uploads it to YouTube
   or Vimeo, and makes it public.
3. Post 1 gets a title carrying "Agents for Humans", then Joe publishes it on builder.aws.
4. Joe pastes `docs/submission.md` into the form, adds the repo link, the video link and
   the Builder ID, picks Good Neighbor, and submits (#974).

Steps 2 and 4 are the only ones on the critical path. A draft can be saved on Devpost
before it is submitted, so 4 can start early and be finished when the video lands.

## How to re-check this file

```bash
gh api repos/jtmuller5/understudy --jq '{private,license:.license.spdx_id}'
curl -s -o /dev/null -w '%{http_code}\n' https://github.com/jtmuller5/understudy
.venv/bin/python -m pytest -q
curl -sL https://agentsforhumans.devpost.com/rules   # the rules have been revised once already
```

Written by an autonomous agent working for Joe Muller.
