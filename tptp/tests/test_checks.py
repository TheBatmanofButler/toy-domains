"""Tests for checks.py, on the made-up library run with the stand-in prover, and on copies of its files
changed by hand so that each check has something to find."""
import gzip
import json

import pytest

import made_up
from tptp_count import checks
from tptp_count.count import count
from tptp_count.prover import counts, unprocessed


@pytest.fixture
def run(tmp_path, stand_in):
    program = stand_in(made_up.table())
    count(made_up.LIBRARY, tmp_path, program, 20261112)
    return tmp_path, program


def _rewrite(path, change):
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    path.write_text("".join(json.dumps(change(line)) + "\n" for line in lines))


def pilot_calls_file(path, processed, **changed):
    """One saved call in the pilot's form: ALG003-1's unaided call, which the stand-in proves. `processed`, or
    any other of the pilot's counts given by name, replaces the true value."""
    proved = next(e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())
                  if e["ending"] == "proved")
    found = counts(proved)
    record = {"theory": "t", "gi": 0, "call": "160|base", "axioms": ["p(X,q)=X", "p(q,X)=X"], "option": None,
              "goal_denied": "p(a,p(q,b))!=p(a,b)",
              "pilot_result": {"status": "proof", "processed": processed or found["processed"],
                               "generated": found["generated"], "tb": found["terms"],
                               "unprocessed": unprocessed(proved), **changed}}
    with gzip.open(path, "wt") as f:
        f.write(json.dumps(record) + "\n")
    return path


def test_every_check_holds_on_a_clean_run(run, tmp_path):
    data, program = run
    assert checks.pilot_calls(pilot_calls_file(tmp_path / "pilot.jsonl.gz", None), program) == []
    assert checks.repeat(data, program) == []
    assert checks.one_bin_each(made_up.LIBRARY, data) == []
    assert checks.no_silent_does_not_prove(data) == []


def test_a_pilot_call_that_differs_is_named(run, tmp_path):
    _, program = run
    failures = checks.pilot_calls(pilot_calls_file(tmp_path / "pilot.jsonl.gz", 3), program)
    assert len(failures) == 1 and failures[0].startswith("pilot call t 0 160|base")


@pytest.mark.parametrize("name", ["processed", "generated", "tb", "unprocessed", "status"])
def test_the_pilot_check_compares_the_ending_and_every_count(run, tmp_path, name):
    _, program = run
    with gzip.open(pilot_calls_file(tmp_path / "same.jsonl.gz", None), "rt") as f:
        true = json.loads(f.read())["pilot_result"][name]
    other = "limit" if name == "status" else true + 1
    changed = pilot_calls_file(tmp_path / "pilot.jsonl.gz", other) if name == "processed" else \
        pilot_calls_file(tmp_path / "pilot.jsonl.gz", None, **{name: other})
    failures = checks.pilot_calls(changed, program)
    assert len(failures) == 1 and failures[0].startswith("pilot call t 0 160|base")


def test_a_repeat_that_differs_is_named(run):
    data, program = run

    def change(problem):
        if problem["id"] == "ALG004-1":
            problem["calls"][18]["processed"] = 159     # call 20 of all, counting from 0 at ALG003-1's unaided call
        return problem
    _rewrite(data / "problems.jsonl", change)
    assert checks.repeat(data, program) == ["ALG004-1 call 20: again clause limit 160, saved clause limit 159"]


def test_a_missing_or_unknown_bin_is_found(run):
    data, _ = run
    lines = (data / "files.jsonl").read_text().splitlines()
    (data / "files.jsonl").write_text("\n".join(lines[:-1]) + "\n")
    assert len(checks.one_bin_each(made_up.LIBRARY, data)) == 1
    _rewrite(data / "files.jsonl", lambda f: {**f, "bin": "proved"})
    assert len(checks.one_bin_each(made_up.LIBRARY, data)) == 12


@pytest.mark.parametrize("ending", ["term cap", "memory cap", "time cap", "unreadable"])
@pytest.mark.parametrize("number", [0, 4, 29])
def test_every_ending_that_does_not_decide_is_found_in_no_single_fact_helps(run, ending, number):
    data, _ = run

    def changed(problem):
        if problem["id"] == "BLG001-1":
            problem["calls"][number]["ending"] = ending
        return problem
    _rewrite(data / "problems.jsonl", changed)
    failures = checks.no_silent_does_not_prove(data)
    assert failures == [f"Problems/BLG/BLG001-1.p: no single fact helps, but its calls ended {sorted({ending, 'clause limit'})}"]


@pytest.mark.parametrize("problem_id, change, words", [
    ("BLG001-1", lambda p: p["calls"][4].update(ending="time cap"), "no single fact helps, but its calls ended"),
    ("BLG001-1", lambda p: p.update(right=[4]), "right facts [4] do not match"),
    ("ALG004-1", lambda p: p.update(right=[]), "right facts [] do not match"),
    ("ALG003-1", lambda p: p["unaided"].update(ending="clause limit"), "proved unaided, but"),
    ("BLG001-1", lambda p: p["unaided"].update(ending="term cap"), "no single fact helps, with unaided term cap"),
])
def test_a_call_that_did_not_decide_counted_as_does_not_prove_is_found(run, problem_id, change, words):
    data, _ = run

    def changed(problem):
        if problem["id"] == problem_id:
            change(problem)
        return problem
    _rewrite(data / "problems.jsonl", changed)
    failures = checks.no_silent_does_not_prove(data)
    assert failures and any(words in f for f in failures), failures
