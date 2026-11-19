"""Tests of options_only.py: trained on a made-up rule it learns it, it scores about chance when the answers are
shuffled, it cannot learn a rule that needs the theorem, it is never handed the theorem, and it refuses test
theorems in training."""
import numpy as np
import pytest
from made_up_programs import OPTIONS, hand_library, problem, rule_problems

from mizar_ladder.programs import options_only


def mean_score(picks, problems):
    return float(np.mean([pick[p["held_back"] - 1] for pick, p in zip(picks, problems)]))


def trained_and_scored(rule, seed=1):
    train, counts = rule_problems(rule, 300, seed)
    test, test_counts = rule_problems(rule, 200, seed + 100, prefix="test")
    return mean_score(options_only.picks(test, options_only.train(train, counts), test_counts), test)


def test_it_learns_a_rule_about_the_options_alone():
    assert trained_and_scored("longest") > 0.95


def test_it_scores_about_chance_on_shuffled_answers():
    # 200 problems at 1/30: a standard error of about 0.013.
    assert abs(trained_and_scored("shuffled") - 1 / 30) < 0.05


def test_it_cannot_learn_a_rule_that_needs_the_theorem():
    assert abs(trained_and_scored("shares") - 1 / 30) < 0.05


def test_the_view_holds_the_options_alone():
    counts = hand_library()
    view = options_only.option_view(problem("test-1", "t1_bb", OPTIONS, 3), counts)
    assert set(view) == {"options", "held_back"} and len(view["options"]) == 30
    # t3_aa: "k9_z(A)=A" is 1 symbol and 2 variables; cited by t2_bb (t1_bb, the problem's own theorem, is left
    # out); 2 facts after the start of article aa.
    assert view["options"][2] == {"length": 3, "different_symbols": 1, "citations": 1, "from_article_start": 2}
    rows = options_only.features(view)
    assert rows.shape == (30, 8)
    # Ranks: t3_aa, t5_aa and t7_aa share the highest citation count (1), so all rank 1; the rest rank 4.
    assert rows[2, 6] == rows[4, 6] == rows[6, 6] == 1 and rows[0, 6] == 4


def test_it_raises_an_error_if_handed_the_theorem():
    counts = hand_library()
    full = problem("test-1", "t1_bb", OPTIONS, 3)
    with pytest.raises(ValueError, match="never given the theorem"):
        options_only.features(dict(full, statement="r1_x(A, k1_y(A))"))
    with pytest.raises(ValueError, match="never given the theorem"):
        options_only.features(dict(options_only.option_view(full, counts), statement="r1_x(A, k1_y(A))"))


def test_it_refuses_a_test_theorem_in_training():
    train, counts = rule_problems("longest", 3, 1)
    counts.left_out = {"t0_prob0"}               # the first problem's theorem stands for a test theorem
    with pytest.raises(ValueError, match="t0_prob0 is a test problem's theorem"):
        options_only.train(train, counts)
    counts.left_out = {"t1_xboole_1"}            # a theorem of the problems' own articles that is not a test one
    options_only.train(train, counts)
    with pytest.raises(ValueError, match="only training problems"):
        options_only.train([dict(train[0], id="test-0001")], counts)


class FixedModel:
    """A model with weights set by hand, so that a pick can be worked out from the features alone."""

    def __init__(self, weights):
        self.weights = np.array(weights, dtype=float)

    def decision_function(self, rows):
        return rows @ self.weights


def test_one_pick_worked_by_hand_with_fixed_weights():
    # Weights: 1 on length, -0.01 on the facts between the option and its article's start. Lengths are 3, but 4
    # for t6_aa and t8_aa ("r1_x(A, k1_y(A))" and "r1_x(k1_y(B), B)"); t6_aa is nearer the start (5 against 7):
    # 4 - .05 against 4 - .07. So the pick is option 6 alone.
    weights = [1, 0, 0, -0.01, 0, 0, 0, 0]
    picks = options_only.picks([problem("test-1", "t1_bb", OPTIONS, 6)], {"model": FixedModel(weights)}, hand_library())
    assert picks == [[0.0] * 5 + [1.0] + [0.0] * 24]
