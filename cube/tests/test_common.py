"""Tests of programs/common.py: making picks, and refusing test states in training."""
import pytest

from cube_ladder.cube import TURNS
from cube_ladder.programs.common import check_training_states, pick_best, pick_on


def test_pick_on_spreads_weight_evenly():
    pick = pick_on(["R", "U'", "R"])
    assert pick[TURNS.index("R")] == 0.5 and pick[TURNS.index("U'")] == 0.5 and sum(pick) == 1
    with pytest.raises(ValueError):
        pick_on([])


def test_pick_best_ties_values_closer_than_the_tolerance():
    values = [0.0] * 18
    values[3], values[7] = 0.9, 0.9 - 1e-12
    assert pick_best(values) == pick_on([TURNS[3], TURNS[7]])
    values[7] = 0.8
    assert pick_best(values) == pick_on([TURNS[3]])


def test_test_states_are_refused():
    check_training_states([{"id": "train-01-0001", "cube": "A"}], {"B"})
    with pytest.raises(ValueError, match="test-03-0002"):
        check_training_states([{"id": "train-01-0001", "cube": "A"}, {"id": "test-03-0002", "cube": "C"}], set())
    with pytest.raises(ValueError, match="train-01-0002: its cube is a test cube"):
        check_training_states([{"id": "train-01-0001", "cube": "A"}, {"id": "train-01-0002", "cube": "B"}], {"B"})
