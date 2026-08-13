"""The video script, checked against the thing it films.

`docs/video-script.md` is what Joe reads while recording, and every command and
every on-screen block in it is a claim about what the demo prints. A claim that
has drifted does not fail anything: it fails on camera, once, on the day, and
the recording is the half of the entry that Design and Presentation are marked
from.

So the script is a test fixture. The commands are parsed out of it and run, and
the blocks it shows on screen are matched against the real output.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPT = (ROOT / "docs" / "video-script.md").read_text()
SEED = json.loads((ROOT / "examples" / "riverside.json").read_text())
SHIFT = "s-2026-08-15-foodbank"


def _blocks() -> list[tuple[str, str]]:
    """Every fenced block as (language, body).

    Scanned line by line rather than matched with a regex: a closing fence and
    an untagged opening fence are the same three characters, so a pattern reads
    the prose between two blocks as a third block.
    """
    found: list[tuple[str, str]] = []
    language: str | None = None
    body: list[str] = []
    for line in SCRIPT.splitlines():
        if line.startswith("```"):
            if language is None:
                language, body = line[3:].strip(), []
            else:
                found.append((language, "\n".join(body)))
                language = None
        elif language is not None:
            body.append(line)
    assert language is None, "an unclosed fence in the script"
    return found


def _bash_commands() -> list[list[str]]:
    """Every demo invocation in the script, as argv, line continuations joined."""
    found = []
    for language, block in _blocks():
        if language != "bash":
            continue
        for line in block.replace("\\\n", " ").splitlines():
            line = line.split("  #")[0].strip()
            if "understudy.demo" in line:
                argv = shlex.split(line)
                found.append(argv[argv.index("understudy.demo") + 1 :])
    return found


def _screen_block(marker: str) -> list[str]:
    """A fenced block with no language tag -- what the script says is on screen."""
    for language, block in _blocks():
        if not language and marker in block:
            return block.splitlines()
    raise AssertionError(f"no on-screen block in the script contains {marker!r}")


def _run(argv: list[str], tmp_path: Path, answers: list[str] | None = None) -> str:
    """Run the demo the way the script does and give back what it printed."""
    from understudy import demo as demo_module

    out: list[str] = []
    real_print = print
    ledger = ["--ledger", str(tmp_path / "ledger.jsonl")]
    for answer in answers or []:
        argv = argv + ["--answer", answer]
    import builtins

    def capture(*parts, **kwargs):  # keep the output, print nothing
        out.append(" ".join(str(p) for p in parts))

    builtins.print = capture
    try:
        assert demo_module.main(argv + ledger) == 0
    finally:
        builtins.print = real_print
    return "\n".join(out)


def test_the_script_actually_contains_demo_commands():
    """Discovery fails open: an empty list would pass every test below."""
    assert len(_bash_commands()) >= 3, "the script's demo commands stopped parsing"


@pytest.mark.parametrize("argv", _bash_commands(), ids=lambda a: " ".join(a))
def test_every_command_in_the_script_runs(argv, tmp_path):
    """Joe types these. Each one exits clean with no terminal and no model."""
    assert "--rehearse" in argv, "the recorded run must not depend on a live model"
    output = _run(argv, tmp_path)
    assert "What the gate decided" in output


def test_the_decision_card_on_screen_is_the_one_the_demo_prints(tmp_path):
    """Shot 5. The four lines a judge is given three silent seconds to read."""
    card = _screen_block("decision 1")
    output = _run(["--rehearse", "--plain"], tmp_path)
    for line in card:
        assert line in output, f"shot 5 shows a line the demo no longer prints: {line!r}"


def test_the_gate_table_on_screen_is_the_one_the_demo_prints(tmp_path):
    """Shot 7. The script says it is ten lines and fits one screen; hold it to that."""
    table = _screen_block("post_public")
    assert len(table) == 10, "shot 7 says ten lines on one screen"

    # The terminal width Joe is told to set, and the width the shot claims the
    # table fits, are the same number and both are a claim about this table. At
    # 100 columns the two `ask send_sms` rows wrap and the ten lines become
    # twelve, which is the shot's whole argument gone.
    widths = {int(n) for n in re.findall(r"(\d+) columns", SCRIPT)}
    assert len(widths) == 1, f"the script names more than one terminal width: {widths}"
    assert max(len(line) for line in table) <= widths.pop()
    # The take's own answers: a decision the coordinator refuses adds a
    # `stopped:` line to the table, and shot 7 is filmed after three yeses.
    output = _run(["--rehearse", "--plain"], tmp_path, answers=["y", "y", "y"])
    assert "\n".join(table) in output, "the table has to appear whole, in this order"


def test_the_reworded_message_survives_the_answer_flag(tmp_path):
    """Shot 6, typed live, and it has two commas in it.

    `--answers` splits on commas, so the shot that carries Design and Creativity
    is the one it cuts in half. The script tells Joe to use `--answer` instead;
    this is that instruction, executable.
    """
    reworded = _screen_block("no pressure at all")[0]
    assert "," in reworded, "the trap only exists for a message with a comma in it"

    output = _run(["--rehearse", "--plain"], tmp_path, answers=["y", "e", reworded, "y"])
    assert reworded in output
    # Scoped to what was sent: the decision card shows the agent's draft too,
    # which is the before-and-after the shot is built on.
    sent = output.split("What went out")[1].split("The ledger")[0]
    assert reworded in sent
    assert "we could use the van. Last time" not in sent, "the agent's draft, not the coordinator's"

    halved = _run(["--rehearse", "--plain", "--answers", "y,e," + reworded + ",y"], tmp_path)
    assert reworded not in halved, "if --answers stopped splitting, the script's warning is stale"


def test_the_quiet_hours_run_sends_nothing(tmp_path):
    """Shot 8. Same agent, same instruction, half past ten at night."""
    argv = next(a for a in _bash_commands() if "--at" in a)
    output = _run(argv, tmp_path, answers=["y", "y", "y"])
    what_went_out = output.split("What went out")[1]
    assert what_went_out.strip().startswith("nothing")
    assert "closing summary" in output, "shot 8 says this line is deliberate; do not cut it"


def test_the_seed_state_each_shot_depends_on():
    """Shots 1 and 2 point a camera at this file. The bullets under 'Seed state'."""
    shift = next(s for s in SEED["shifts"] if s["id"] == SHIFT)
    assert (shift["needed"], len(shift["assigned"])) == (6, 4), "short by two"
    assert (shift["start"], shift["end"]) == ("09:00", "13:00")

    people = {v["name"]: v for v in SEED["volunteers"]}
    assert people["Nadia Farouk"]["last_served"] is None, "never given a shift"
    assert "Saturday" in people["Nadia Farouk"]["available"]
    assert people["Priya Raman"]["last_served"].startswith("2026-06"), "last served in June"
    assert "drives" in people["Priya Raman"]["note"]
    assert "lighter" in people["Dana Okonkwo"]["note"]
    assert people["Dana Okonkwo"]["last_served"] > people["Priya Raman"]["last_served"]


def test_no_real_person_is_in_the_seed_file():
    """Fiction, and it stays fiction -- in the repo and on camera."""
    for volunteer in SEED["volunteers"]:
        assert volunteer["phone"].startswith("+1-555-"), volunteer["name"]
        assert volunteer["email"].endswith("@example.org"), volunteer["name"]


def test_the_test_count_the_script_puts_on_screen_is_the_real_one():
    """Shot 9 shows `pytest -q` and says the number out loud. Both have to be true.

    Derived from pytest itself rather than copied, because the number changes
    every time somebody adds a test -- which is exactly when the script goes
    stale and nobody looks.
    """
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    count = int(re.search(r"(\d+) tests? collected", collected.stdout).group(1))

    assert f"{count} passed" in SCRIPT, f"the script's `pytest -q` line does not say {count} passed"
    assert _spell(count).lower() in SCRIPT.lower(), f"shot 9 does not say {_spell(count)} out loud"

    readme = (ROOT / "README.md").read_text()
    assert f"{count} tests" in readme, f"the README still claims a different number than {count}"


def _spell(number: int) -> str:
    tens = {
        2: "Twenty",
        3: "Thirty",
        4: "Forty",
        5: "Fifty",
        6: "Sixty",
        7: "Seventy",
        8: "Eighty",
        9: "Ninety",
    }
    units = [
        "",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
    ]
    assert 20 <= number < 100, "spell out a number outside this range by hand"
    word = tens[number // 10]
    return word if number % 10 == 0 else f"{word}-{units[number % 10]}"
