"""Tests of shortest.py: agreement with the plain search, a problem worked by hand, the outcomes other than a
depth, and (slow) the earlier run's 60 problems."""
import pytest
from conftest import read_fixture
from small_problems import small_problems

from fe_ladder.identity_text import read_identity, write_identity
from fe_ladder.moves import options
from fe_ladder.shortest import ALREADY_PROVED, DEEPER, DEPTH, OUT_OF_TIME, PlainSearch, solve

CAUCHY = read_identity("f(x + y) = f(x) + f(y)")


def answers(solution):
    return solution.outcome, solution.depth, solution.right, solution.proofs, solution.sequences


def test_agrees_with_the_plain_search_on_300_small_problems():
    outcomes = {}
    for equation, goal in small_problems(300):
        found = solve(equation, goal, most_moves=3)
        assert answers(found) == answers(PlainSearch().solve(equation, goal, 3))
        outcomes[found.depth] = outcomes.get(found.depth, 0) + 1
    assert all(outcomes.get(depth, 0) >= 10 for depth in (1, 2, 3))


def test_a_depth_3_problem_worked_by_hand():
    # Goal f(3x) = 3f(x) from Cauchy. The proof: y=x on (1) gives f(2x) = 2f(x); y=x+y on (1) gives
    # f(2x + y) = f(x) + f(x + y); y=x on that gives f(3x) = f(x) + f(2x); then f(3x) = 3f(x). No two moves reach
    # an identity with f(3x) and f(2x) = 2f(x) together. The three moves can be made in 3 orders (y=x first,
    # second or third), so there are 3 proofs, and the right first moves are y=x and y=x+y.
    found = solve(CAUCHY, read_identity("f(3x) = 3f(x)"))
    assert answers(found) == (DEPTH, 3, [1, 5], 3, 2117)
    root = options([CAUCHY])
    assert [root[n].moves for n in found.right] == [[(1, "y=x")], [(1, "y=x+y")]]
    assert found.pages == [1, 9, 83]


def test_a_problem_already_proved():
    found = solve(CAUCHY, read_identity("2f(x + y) - 2f(x) = 2f(y)"))
    assert found.outcome == ALREADY_PROVED and found.depth is None


def test_a_problem_deeper_than_allowed_is_named():
    found = solve(CAUCHY, read_identity("f(3x) = 3f(x)"), most_moves=2)
    assert found.outcome == DEEPER and found.depth is None and found.right == []


def test_a_time_limit_that_is_reached_is_reported():
    earlier = read_fixture("earlier_problems.jsonl")[-1]
    found = solve(read_identity(earlier["equation"]), read_identity(earlier["goal"]), time_limit=0.0)
    assert found.outcome == OUT_OF_TIME and found.depth is None


def test_the_plain_search_refuses_more_than_3_moves():
    with pytest.raises(ValueError):
        PlainSearch().solve(CAUCHY, CAUCHY, 4)


@pytest.mark.slow
def test_the_earlier_run_s_60_problems():
    for p in read_fixture("earlier_problems.jsonl"):
        equation = read_identity(p["equation"])
        found = solve(equation, read_identity(p["goal"]))
        assert answers(found) == (DEPTH, p["depth"], p["right_moves"], p["proofs"], p["sequences"]), p["id"]
        assert [[write_identity(o.result), [list(m) for m in o.moves]] for o in options([equation])] == \
            [[o["result"], o["moves"]] for o in p["options"]], p["id"]


def cache_sizes():
    from fe_ladder import proof
    from fe_ladder.identities import apply
    return apply.cache_info().currsize, len(proof._TERM_NUMBER)


def clear_by_hand():
    from fe_ladder import proof
    from fe_ladder.identities import apply
    apply.cache_clear()
    proof._TERM_NUMBER.clear()


def test_caches_hold_no_more_after_20_problems_than_after_the_largest_alone():
    # The table of substitution results and the numbering of terms are kept for one problem only.
    problems = [(read_identity(p["equation"]), read_identity(p["goal"]))
                for p in read_fixture("earlier_problems.jsonl") if p["depth"] == 3][:20]
    alone = []
    for equation, goal in problems:
        clear_by_hand()
        solve(equation, goal)
        alone.append(cache_sizes())
    clear_by_hand()
    for equation, goal in problems:
        solve(equation, goal)
    after = cache_sizes()
    assert after[0] <= max(a[0] for a in alone) and after[1] <= max(a[1] for a in alone)
