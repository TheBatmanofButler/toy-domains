"""Tests for settle.py, on pairs of counts of the made-up library made with the stand-in prover (and copies of
them changed by hand): what is settled, what is unsettled and where its files go, and every difference that must
stop the stage."""
import gzip
import json
import shutil

import pytest

import made_up
from tptp_count.count import count
from tptp_count.prover import HEURISTICS
from tptp_count.settle import SettleError, settle

SEED = 20261112
ALG004_AXIOMS = "(m(X,m(Y,Z))=m(m(X,Y),Z))"
REAL = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
NORMAL = made_up._printed([made_up.G] + made_up.FACTS) + REAL["nothing left"]


def _row(heuristic, limit, ordering, answer):
    """A stand-in answer for one of the deriving runs of ALG004's axiom set (axiom set 1)."""
    return (["--print-saturated=eE", f"--processed-clauses-limit={limit} ", f"-t{ordering}",
             HEURISTICS[heuristic] + "\n", ALG004_AXIOMS], answer)


CUT_OFF = made_up._printed(made_up.FACTS[:3]) + REAL["time cap"]


def _two_counts(tmp_path, stand_in, table):
    program = stand_in(table)
    for name in ("first", "second"):
        count(made_up.LIBRARY, tmp_path / name, program, SEED)
    return tmp_path / "first", tmp_path / "second"


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _final(folder):
    """Every final file, by name, as bytes."""
    found = {name: (folder / name).read_bytes() for name in ("files.jsonl", "problems.jsonl", "derived_facts.jsonl")}
    found.update({f"calls/{p.name}": p.read_bytes() for p in sorted((folder / "calls").iterdir())})
    return found


def _call_lines(path):
    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f]


@pytest.fixture
def same(tmp_path, stand_in):
    return _two_counts(tmp_path, stand_in, made_up.table())


@pytest.fixture
def unsettled(tmp_path, stand_in):
    return _two_counts(tmp_path, stand_in, made_up.unsettled_table())


def test_two_identical_counts_settle_to_the_first(same, tmp_path):
    first, second = same
    settled = settle(first, second, tmp_path / "out")
    assert settled == {"unsettled": [], "cut off differently": []}
    assert _final(tmp_path / "out") == _final(first)
    assert json.loads((tmp_path / "out" / "settled.json").read_text()) == settled


def test_a_set_with_no_list_in_both_and_other_runs_cut_off_is_settled_and_named(tmp_path, stand_in):
    first, second = _two_counts(tmp_path, stand_in, [
        _row("S3", 150, "LPO4", {"first time": CUT_OFF, "after": NORMAL}),
        _row("S3", 150, "KBO6", {"first time": NORMAL, "after": CUT_OFF})] + made_up.table())
    assert [r["ending"] for r in _jsonl(first / "derived_facts.jsonl")[1]["runs"]][::3] == ["nothing left", "time cap"]
    assert [r["ending"] for r in _jsonl(second / "derived_facts.jsonl")[1]["runs"]][::3] == ["time cap", "nothing left"]
    settled = settle(first, second, tmp_path / "out")
    assert settled == {"unsettled": [], "cut off differently": [made_up.SET_1]}
    assert _final(tmp_path / "out") == _final(first)


def test_a_set_with_a_list_in_one_count_only_is_unsettled_and_its_files_go_where_the_rule_says(unsettled, tmp_path):
    first, second = unsettled
    assert _jsonl(first / "derived_facts.jsonl")[1]["facts"] is not None
    assert _jsonl(second / "derived_facts.jsonl")[1]["facts"] is None
    before = {f["path"]: f["bin"] for f in _jsonl(first / "files.jsonl")}
    assert before["Problems/ALG/ALG004-1.p"] == "a problem" and before["Problems/BLG/BLG001-1.p"] == "no single fact helps"
    out = tmp_path / "out"
    settled = settle(first, second, out)
    assert settled == {"unsettled": [{"axiom_set": 1, "first_file": made_up.SET_1, "files": made_up.UNSETTLED_FILES}],
                       "cut off differently": []}
    assert [(f["path"], f["bin"], f["why"]) for f in _jsonl(out / "files.jsonl")] == made_up.UNSETTLED_BINS
    problems = {p["id"]: p for p in _jsonl(out / "problems.jsonl")}
    first_problems = {p["id"]: p for p in _jsonl(first / "problems.jsonl")}
    for name in ("ALG004-1", "BLG001-1"):
        assert problems[name] == {k: first_problems[name][k] for k in ("id", "path", "area", "axioms", "goal",
                                                                        "unaided", "seed")}
        assert [c["call"] for c in _call_lines(out / "calls" / f"{name}.jsonl.gz")] == ["unaided"]
        assert _call_lines(out / "calls" / f"{name}.jsonl.gz")[0] == _call_lines(first / "calls" / f"{name}.jsonl.gz")[0]
    for name in ("ALG004-3", "ALG004-4"):     # proved unaided, and unaided call that did not decide: as counted
        assert problems[name] == first_problems[name]
        assert (out / "calls" / f"{name}.jsonl.gz").read_bytes() == (first / "calls" / f"{name}.jsonl.gz").read_bytes()
    assert list(problems) == [f["problem_id"] for f in _jsonl(out / "files.jsonl") if f["problem_id"]]
    # the unsettled set's final record shows no facts; each count keeps its own record
    final_sets, first_sets = _jsonl(out / "derived_facts.jsonl"), _jsonl(first / "derived_facts.jsonl")
    assert final_sets[1] == {**first_sets[1], "facts": None, "unsettled": True} and first_sets[1]["facts"]
    assert final_sets[:1] + final_sets[2:] == first_sets[:1] + first_sets[2:]
    assert all("unsettled" not in s for s in final_sets[:1] + final_sets[2:])
    # the other way round: the same bins
    settle(second, first, tmp_path / "other")
    assert [(f["path"], f["bin"], f["why"]) for f in _jsonl(tmp_path / "other" / "files.jsonl")] == made_up.UNSETTLED_BINS


def test_two_different_lists_for_one_set_stop(tmp_path, stand_in):
    changed = NORMAL.replace(made_up.FACTS[29], "m(X1,i(i(i(i(i(e))))))=m(i(i(i(i(i(e))))),X1)")
    first, second = _two_counts(tmp_path, stand_in, [
        _row("S3", 150, "KBO6", {"first time": NORMAL, "after": changed})] + made_up.table())
    with pytest.raises(SettleError, match=r"axiom set 1 \(Problems/ALG/ALG004-1.p\): the two counts derived two "
                                          r"different lists of facts"):
        settle(first, second, tmp_path / "out")


def _changed_copy(first, tmp_path, name, change):
    second = tmp_path / "changed"
    shutil.copytree(first, second)
    path = second / name
    if name.endswith(".gz"):
        lines = _call_lines(path)
        change(lines)
        path.write_bytes(gzip.compress("".join(json.dumps(line) + "\n" for line in lines).encode(), mtime=0))
    else:
        lines = _jsonl(path)
        change(lines)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return second


def _by(field, value, change):
    def changing(lines):
        for line in lines:
            if line.get(field) == value:
                change(line)
    return changing


@pytest.mark.parametrize("name, change, words", [
    ("files.jsonl", _by("path", "Problems/ALG/ALG003-1.p", lambda f: f.update(bin="a problem")),
     "Problems/ALG/ALG003-1.p: differs"),
    ("problems.jsonl", _by("id", "ALG004-1", lambda p: p.update(right=p["right"][:1])),
     "Problems/ALG/ALG004-1.p: differs"),
    ("calls/ALG005-1.jsonl.gz", _by("call", "unaided", lambda c: c.update(output=c["output"].replace("1", "2", 1))),
     "Problems/ALG/ALG005-1.p: differs"),
    ("calls/axiom_set_1.jsonl.gz", _by("run", 2, lambda r: r.update(output=r["output"].replace("1", "2", 1))),
     r"axiom set 1 \(Problems/ALG/ALG004-1.p\): its deriving runs differ"),
    ("derived_facts.jsonl", _by("axiom_set", 1, lambda s: s["runs"][4].update(ending="clause limit")),
     r"axiom set 1 \(Problems/ALG/ALG004-1.p\): its deriving runs differ"),
])
def test_a_difference_on_a_settled_set_stops(same, tmp_path, name, change, words):
    first, _ = same
    with pytest.raises(SettleError, match=words):
        settle(first, _changed_copy(first, tmp_path, name, change), tmp_path / "out")


def test_a_difference_in_the_unaided_call_of_a_file_on_an_unsettled_set_stops(unsettled, tmp_path):
    first, second = unsettled
    changed = _changed_copy(second, tmp_path, "calls/ALG004-1.jsonl.gz", _by(
        "call", "unaided", lambda c: c.update(output=c["output"].replace("1", "2", 1))))
    with pytest.raises(SettleError, match="Problems/ALG/ALG004-1.p: its unaided call differs"):
        settle(first, changed, tmp_path / "out")


def test_two_counts_over_different_libraries_stop(same, tmp_path, stand_in):
    first, _ = same
    library = tmp_path / "library"
    shutil.copytree(made_up.LIBRARY, library)
    path = library / "Problems" / "ALG" / "ALG007-1.p"
    path.write_text(path.read_text().replace("k(k(X)) = k(X)", "k(k(k(X))) = k(X)"))
    count(library, tmp_path / "other", stand_in(made_up.table()), SEED)
    with pytest.raises(SettleError, match="the two counts hold different axiom sets"):
        settle(first, tmp_path / "other", tmp_path / "out")


def test_settling_the_same_two_counts_twice_writes_identical_files(unsettled, tmp_path):
    first, second = unsettled
    settle(first, second, tmp_path / "out")
    once = _final(tmp_path / "out") | {"settled.json": (tmp_path / "out" / "settled.json").read_bytes()}
    (tmp_path / "out" / "calls" / "left_over.jsonl.gz").write_bytes(b"")     # anything left from before goes
    settle(first, second, tmp_path / "out")
    assert _final(tmp_path / "out") | {"settled.json": (tmp_path / "out" / "settled.json").read_bytes()} == once


def test_counts_whose_saved_results_have_no_axiom_set_number_stop(same, tmp_path):
    first, second = same
    path = first / "work" / "problems" / "ALG003-1.json"
    result = json.loads(path.read_text())
    del result["axiom_set"]
    path.write_text(json.dumps(result))
    with pytest.raises(SettleError, match="no axiom set number"):
        settle(first, second, tmp_path / "out")


def test_counts_that_read_different_files_stop(same, tmp_path, stand_in):
    first, _ = same
    library = tmp_path / "library"
    shutil.copytree(made_up.LIBRARY, library)
    shutil.copyfile(library / "Problems" / "ALG" / "ALG002-1.p", library / "Problems" / "ALG" / "ALG002-2.p")
    count(library, tmp_path / "other", stand_in(made_up.table()), SEED)
    with pytest.raises(SettleError, match="the two counts read different files"):
        settle(first, tmp_path / "other", tmp_path / "out")


def test_counts_that_put_other_files_on_an_unsettled_set_stop(unsettled, tmp_path):
    first, second = unsettled
    path = second / "work" / "problems" / "ALG003-1.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "axiom_set": 1}))
    with pytest.raises(SettleError, match="the two counts put different files on the unsettled axiom sets"):
        settle(first, second, tmp_path / "out")
