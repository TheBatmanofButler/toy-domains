"""Tests of surface_trained.py: trained on a made-up rule that needs the theorem it learns it, it scores about
chance when the answers are shuffled, it chooses its strength by cross-validation across articles, and it refuses
test theorems in training."""
import numpy as np
import pytest
from made_up_programs import OPTIONS, hand_library, problem, rule_problems
from test_options_only import mean_score

from mizar_ladder.programs import surface_trained


def trained(rule, seed=1):
    train, counts = rule_problems(rule, 300, seed)
    return surface_trained.train(train, counts)


def scored(model, rule, seed=101):
    test, counts = rule_problems(rule, 200, seed, prefix="test")
    return mean_score(surface_trained.picks(test, model, counts), test)


def test_it_learns_a_rule_that_needs_the_theorem():
    model = trained("shares")
    assert scored(model, "shares") > 0.9
    assert set(model["cross_validation"]) == set(surface_trained.STRENGTHS)
    assert model["strength"] == max(surface_trained.STRENGTHS, key=lambda s: model["cross_validation"][s])


def test_it_scores_about_chance_on_shuffled_answers():
    assert abs(scored(trained("shuffled"), "shuffled") - 1 / 30) < 0.05


def test_the_features_worked_by_hand():
    counts = hand_library()
    rows = surface_trained.features(problem("train-1", "t3_bb", OPTIONS, 5, given=["t3_aa"]), counts)
    assert rows.shape == (30, 18)
    # t7_aa: cited with t3_aa by t2_bb (1); t3_aa itself is cited with itself by t1_bb and t2_bb (2); t5_aa by
    # t1_bb (1); the problem's own theorem t3_bb cites neither.
    assert rows[6, 11] == 1 and rows[2, 11] == 2 and rows[4, 11] == 1 and rows[0, 11] == 0
    # Facts between t1_aa and t3_bb: t2_aa .. t30_aa, t1_bb, t2_bb: 31.
    assert rows[0, 12] == 31
    # Share of the option's symbols in the theorem (k9_z): 1 for t1_aa, 0 for t2_aa (r1_x).
    assert rows[0, 10] == 1 and rows[1, 10] == 0


def test_cross_validation_splits_by_article():
    train, counts = rule_problems("shares", 40, 3)
    rows = [surface_trained.features(p, counts) for p in train]
    found = surface_trained.cross_validation(rows, train, strengths=(1.0,), folds=5)
    assert list(found) == [1.0] and 0 <= found[1.0] <= 1


def test_the_folds_never_split_an_article(monkeypatch):
    # 40 problems over 8 articles (prob0 .. prob7, five problems each). Every fold's held-out problems are whole
    # articles, none of them among the articles it was trained on, and each problem is held out exactly once.
    train, counts = rule_problems("shares", 40, 3)
    rows = [surface_trained.features(p, counts) for p in train]
    problem_of = {id(r): p for r, p in zip(rows, train)}
    folds, real_fit, real_score = [], surface_trained.options_only.fit, surface_trained.mean_score

    def fit(inside_rows, targets, strength):
        folds.append({"inside": [problem_of[id(r)] for r in inside_rows]})
        return real_fit(inside_rows, targets, strength)

    def score(model, outside_rows, outside):
        folds[-1]["outside"] = outside
        return real_score(model, outside_rows, outside)
    monkeypatch.setattr(surface_trained.options_only, "fit", fit)
    monkeypatch.setattr(surface_trained, "mean_score", score)
    surface_trained.cross_validation(rows, train, strengths=(1.0,), folds=5)
    assert len(folds) == 5
    for fold in folds:
        inside, outside = {p["article"] for p in fold["inside"]}, {p["article"] for p in fold["outside"]}
        assert not inside & outside
        assert len(fold["outside"]) == 5 * len(outside)                    # every problem of those articles
    assert sorted(p["id"] for fold in folds for p in fold["outside"]) == sorted(p["id"] for p in train)
    # Two articles: only two folds can be made.
    two = [dict(p, article=f"prob{n % 2}") for n, p in enumerate(train)]
    assert list(surface_trained.cross_validation(rows, two, strengths=(1.0,), folds=5)) == [1.0]


def test_it_refuses_a_test_theorem_in_training():
    train, counts = rule_problems("shares", 3, 1)
    counts.left_out = {"t5_tops_1"}
    with pytest.raises(ValueError, match="t5_tops_1 is a test problem's theorem"):
        surface_trained.train(train + [dict(train[0], id="train-9999", theorem="t5_tops_1")], counts)
    assert np.isfinite(rule_problems("shares", 1, 1)[1].symbol_weight("k1_sym"))


def test_one_pick_worked_by_hand_with_fixed_weights():
    # Weights: 1 on the theorems citing the option with a given fact, .001 on the facts between the option and the
    # theorem. Given t3_aa, for the theorem t3_bb: t3_aa 2 (t1_bb, t2_bb) + .001 x 29 = 2.029; t5_aa and t7_aa
    # 1 (t1_bb; t2_bb) + .027 and + .025; t1_aa 0 + .031. So the pick is option 3.
    from test_options_only import FixedModel
    weights = [0] * 18
    weights[11], weights[12] = 1, 0.001
    picks = surface_trained.picks([problem("train-1", "t3_bb", OPTIONS, 5, given=["t3_aa"])],
                                  {"model": FixedModel(weights)}, hand_library())
    assert picks == [[0.0] * 2 + [1.0] + [0.0] * 27]


def test_the_share_of_an_options_symbols_in_the_theorem():
    # The first option has three symbols, one of them (r1_x) the theorem's: a share of 1/3. The second has two,
    # both the theorem's: 1. The others have one, not the theorem's: 0.
    from mizar_ladder.programs.common import Counts
    facts = [("t1_aa", "r1_x(A) & k5_q(A) & k6_q(A)"), ("t2_aa", "r1_x(A) & k1_y(A)")]
    facts += [(f"t{n}_aa", "k9_z(A)=A") for n in range(3, 31)] + [("t1_bb", "r1_x(A, k1_y(A)) & k2_w(A)")]
    rows = surface_trained.features(problem("train-1", "t1_bb", OPTIONS, 1), Counts(facts, {}, left_out=set()))
    assert rows[0, 10] == pytest.approx(1 / 3) and rows[1, 10] == 1 and rows[2, 10] == 0
