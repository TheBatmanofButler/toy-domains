"""Tests of programs/lookup.py on made-up training sets."""
import pytest

from cube_ladder.cube import SOLVED, TURNS
from cube_ladder.programs.common import pick_on
from cube_ladder.programs.lookup import picks, train


def made_up(right_turn_lists, distances=None):
    distances = distances or [2] * len(right_turn_lists)
    return [{"id": f"train-{d:02d}-{n:04d}", "cube": f"cube {n}", "distance": d, "right_turns": turns}
            for n, (turns, d) in enumerate(zip(right_turn_lists, distances))]


def test_counts_and_picks_the_most_frequent_turn():
    counts = train(made_up([["R"], ["R", "U"], ["U'"], ["R"], ["F2", "U'"]]), set())
    assert counts["R"] == 3 and counts["U'"] == 2 and counts["U"] == 1 and counts["F2"] == 1 and counts["B"] == 0
    assert sum(counts.values()) == 7 and set(counts) == set(TURNS)
    assert picks(["any cube", "another"], counts) == [pick_on(["R"]), pick_on(["R"])]


def test_counts_over_every_distance_together():
    # R wins at distances 2 and 3 (4 in all); F2 wins only once distances 17 and 18 are counted too
    # (5 in all). A lookup trained on only some distances would pick R.
    states = made_up([["R"], ["R"], ["F2"], ["R"], ["R"], ["F2"], ["F2"], ["F2"], ["F2"]],
                     distances=[2, 2, 2, 3, 3, 17, 17, 18, 18])
    counts = train(states, set())
    assert counts["R"] == 4 and counts["F2"] == 5
    assert picks(["any cube"], counts) == [pick_on(["F2"])]


def test_a_tie_spreads_the_weight():
    counts = train(made_up([["R"], ["U'"], ["R", "U'"]]), set())
    assert picks(["any cube"], counts) == [pick_on(["R", "U'"])]


def test_refuses_test_states_by_id_and_by_content():
    with pytest.raises(ValueError, match="only training states"):
        train([{"id": "test-01-0001", "cube": SOLVED, "right_turns": ["R"]}], set())
    with pytest.raises(ValueError, match="test cube"):
        train(made_up([["R"]]), {"cube 0"})
