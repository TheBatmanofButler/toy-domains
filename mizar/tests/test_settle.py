"""Tests of settle.py on hand-made pairs of runs: identical; the same ending with different counts and different
other facts (settled, the first run kept); proved in one run and the clause limit in the other (unsettled); proved
in both with the option used in one only (unsettled); a cap in either run against a verdict in the other
(unsettled); an unsettled call's final record keeps no used facts or counts, and settled.json names it by
problem, option number and fact name; the shares in settled.json worked by hand; old files cleared; runs of
different calls refused."""
import gzip
import json

import pytest

from mizar_ladder.settle import SettleError, decided, settle


def record(problem_id, option, ending="clause limit", processed=250, used=(), generated=10, terms=900):
    return {"problem_id": problem_id, "option": option, "option_name": None if option is None else f"t{option}_a",
            "ending": ending, "processed": processed, "generated": generated, "terms": terms, "used": list(used),
            "exit_code": 0}


def a_run(folder, records):
    (folder / "raw" / "calls").mkdir(parents=True)
    (folder / "prover_calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    for problem_id in {r["problem_id"] for r in records}:
        (folder / "raw" / "calls" / f"{problem_id}.jsonl.gz").write_bytes(gzip.compress(folder.name.encode(), mtime=0))
    return folder


RUN = [record("test-0001", None), record("test-0001", 1, "proved", 40, ["t1_a", "d1_a"]),
       record("test-0002", None, "nothing left")]


def settled(tmp_path, first, second):
    out = tmp_path / "out"
    return settle(a_run(tmp_path / "first", first), a_run(tmp_path / "second", second), out), out


def summary(out):
    return json.loads((out / "settled.json").read_text())


def test_identical_runs_settle_every_call(tmp_path):
    final, out = settled(tmp_path, RUN, RUN)
    assert final == RUN and all(decided(r) for r in final)
    assert [json.loads(line) for line in (out / "prover_calls.jsonl").read_text().splitlines()] == final
    assert summary(out) == {"calls": 3, "unsettled": 0, "unsettled_share": 0.0,
                            "by_way": {"the endings differed": 0, "the use of the option differed": 0},
                            "unsettled_calls": []}
    # The first run's outputs are kept.
    assert gzip.decompress((out / "raw" / "calls" / "test-0001.jsonl.gz").read_bytes()) == b"first"


def test_the_same_ending_with_other_counts_and_other_facts_is_settled_and_the_first_run_kept(tmp_path):
    second = [record("test-0001", None, processed=900, generated=99, terms=12345),
              record("test-0001", 1, "proved", 77, ["t1_a", "d9_a", "d8_a"], generated=3), RUN[2]]
    final, out = settled(tmp_path, RUN, second)
    assert final == RUN and summary(out)["unsettled"] == 0


@pytest.mark.parametrize("first_ending, second_ending", [
    ("proved", "clause limit"), ("clause limit", "proved"),          # a verdict changed
    ("time cap", "proved"), ("proved", "time cap"),                  # a cap in either run against a verdict
    ("memory cap", "nothing left"), ("clause limit", "term cap"),
])
def test_endings_that_differ_make_the_call_unsettled(tmp_path, first_ending, second_ending):
    used = ["t1_a"]
    first = [RUN[0], record("test-0001", 1, first_ending, 40, used if first_ending == "proved" else []), RUN[2]]
    second = [RUN[0], record("test-0001", 1, second_ending, 50, used if second_ending == "proved" else []), RUN[2]]
    final, out = settled(tmp_path, first, second)
    assert [r["ending"] for r in final] == ["clause limit", "unsettled", "nothing left"] and not decided(final[1])
    assert final[1] == dict(first[1], ending="unsettled", endings=[first_ending, second_ending], used=None,
                            processed=None, generated=None, terms=None, exit_code=None)
    assert summary(out)["unsettled_calls"] == [{"problem_id": "test-0001", "option": 1, "option_name": "t1_a",
                                                "why": "the endings differed", "endings": [first_ending, second_ending]}]


def test_proved_in_both_with_the_option_used_in_one_only_is_unsettled(tmp_path):
    second = [RUN[0], record("test-0001", 1, "proved", 40, ["d1_a"]), RUN[2]]
    final, out = settled(tmp_path, RUN, second)
    assert final[1]["ending"] == "unsettled" and final[1]["endings"] == ["proved", "proved"]
    # Neither run's used facts are kept as if settled: the first used t1_a, the second did not.
    assert final[1]["used"] is None and final[1]["processed"] is None
    assert summary(out)["by_way"] == {"the endings differed": 0, "the use of the option differed": 1}
    # Without an option there is no option to use: two proofs with other facts agree.
    second = [RUN[0], RUN[1], record("test-0002", None, "nothing left", 3)]
    assert settled(tmp_path / "again", RUN, second)[0] == RUN


def test_the_shares_worked_by_hand(tmp_path):
    # Eight calls: one with endings that differ, one with the use of the option that differs: 2 of 8 = .25.
    first = [record("test-0001", None)] + [record("test-0001", n, "proved", 40, [f"t{n}_a"]) for n in range(1, 8)]
    second = list(first)
    second[3] = record("test-0001", 3, "time cap", None)
    second[5] = record("test-0001", 5, "proved", 40, ["d1_a"])
    _, out = settled(tmp_path, first, second)
    found = summary(out)
    assert (found["calls"], found["unsettled"], found["unsettled_share"]) == (8, 2, 0.25)
    assert found["by_way"] == {"the endings differed": 1, "the use of the option differed": 1}
    assert [(u["option"], u["why"]) for u in found["unsettled_calls"]] == [(3, "the endings differed"),
                                                                            (5, "the use of the option differed")]


def test_no_old_file_is_left_after_settling(tmp_path):
    out = tmp_path / "out"
    (out / "raw" / "calls").mkdir(parents=True)
    (out / "raw" / "calls" / "test-0099.jsonl.gz").write_bytes(b"old")
    (out / "prover_calls.jsonl").write_text("old\n")
    (out / "settled.json").write_text("old")
    (out / "other.json").write_text("not the settling's")
    settled(tmp_path, RUN, RUN)
    assert sorted(p.name for p in (out / "raw" / "calls").iterdir()) == ["test-0001.jsonl.gz", "test-0002.jsonl.gz"]
    assert "old" not in (out / "prover_calls.jsonl").read_text() and "old" not in (out / "settled.json").read_text()
    assert (out / "other.json").read_text() == "not the settling's"


def test_runs_of_different_calls_are_refused(tmp_path):
    with pytest.raises(SettleError, match="different calls"):
        settled(tmp_path, RUN, RUN[:2])
