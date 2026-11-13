"""Tests of problems.py: a tiny build (depths 2 and 3, searched to 3 moves, 5 test and 10 training problems per
depth), its counts, its checks, and the same files from the same seed whatever the number of processes."""
import copy

import pytest

from fe_ladder.identities import problem_key
from fe_ladder.identity_text import read_identity
from fe_ladder.problems import (DEPTH_FULL, DEPTH_ONE, SAME_AS_TAKEN, TAKEN, BuildError, build_problems, check_sets,
                                check_solved_again, read_jsonl, write_jsonl)
from fe_ladder.shortest import PlainSearch

TINY = dict(test_per_depth=5, train_per_depth=10, depths=(2, 3), most_moves=3)


@pytest.fixture(scope="module")
def tiny():
    return build_problems(8, workers=2, **TINY)


def test_counts_are_exact_and_add_up(tiny):
    test, train, summary = tiny
    assert summary["test_count_by_depth"] == {2: 5, 3: 5}
    assert summary["training_count_by_depth"] == {2: 10, 3: 10}
    assert summary["training_depths_left_short"] == []
    assert sum(summary["count_by_kind"].values()) == summary["attempts"]
    assert summary["count_by_kind"][TAKEN] == 30
    assert set(summary["count_by_kind"]) <= {TAKEN, SAME_AS_TAKEN, DEPTH_FULL, DEPTH_ONE, "already proved",
                                            "deeper than most_moves", "no equation found", "no goal found"}
    assert sorted(p["id"] for p in test if p["depth"] == 2) == [f"test-2-{n:04d}" for n in range(1, 6)]
    assert sorted(p["id"] for p in train if p["depth"] == 3) == [f"train-3-{n:04d}" for n in range(1, 11)]


def test_attempts_are_taken_in_order_test_places_first(tiny):
    test, train, _ = tiny
    for depth in (2, 3):
        test_attempts = [p["attempt"] for p in test if p["depth"] == depth]
        train_attempts = [p["attempt"] for p in train if p["depth"] == depth]
        assert test_attempts == sorted(test_attempts) and train_attempts == sorted(train_attempts)
        assert max(test_attempts) < min(train_attempts)


def test_no_problem_repeats_within_or_across_the_sets(tiny):
    test, train, _ = tiny
    keys = [problem_key(read_identity(p["equation"]), read_identity(p["goal"])) for p in test + train]
    assert len(set(keys)) == len(keys)


def test_every_problem_has_right_moves_found_again_by_the_plain_search(tiny):
    test, train, _ = tiny
    for p in test + train:
        assert p["right_moves"] and p["seed"] == 8 and p["planted"]["first_chain"]
        plain = PlainSearch().solve(read_identity(p["equation"]), read_identity(p["goal"]), 3)
        assert (plain.depth, plain.right, plain.proofs, plain.sequences) == (
            p["depth"], p["right_moves"], p["proofs"], p["sequences"])


def test_the_same_seed_gives_the_same_files_in_one_process(tiny, tmp_path):
    test, train, summary = tiny
    again_test, again_train, again_summary = build_problems(8, workers=1, **TINY)
    for name, first, second in (("test", test, again_test), ("train", train, again_train)):
        write_jsonl(tmp_path / f"{name}_1.jsonl", first)
        write_jsonl(tmp_path / f"{name}_2.jsonl", second)
        assert (tmp_path / f"{name}_1.jsonl").read_text() == (tmp_path / f"{name}_2.jsonl").read_text()
    assert read_jsonl(tmp_path / "test_1.jsonl") == test
    assert again_summary["count_by_kind"] == summary["count_by_kind"]


def test_a_depth_with_too_few_training_problems_says_so(tiny):
    test, _, _ = tiny
    last_test_attempt = max(p["attempt"] for p in test)
    _, train, summary = build_problems(8, most_attempts=last_test_attempt + 30, **TINY)
    assert summary["attempts"] == last_test_attempt + 30
    assert summary["training_depths_left_short"]
    for depth in summary["training_depths_left_short"]:
        assert summary["training_count_by_depth"][depth] == sum(p["depth"] == depth for p in train) < 10


def test_a_test_set_that_cannot_be_filled_stops_the_build():
    with pytest.raises(BuildError, match="test set has"):
        build_problems(8, most_attempts=5, **TINY)


def test_the_checks_on_the_sets(tiny):
    test, train, summary = tiny
    check_sets(test, train, summary, 5, 10)
    with pytest.raises(BuildError, match="same problem"):
        check_sets(test, train + [dict(test[0], id="train-x")], summary, 5, 10)
    with pytest.raises(BuildError, match="no right move"):
        check_sets([dict(test[0], right_moves=[])] + test[1:], train, summary, 5, 10)
    with pytest.raises(BuildError, match="more than 10"):
        check_sets(test, train, dict(summary, training_count_by_depth={2: 11, 3: 10}), 5, 10)
    many_late = dict(summary, count_by_kind=dict(summary["count_by_kind"], **{"out of time": summary["attempts"] // 50}))
    with pytest.raises(BuildError, match="out of time"):
        check_sets(test, train, many_late, 5, 10)


def test_a_recorded_depth_that_is_not_found_again_stops_the_build(tiny):
    test, _, _ = tiny
    check_solved_again(test, most_moves=3)
    wrong = copy.deepcopy(test[0])
    wrong["right_moves"] = wrong["right_moves"][:-1] + [99]
    with pytest.raises(BuildError, match="solved again"):
        check_solved_again([wrong], most_moves=3)


def test_the_out_of_time_limit_counts_over_the_problems_that_reached_the_search(tiny):
    test, train, summary = tiny
    # 1,000 attempts, 900 of which made no problem: 100 reached the search. 1 out of time is 1%, allowed; 2 are
    # more than 1%, though they are only 0.2% of the attempts.
    for out_of_time, allowed in ((1, True), (2, False)):
        kinds = {"no equation found": 600, "no goal found": 300, "out of time": out_of_time,
                 TAKEN: 100 - out_of_time}
        made_up = dict(summary, attempts=1000, count_by_kind=kinds)
        if allowed:
            check_sets(test, train, made_up, 5, 10)
        else:
            with pytest.raises(BuildError, match="2 of 100 problems searched ran out of time"):
                check_sets(test, train, made_up, 5, 10)
