"""Tests of programs/lookahead.py: perfect up to its depth, and problems worked by hand."""
import pytest
from conftest import record
from small_problems import small_problems

from fe_ladder.identity_text import write_identity
from fe_ladder.programs.common import score
from fe_ladder.programs.lookahead import picks, search

# Constant family: f(x + y) = f(x). Proof of the goal: y=1 gives f(x + 1) = f(x) (option 3), then x=0 on that
# gives f(1) = f(0); the goal is their sum. x=1 (option 5) gives f(x + 1) = f(1), which has every term of the
# goal and nothing else, so the page score puts it first, though it is not on the way to a 2-move proof.
ASTRAY = ("f(x + y) - f(x) = 0", "f(x + 1) - f(x) + f(1) - f(0) = 0")


@pytest.fixture(scope="module")
def near():
    """200 small problems of depth 1 to 3."""
    found = []
    for n, (equation, goal) in enumerate(small_problems(400, seed=4)):
        r = record(write_identity(equation), write_identity(goal), f"test-x-{n:04d}", most_moves=3)
        if r["depth"]:
            found.append(r)
    return found[:200]


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_scores_1_on_every_problem_within_its_depth(depth, near):
    within = [r for r in near if r["depth"] <= depth]
    assert len(near) == 200 and len(within) >= 20
    for r, pick in zip(within, picks(within, depth)):
        assert score(pick, r["right_moves"]) == pytest.approx(1), r["id"]


def test_hand_worked_cauchy_three_times():
    # f(3x) = 3f(x) from Cauchy needs 3 moves (see test_shortest.py); the right first moves are options 1 (y=x)
    # and 5 (y=x+y). One move ahead nothing proves it; four options leave a page of score (0, -4): f(0) = 0,
    # f(2x) = 2f(x), f(x + y) = f(x) - f(-y) and f(2x + y) = f(x) + f(x + y) each add one term not in the goal.
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    pick, examined = search(r, 1)
    assert pick == [0.25, 0.25, 0, 0, 0.25, 0.25, 0, 0, 0] and examined == 9
    assert score(pick, r["right_moves"]) == 0.5
    pick, examined = search(r, 3)
    # Examined: 9 sequences of one move, 119 of two, 2117 of three (the last as counted by the search).
    assert pick == [0, 0.5, 0, 0, 0, 0.5, 0, 0, 0] and examined == 9 + 119 + 2117


def test_hand_worked_one_move_is_led_astray_and_two_are_not():
    r = record(*ASTRAY)
    assert r["depth"] == 2 and r["right_moves"] == [3]
    assert search(r, 1)[0] == [0, 0, 0, 0, 0, 1.0, 0, 0, 0]
    assert search(r, 2)[0] == [0, 0, 0, 1.0, 0, 0, 0, 0, 0]
    assert search(r, 3)[0] == search(r, 2)[0]       # the proof at 2 moves stops the search there


def test_depth_must_be_at_least_1():
    with pytest.raises(ValueError):
        search(record(*ASTRAY), 0)


def test_the_earlier_run_s_score_only_lookahead_gives_its_scores_on_the_60_earlier_problems():
    # The earlier lookahead (kept in tests/score_only_lookahead.py) scores pages by the page score alone and never
    # asks whether the goal is proved; the earlier run's scores for it, at 1, 2 and 3 moves, are in the fixture.
    from conftest import read_fixture
    from score_only_lookahead import search as score_only
    for p in read_fixture("earlier_problems.jsonl"):
        for depth in (1, 2, 3):
            assert score(score_only(p, depth), p["right_moves"]) == pytest.approx(
                p["score_only_lookahead"][str(depth)]), (p["id"], depth)


def test_the_programs_keep_their_caches_for_one_problem_only():
    from conftest import read_fixture
    from test_shortest import cache_sizes, clear_by_hand
    from fe_ladder.programs import narrow_deep
    records = read_fixture("earlier_problems.jsonl")[:20]
    alone = []
    for r in records:
        clear_by_hand()
        search(r, 2)
        narrow_deep.search(r, 1)
        alone.append(cache_sizes())
    clear_by_hand()
    picks(records, 2)
    narrow_deep.picks(records, 1)
    after = cache_sizes()
    assert after[0] <= max(a[0] for a in alone) and after[1] <= max(a[1] for a in alone)
