"""Tests of prover_key.py: one hand-made case for every line of the bin rule, and one where an option's call
proved the theorem without the option in the proof; with the stand-in prover on the made-up library's two test
problems, one worker and four write the same files, and a run stopped half-way and started again writes the
same files (calls.py)."""
import json

import pytest
from made_up_outputs import output
from made_up_prover import table

from mizar_ladder import prover_key
from mizar_ladder.prover import LIMIT
from mizar_ladder.calls import make_calls
from mizar_ladder.problems import build

CL, P, NL, TC, U = "clause limit", "proved", "nothing left", "time cap", "unreadable"
NAMES = [f"t{n}_aa" for n in range(1, 31)]
PROBLEM = {"id": "test-0001", "theorem": "t1_bb", "held_back": 4, "options": [{"name": n} for n in NAMES]}


def records(without, options=None, unsettled=()):
    """Settled records: the call without an option, then option n as `options[n]` = (ending, used) or a clause
    limit; the options in `unsettled` (None for the call without an option) unsettled, their first run's ending
    as given."""
    options = options or {}
    found = []
    for n in [None] + list(range(1, 31)):
        ending, used = (without, []) if n is None else options.get(n, (CL, []))
        record = {"problem_id": "test-0001", "option": n, "ending": ending, "used": used}
        if n in unsettled:
            record.update(ending="unsettled", endings=[ending, "time cap"])
        found.append(record)
    return found


# (calls, (bin, right options, options proved without being used, reason)). Option 4 is the held-back one.
@pytest.mark.parametrize("calls, expected", [
    (records(P), (prover_key.PROVED_WITHOUT, [], [], None)),
    (records(P, {3: (P, ["t3_aa"])}), (prover_key.PROVED_WITHOUT, [], [], None)),     # no right options here
    (records(P, unsettled=[None]), (prover_key.STOPPED, [], [], "call without an option: unsettled")),
    (records(TC, {3: (P, ["t3_aa"])}), (prover_key.STOPPED, [], [], "call without an option: time cap")),
    (records(CL, {3: (P, ["t3_aa"])}, unsettled=[None]),
     (prover_key.STOPPED, [], [], "call without an option: unsettled")),
    (records(NL, {3: (P, ["t3_aa"])}), (prover_key.HAS_RIGHT, [3], [], None)),          # nothing left: does not prove
    (records(CL, {3: (P, ["t3_aa", "d1_bb"]), 5: (P, ["d1_bb"])}), (prover_key.HAS_RIGHT, [3], [5], None)),
    (records(CL, {5: (P, ["d1_bb"]), 6: (NL, [])}), (prover_key.NONE_PROVES, [], [5], None)),
    (records(NL, {5: (P, ["d1_bb"]), 6: (TC, []), 12: (U, [])}),
     (prover_key.STOPPED, [], [5], "option 6: time cap; option 12: unreadable")),     # options did not decide
    (records(CL, {5: (P, ["t5_aa"])}, unsettled=[5]), (prover_key.STOPPED, [], [], "option 5: unsettled")),
])
def test_every_line_of_the_bin_rule(calls, expected):
    found = prover_key.key_of(PROBLEM, calls)
    assert (found["bin"], found["right"], found["proved_without_use"], found["reason"]) == expected
    assert found["problem_id"] == "test-0001" and found["held_back_ending"] == calls[4]["ending"]


@pytest.fixture
def test_problems(made_up):
    return build(made_up, 7, 2, ("xboole_0", "xboole_1"))[1]


def scenario(test_problems, limit=LIMIT):
    """At `limit`: without an option, a clause limit; the held-back fact proves the theorem and is used; the option
    after it (in the options' order) proves it without being used; every other option, a clause limit."""
    found = {}
    for p in test_problems:
        names = [o["name"] for o in p["options"]]
        held = names[p["held_back"] - 1]
        after = names[p["held_back"] % 30]
        found[p["theorem"]] = {limit: (CL, {held: (P, True), after: (P, False)})}
    return found


def every_file(folder):
    return {str(path.relative_to(folder)): path.read_bytes() for path in sorted(folder.rglob("*")) if path.is_file()}


def test_the_key_with_the_stand_in(made_up, test_problems, stand_in_prover, tmp_path):
    program = stand_in_prover(table(scenario(test_problems)) + [([], output(CL))])
    key = prover_key.run(made_up, test_problems, LIMIT, tmp_path, program)
    for line, p in zip(key, test_problems):
        assert line == {"problem_id": p["id"], "bin": prover_key.HAS_RIGHT, "reason": None, "right": [p["held_back"]],
                        "proved_without_use": [p["held_back"] % 30 + 1], "held_back_ending": P}
    calls = [json.loads(x) for x in (tmp_path / "prover_calls.jsonl").read_text().splitlines()]
    assert len(calls) == 62 and [c["option"] for c in calls[:31]] == [None] + list(range(1, 31))
    assert not any(c["ending"] == "unsettled" for c in calls) and (tmp_path / "raw" / "calls" / "test-0001.jsonl.gz").exists()
    assert [json.loads(x) for x in (tmp_path / "prover_key.jsonl").read_text().splitlines()] == key


def test_one_worker_and_four_write_the_same_files(made_up, test_problems, stand_in_prover, tmp_path):
    program = stand_in_prover(table(scenario(test_problems)) + [([], output(CL))])
    prover_key.run(made_up, test_problems, LIMIT, tmp_path / "one", program, workers=1)
    prover_key.run(made_up, test_problems, LIMIT, tmp_path / "four", program, workers=4)
    assert every_file(tmp_path / "one") == every_file(tmp_path / "four")


def test_a_run_stopped_half_way_and_started_again_writes_the_same_files(made_up, test_problems, stand_in_prover,
                                                                         tmp_path):
    program = stand_in_prover(table(scenario(test_problems)) + [([], output(CL))])
    every = prover_key.every_call
    make_calls(made_up, test_problems, every, LIMIT, tmp_path / "whole", program)
    # Stopped after the first problem, with a half-written result left behind.
    make_calls(made_up, test_problems[:1], every, LIMIT, tmp_path / "again", program)
    (tmp_path / "again" / "work" / "test-0002.json.part").write_text("{")
    (tmp_path / "again" / "prover_calls.jsonl").unlink()
    make_calls(made_up, test_problems, every, LIMIT, tmp_path / "again", program)
    assert not (tmp_path / "again" / "work" / "test-0002.json.part").exists()     # written over, then moved
    assert every_file(tmp_path / "whole") == every_file(tmp_path / "again")
