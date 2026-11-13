"""Tests of programs/guessing.py."""
from conftest import read_fixture

from cube_ladder.programs.guessing import picks
from cube_ladder.scoring import score_pick


def test_guessing_scores_right_turns_divided_by_18():
    states = read_fixture("pilot_path_states.jsonl")
    for state, pick in zip(states, picks([s["cube"] for s in states])):
        assert pick == [1 / 18] * 18
        assert abs(score_pick(pick, state["right_turns"]) - len(state["right_turns"]) / 18) < 1e-12
