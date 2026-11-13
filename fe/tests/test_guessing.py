"""Tests of programs/guessing.py."""
from conftest import record

from fe_ladder.programs import guessing
from fe_ladder.programs.common import score


def test_guessing_scores_right_moves_divided_by_options():
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    (pick,) = guessing.picks([r])
    assert pick == [1 / 9] * 9 and score(pick, r["right_moves"]) == 2 / 9
