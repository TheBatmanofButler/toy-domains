"""Tests of programs/lookup.py and programs/recall.py on made-up sets."""
import pytest

from fe_ladder.identities import SUBSTITUTIONS
from fe_ladder.programs import lookup, recall


def made_up(problem_id, moves_per_option, right):
    """A record with made-up options: each a list of substitutions on the equation."""
    return {"id": problem_id, "equation": "f(x + y) = f(x) + f(y)", "goal": f"f({len(problem_id)}x) = 0",
            "options": [{"result": "", "moves": [[1, s] for s in subs]} for subs in moves_per_option],
            "right_moves": right}


def test_lookup_counts_right_substitutions_and_picks_the_commonest_available():
    train = [made_up("train-2-0001", [["y=0"], ["y=x", "y=-x"], ["y=1"]], [1]),
             made_up("train-2-0002", [["y=x"], ["y=1"]], [0, 1]),
             made_up("train-2-0003", [["y=-x"], ["y=1"]], [0])]
    counts = lookup.train(train, [])
    assert counts["y=x"] == 2 and counts["y=-x"] == 2 and counts["y=1"] == 1 and counts["y=0"] == 0
    assert sum(counts.values()) == 5 and list(counts) == list(SUBSTITUTIONS)
    problems = [made_up("test-2-0001", [["y=0"], ["y=1"], ["y=x"]], []),          # y=x wins
                made_up("test-2-0002", [["y=x"], ["y=0"], ["y=-x"]], []),         # y=x and y=-x tie
                made_up("test-2-0003", [["y=0"], ["y=x", "y=-x"]], []),           # one option holds both
                made_up("test-2-0004", [["y=0"], ["swap x,y"]], [])]              # all counts 0: a tie
    assert lookup.picks(problems, counts) == [[0, 0, 1.0], [0.5, 0, 0.5], [0, 1.0], [0.5, 0.5]]


def test_lookup_refuses_a_test_problem():
    with pytest.raises(ValueError):
        lookup.train([made_up("test-2-0001", [["y=0"]], [0])], [])


def test_recall_takes_the_first_substitution_in_the_list_that_is_available():
    problems = [made_up("test-2-0001", [["y=0", "x=0"], ["y=x"]], []),
                made_up("test-2-0002", [["y=x"], ["swap x,y"], ["x=1"]], [])]
    # Options are listed by the earliest substitution among their moves, so this is the first option, but a
    # made-up order checks the rule itself: here the first option holds only a later substitution.
    out_of_order = made_up("test-2-0003", [["x=1"], ["y=1"], ["x=0"]], [])
    assert recall.picks(problems + [out_of_order]) == [[1.0, 0], [1.0, 0, 0], [0, 0, 1.0]]
    with pytest.raises(ValueError):
        recall.first_available(made_up("test-2-0004", [], []))
