"""Tests of guessing.py: equal weight on all 30 options scores 1/30 on every problem."""
import pytest
from made_up_programs import OPTIONS, problem

from mizar_ladder.programs import guessing


def test_guessing_scores_one_in_thirty():
    problems = [problem(f"test-{n}", "t1_bb", OPTIONS, n) for n in (1, 17, 30)]
    for pick, p in zip(guessing.picks(problems), problems):
        assert len(pick) == 30 and sum(pick) == pytest.approx(1)
        assert pick[p["held_back"] - 1] == pytest.approx(1 / 30)
