"""The prover's key for every test problem, at the experiment's limit (prover.LIMIT) or the one stage 2 is given.

For each test problem: the call without an option, then one call per option, all of it twice, then settled. An
option is right under the prover's key when its call proved the theorem and the option is among the facts the proof
uses. The key is defined when the call without an option does not prove the theorem (clause limit, or nothing left:
a finished search with no proof is a verdict). The bin is decided in this order: the call without an option is
settled and proved it ("proved without an option"); it did not decide or is unsettled ("stopped for another
reason"); some option is right ("has right options"); every option's call decided ("no option proves it");
otherwise "stopped for another reason". A problem stopped for another reason says why, and the list of right
options is empty outside "has right options". Each line also gives how the held-back option's call ended: "nothing
left" there, with every fact the author cited given, is a check on the translation from Mizar.
"""
import json
from pathlib import Path

from mizar_ladder import prover
from mizar_ladder.calls import make_calls
from mizar_ladder.problems import OPTIONS
from mizar_ladder.settle import decided, settle

PROVED_WITHOUT, HAS_RIGHT, NONE_PROVES, STOPPED = ("proved without an option", "has right options",
                                                   "no option proves it", "stopped for another reason")
BINS = (PROVED_WITHOUT, HAS_RIGHT, NONE_PROVES, STOPPED)


def every_call(problem):
    return [None] + list(range(1, OPTIONS + 1))


def key_of(problem, records):
    """The problem's line of prover_key.jsonl from its settled calls."""
    by_option = {r["option"]: r for r in records}
    names = [o["name"] for o in problem["options"]]
    proved = [n for n in range(1, OPTIONS + 1) if decided(by_option[n]) and by_option[n]["ending"] == prover.PROVED]
    right = [n for n in proved if names[n - 1] in by_option[n]["used"]]
    without = by_option[None]
    undecided = [n for n in range(1, OPTIONS + 1) if not decided(by_option[n])]
    reason = None
    if without["ending"] == prover.PROVED:
        bin_name = PROVED_WITHOUT
    elif not decided(without):
        bin_name, reason = STOPPED, f"call without an option: {without['ending']}"
    elif right:
        bin_name = HAS_RIGHT
    elif not undecided:
        bin_name = NONE_PROVES
    else:
        bin_name = STOPPED
        reason = "; ".join(f"option {n}: {by_option[n]['ending']}" for n in undecided)
    return {"problem_id": problem["id"], "bin": bin_name, "reason": reason,
            "right": right if bin_name == HAS_RIGHT else [],
            "proved_without_use": [n for n in proved if n not in right],
            "held_back_ending": by_option[problem["held_back"]]["ending"]}


def run(library, test, limit, data, program, workers=1):
    """Makes the calls twice under `data`/raw/key/, settles them into `data` (prover_calls.jsonl, raw/calls/,
    settled.json) and writes `data`/prover_key.jsonl. Returns the key's lines."""
    data = Path(data)
    for run_name in ("first", "second"):
        make_calls(library, test, every_call, limit, data / "raw" / "key" / run_name, program, workers)
    records = settle(data / "raw" / "key" / "first", data / "raw" / "key" / "second", data)
    by_problem = {}
    for record in records:
        by_problem.setdefault(record["problem_id"], []).append(record)
    key = [key_of(p, by_problem[p["id"]]) for p in test]
    (data / "prover_key.jsonl").write_text("".join(json.dumps(line) + "\n" for line in key))
    return key
