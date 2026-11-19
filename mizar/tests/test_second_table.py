"""Tests of second_table.py on ten made-up problems, every figure worked out by hand.

Problem n holds back option n; the key's lines come in the order p3 p9 p1 p10 p6 p2 p8 p5 p7 p4. Prover bins: p1 to p6 have right options; p7 proved without an option; p8 no
option proves it; p9 and p10 stopped for another reason. Right options under the prover's key (and the option
calls that proved the theorem without the option in the proof): p1 [1] ([7]), p2 [2, 12], p3 [13] ([8, 9]), p4
[14, 24], p5 [5], p6 [16]; p8 has one such call ([3]), not counted, being outside the table.
So the held-back option is right in p1, p2 and p5: 3 of 6 = .5; the other options right per problem: 0 1 1 2 0 1,
mean 5/6; option calls proving without the option: 3. Right by either key: p1 {1}, p2 {2, 12}, p3 {3, 13},
p4 {4, 14, 24}, p5 {5}, p6 {6, 16}.

recall picks p1 1, p2 12, p3 3, p4 14 and 4 (half each), p5 1, p6 16. Per problem:
  prover 1 1 0 .5 0 1 (mean 3.5/6); either 1 1 1 1 0 1 (5/6); author 1 0 1 .5 0 0 (2.5/6).
search is in the picks but left out. The model's five tries: p1 1 1 1 7 unreadable; p2 12 12 2 3 3; p3 13 3 3 3
3; p4 24 24 24 24 24; p5 6 6 6 6 6; p6 6 16 6 16 6. Per problem:
  prover .6 .6 .2 1 0 .4 (mean 2.8/6 = 7/15); either .6 .6 1 1 0 1 (4.2/6 = .7); author .6 .2 .8 0 0 .6 (2.2/6).
Model minus recall: prover -.4 -.4 .2 .5 0 -.6; either -.4 -.4 0 0 0 0; author -.4 .2 -.2 -.5 0 .6.
Every standard error is the sample standard deviation of those six over sqrt(6).
"""
from math import sqrt
from statistics import stdev

import pytest

from mizar_ladder import scoring
from mizar_ladder.programs.common import pick_on
from mizar_ladder.second_table import second_table

RIGHT = {1: [1], 2: [2, 12], 3: [13], 4: [14, 24], 5: [5], 6: [16], 7: [], 8: [], 9: [], 10: []}
WITHOUT_USE = {1: [7], 3: [8, 9], 8: [3]}
BIN = {7: "proved without an option", 8: "no option proves it", 9: "stopped for another reason",
       10: "stopped for another reason"}
RECALL = {1: [1], 2: [12], 3: [3], 4: [14, 4], 5: [1], 6: [16]}
TRIES = {1: [1, 1, 1, 7, None], 2: [12, 12, 2, 3, 3], 3: [13, 3, 3, 3, 3], 4: [24] * 5, 5: [6] * 5,
         6: [6, 16, 6, 16, 6]}


def made_up():
    problems = [{"id": f"p{n}", "held_back": n} for n in range(1, 11)]
    # The key's lines in another order than the problems', as the code must match them by id; the right options
    # empty outside "has right options", as prover_key.py writes them.
    key = [{"problem_id": f"p{n}", "bin": BIN.get(n, "has right options"), "right": RIGHT[n],
            "proved_without_use": WITHOUT_USE.get(n, []), "reason": None} for n in (3, 9, 1, 10, 6, 2, 8, 5, 7, 4)]
    picks = []
    for p in problems:
        for program, chosen in (("recall", RECALL.get(p["held_back"], [1])), ("search", [2])):
            weights = pick_on(chosen)
            picks.append({"problem_id": p["id"], "program": program, "weights": weights,
                          "score": scoring.score_pick(weights, [p["held_back"]])})
    answers = [{"problem_id": p["id"], "try": t, "failed": False,
                "answer_text": "no idea" if option is None else f"FACT: {option}"}
               for p in problems for t, option in enumerate(TRIES.get(p["held_back"], [1] * 5), 1)]
    return problems, picks, answers, key


def figures(values):
    return {"mean": pytest.approx(sum(values) / len(values)), "standard_error": pytest.approx(stdev(values) / sqrt(6))}


def test_every_figure_worked_by_hand():
    table = second_table(*made_up())
    assert table["bins"] == {"proved without an option": 1, "has right options": 6, "no option proves it": 1,
                             "stopped for another reason": 2}
    assert table["problems"] == 6 and list(table["programs"]) == ["recall"]          # search left out
    assert table["programs"]["recall"] == {"prover": figures([1, 1, 0, .5, 0, 1]), "either": figures([1, 1, 1, 1, 0, 1]),
                                           "author": figures([1, 0, 1, .5, 0, 0])}
    assert table["model"] == {"prover": figures([.6, .6, .2, 1, 0, .4]), "either": figures([.6, .6, 1, 1, 0, 1]),
                              "author": figures([.6, .2, .8, 0, 0, .6])}
    assert table["model"]["prover"]["mean"] == pytest.approx(7 / 15) and table["model"]["either"]["mean"] == pytest.approx(.7)
    assert table["model_minus_program"]["recall"] == {"prover": figures([-.4, -.4, .2, .5, 0, -.6]),
                                                      "either": figures([-.4, -.4, 0, 0, 0, 0]),
                                                      "author": figures([-.4, .2, -.2, -.5, 0, .6])}
    assert table["held_back_right_share"] == pytest.approx(0.5) and table["other_right_mean"] == pytest.approx(5 / 6)
    assert table["proved_without_use_calls"] == 3
    assert table["runs_disagreed_share"] is None
    assert second_table(*made_up(), runs_disagreed=0.5)["runs_disagreed_share"] == 0.5


def test_no_problem_with_right_options_and_a_key_that_does_not_fit():
    problems, picks, answers, key = made_up()
    nothing = [dict(line, bin="no option proves it") for line in key]
    table = second_table(problems, picks, answers, nothing)
    assert table["problems"] == 0 and table["held_back_right_share"] is None and table["other_right_mean"] is None
    assert table["model"]["prover"] == {"mean": None, "standard_error": None} and table["programs"] == {}
    with pytest.raises(scoring.ScoringError, match="exactly the test problems"):
        second_table(problems, picks, answers, key[1:])
    with pytest.raises(scoring.ScoringError, match="tries"):
        second_table(problems, picks, answers[1:], key)
