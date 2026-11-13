"""Tests of programs/surface_relaxed.py: the old run's feature values, and a sanity check of the reader."""
import sys
from pathlib import Path

import numpy as np
import pytest
from conftest import read_fixture

from cube_ladder.cube import SOLVED, TURNS, apply_turn
from cube_ladder.programs import surface_relaxed
from cube_ladder.scoring import score_pick

sys.path.insert(0, str(Path(__file__).resolve().parent / "reference"))
from old_features import FeatureExtractor  # noqa: E402
from old_puzzle import CUBE3, str_to_state  # noqa: E402


def test_reproduces_the_old_run_s_feature_values_on_50_old_states():
    states = read_fixture("old_run_states.jsonl")[:50]
    old, old_names = FeatureExtractor(CUBE3).pair_features(np.array([str_to_state(CUBE3, s["cube"]) for s in states]))
    new = surface_relaxed.features([s["cube"] for s in states])
    assert new.shape == old.shape == (50, 18, 63)
    assert np.array_equal(new, old)
    assert len(surface_relaxed.FEATURE_NAMES) == len(old_names) == 63


def test_counts_of_the_solved_cube():
    counts = dict(zip(surface_relaxed.COUNT_NAMES, surface_relaxed.counts(np.array([[0] * 9 + [1] * 9 + [2] * 9
                                                                                     + [3] * 9 + [4] * 9 + [5] * 9]))[0]))
    assert counts["pieces"] == 20 and counts["stickers"] == 48 and counts["corners"] == 8 and counts["edges"] == 12
    assert counts["twist"] == 0 and counts["flip"] == 0 and counts["face_U"] == 8 and counts["cross_D"] == 1


def test_learns_to_finish_a_cube_one_turn_from_solved(distance_table):
    # Trained on states at every distance, the reader should at least see that a turn which solves the
    # cube is right: after it, every count is at its best.
    training = [{**s, "id": f"train-{n:04d}"} for n, s in enumerate(read_fixture("pilot_path_states.jsonl"))]
    model = surface_relaxed.train(training, test_cubes=set())
    one_away = [cube for cube, d in distance_table.items() if d == 1]
    for cube, pick in zip(one_away, surface_relaxed.picks(one_away, model)):
        right = [t for t in TURNS if apply_turn(cube, t) == SOLVED]
        assert score_pick(pick, right) == 1


def test_refuses_test_states_by_id_and_by_content():
    with pytest.raises(ValueError, match="only training states"):
        surface_relaxed.train([{"id": "test-01-0001", "cube": SOLVED, "right_turns": ["R"]}], set())
    with pytest.raises(ValueError, match="test cube"):
        surface_relaxed.train([{"id": "train-01-0001", "cube": SOLVED, "right_turns": ["R"]}], {SOLVED})
