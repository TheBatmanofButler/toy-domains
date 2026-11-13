"""Tests of programs/surface_strict.py: it learns a planted rule, learns nothing from shuffled answers,
weights cubes with several right turns, and refuses test states."""
import random

import numpy as np
import pytest

from cube_ladder.cube import SOLVED, TURNS, random_cube
from cube_ladder.programs import surface_strict
from cube_ladder.scoring import score_pick

COLOURS = "URFDLB"


def planted_turn(cube):
    """The made-up rule: the colours of two stickers decide the right turn."""
    return TURNS[(COLOURS.index(cube[0]) * 6 + COLOURS.index(cube[20])) % 18]


def made_up_states(count, seed, shuffle=False):
    rng = random.Random(seed)
    cubes = [random_cube(rng) for _ in range(count)]
    answers = [[planted_turn(c)] for c in cubes]
    if shuffle:
        rng.shuffle(answers)
    return [{"id": f"train-00-{n:04d}", "cube": c, "right_turns": a} for n, (c, a) in enumerate(zip(cubes, answers))]


def mean_score(trained, states):
    picks = surface_strict.picks([s["cube"] for s in states], trained)
    return np.mean([score_pick(p, s["right_turns"]) for p, s in zip(picks, states)])


@pytest.fixture(scope="module")
def held_out():
    return made_up_states(400, seed=2)


def test_learns_a_planted_sticker_rule(held_out):
    trained = surface_strict.train(made_up_states(1500, seed=1), set(), strengths=(0.01, 10.0))
    assert mean_score(trained, held_out) > 0.95
    assert trained["strength"] == 10.0   # the weak setting cannot fit the rule; cross-validation sees it
    assert trained["cross_validation"][10.0] > trained["cross_validation"][0.01]


def test_scores_about_chance_on_shuffled_answers(held_out):
    trained = surface_strict.train(made_up_states(1500, seed=1, shuffle=True), set(), strengths=(0.01, 10.0))
    assert mean_score(trained, held_out) < 0.15   # chance is 1/18, about 0.056


def test_several_right_turns_count_in_proportion():
    states = [{"id": "train-01-0001", "cube": SOLVED, "right_turns": ["R", "U", "F"]},
              {"id": "train-01-0002", "cube": SOLVED, "right_turns": ["B2"]}]
    x, answers, weights, groups = surface_strict._training_rows(states)
    assert x.shape == (4, 324)
    assert [TURNS[a] for a in answers] == ["R", "U", "F", "B2"]
    assert weights.tolist() == pytest.approx([1 / 3, 1 / 3, 1 / 3, 1.0])
    assert groups.tolist() == [0, 0, 0, 1]


def test_features_are_one_fact_per_sticker_and_colour():
    x = surface_strict.features([SOLVED])
    assert x.shape == (1, 324) and x.sum() == 54
    assert x[0, 6 * 0 + 0] == 1 and x[0, 6 * 9 + 1] == 1 and x[0, 6 * 53 + 5] == 1


def test_turns_never_seen_in_training_get_no_weight():
    rng = random.Random(5)
    states = [{"id": f"train-01-{n:04d}", "cube": random_cube(rng), "right_turns": ["R", "U"]} for n in range(20)]
    trained = surface_strict.train(states, set(), strengths=(1.0,), folds=2)
    pick = surface_strict.picks([SOLVED], trained)[0]
    assert sum(w for w, t in zip(pick, TURNS) if t not in ("R", "U")) == 0


def test_refuses_test_states_by_id_and_by_content():
    with pytest.raises(ValueError, match="only training states"):
        surface_strict.train([{"id": "test-01-0001", "cube": SOLVED, "right_turns": ["R"]}], set())
    with pytest.raises(ValueError, match="test cube"):
        surface_strict.train([{"id": "train-01-0001", "cube": SOLVED, "right_turns": ["R"]}], {SOLVED})
