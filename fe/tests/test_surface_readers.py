"""Tests of programs/surface_strict.py and programs/surface_relaxed.py: the strict reader learns a made-up rule
and not shuffled answers; the relaxed reader's inputs are the earlier run's; neither trains on a test problem."""
import random

import numpy as np
import pytest
from conftest import read_fixture

from fe_ladder.generator import generate
from fe_ladder.identities import SUBSTITUTIONS
from fe_ladder.identity_text import write_identity
from fe_ladder.programs import surface_relaxed, surface_strict
from fe_ladder.programs.common import score

EVERY_SUBSTITUTION = [{"result": "", "moves": [[1, s]]} for s in SUBSTITUTIONS]


def planted_rule_problems(set_name, how_many, seed, shuffled=False):
    """Made-up problems: real equations; the goal holds the term f(5x) when y=x is right and f(7x) when y=-x is."""
    rng = random.Random(seed)
    found, attempt = [], seed * 1000
    while len(found) < how_many:
        attempt += 1
        made = generate(seed, attempt)
        if "equation" not in made:
            continue
        planted = rng.choice(["y=x", "y=-x"])
        term = "f(5x)" if planted == "y=x" else "f(7x)"
        answer = rng.choice(["y=x", "y=-x"]) if shuffled else planted
        found.append({"id": f"{set_name}-0-{len(found):04d}", "equation": write_identity(made["equation"]),
                      "goal": f"{term} + {write_identity(made['goal']).replace(' = ', ' - (', 1)}) = 0",
                      "options": EVERY_SUBSTITUTION, "right_moves": [SUBSTITUTIONS.index(answer)]})
    return found


def mean_score(picks, problems):
    return float(np.mean([score(p, r["right_moves"]) for p, r in zip(picks, problems)]))


def test_strict_reader_learns_a_planted_term_and_not_shuffled_answers():
    train, test = planted_rule_problems("train", 200, 1), planted_rule_problems("test", 100, 2)
    trained = surface_strict.train(train, test)
    assert set(trained["cross_validation"]) == set(surface_strict.STRENGTHS)
    assert len(trained["terms"]) == 40
    assert mean_score(surface_strict.picks(test, trained), test) > 0.95
    shuffled = surface_strict.train(planted_rule_problems("train", 200, 1, shuffled=True), test)
    assert 0.3 < mean_score(surface_strict.picks(test, shuffled), test) < 0.7   # chance is one half


def test_strict_reader_shares_a_problem_among_its_right_moves():
    r = {"id": "train-0-0001", "equation": "f(x + y) = f(x) + f(y)", "goal": "f(3x) = 3f(x)",
         "options": [{"result": "", "moves": [[1, "y=0"], [1, "x=0"]]}, {"result": "", "moves": [[1, "y=x"]]}],
         "right_moves": [0, 1]}
    _, answers, weights, groups = surface_strict._training_rows([r], surface_strict.commonest_terms([r]))
    assert [SUBSTITUTIONS[a] for a in answers] == ["y=0", "x=0", "y=x"]
    assert weights.tolist() == [0.25, 0.25, 0.5] and groups.tolist() == [0, 0, 0]


def test_relaxed_reader_inputs_are_the_earlier_run_s_on_50_problems():
    earlier = read_fixture("earlier_surface_inputs.jsonl")
    assert len(earlier) == 50
    # The earlier columns that the rebuilt reader keeps, in its order (target_derived and depth_so_far, always 0
    # on the page of the equation, are left out).
    kept = [f"sigma_{s}" for s in range(1, 14)] + ["atoms_before", "atoms_after", "goal_matched_after",
                                                   "introduces_const", "new_f_atoms", "new_mono_atoms"]
    for p in earlier:
        old = np.array(p["inputs"])
        names = p["input_names"]
        assert (old[:, names.index("target_derived")] == 0).all() and (old[:, names.index("depth_so_far")] == 0).all()
        assert surface_relaxed.option_features(p).tolist() == old[:, [names.index(n) for n in kept]].tolist(), p["id"]


def test_relaxed_reader_learns_and_picks():
    earlier = read_fixture("earlier_surface_inputs.jsonl")
    train = [dict(p, id=f"train-{n}") for n, p in enumerate(earlier[:40])]
    test = [dict(p, id=f"test-{n}") for n, p in enumerate(earlier[40:])]
    model = surface_relaxed.train(train, test)
    picks = surface_relaxed.picks(test, model)
    assert len(picks) == 10 and all(sum(p) == pytest.approx(1) for p in picks)


def test_neither_reader_trains_on_a_test_problem():
    earlier = read_fixture("earlier_surface_inputs.jsonl")
    test = [dict(earlier[0], id="test-3-0001")]
    for train in (test, [dict(earlier[0], id="train-3-0001")]):
        with pytest.raises(ValueError, match="refusing"):
            surface_relaxed.train(train, test)
        with pytest.raises(ValueError, match="refusing"):
            surface_strict.train(train, test)


def test_cross_validation_keeps_the_best_strength():
    # A strength so small that the reader cannot learn the planted term scores about one half held out; 10
    # scores about 1. The best is kept, whichever order they are listed in.
    train, test = planted_rule_problems("train", 100, 3), planted_rule_problems("test", 10, 4)
    for strengths in ((1e-6, 10.0), (10.0, 1e-6)):
        trained = surface_strict.train(train, test, strengths=strengths)
        scores = trained["cross_validation"]
        assert scores[10.0] > scores[1e-6] + 0.2
        assert trained["strength"] == 10.0


def test_the_strict_reader_s_inputs_do_not_change_with_the_options():
    earlier = read_fixture("earlier_surface_inputs.jsonl")[:10]
    chosen = surface_strict.commonest_terms(earlier)
    changed = [dict(p, options=p["options"][:3], right_moves=[0]) for p in earlier]
    assert surface_strict.features(changed, chosen).tolist() == surface_strict.features(earlier, chosen).tolist()
