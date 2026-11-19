"""Tests of scoring.py on ten made-up problems, every figure worked out by hand and written in below.

Problems (the held-back option), and the model's right tries out of 5:
  2 cited facts, sets, relations and functions: p1 [1] 5, p2 [2] 3, p3 [3] 2, p4 [4] 0, p5 [5] 4
  5 cited facts, topology:                      p6 [6] 1, p7 [7] 3, p8 [8] 5, p9 [9] 0, p10 [10] 2
So the rows "2 to 3 cited" and "sets, relations and functions" hold p1 to p5, and "4 to 6 cited" and "topology"
p6 to p10. Model problem scores are right/5, so the first rows = (1 + .6 + .4 + 0 + .8) / 5 = .56, the second =
(.2 + .6 + 1 + 0 + .4) / 5 = .44, and all problems .5. The model gets (3 or more right) p1 p2 p5 and p7 p8.

Program "recall" puts weight on: p1 its right option (score 1), p2 the right one and another (.5), p3 right (1),
p4 a wrong one (0), p5 right and another (.5); p6 right (1), p7 right and two others (1/3), p8 right (1), p9
right (1), p10 a wrong one (0). Means: first rows 3/5 = .6; second (1 + 1/3 + 1 + 1 + 0) / 5 = 2/3; all 19/30.
It gets (more than .5) p1 p3 and p6 p8 p9; a score of exactly .5 (p2, p5) does not count. Guessing scores 1/30
everywhere. Room = 1 - .6 = .4, 1 - 2/3 = 1/3, and 1 - 19/30 = 11/30.

Chance that a guessing model is right on 3 or more of 5 tries, with 1 right option of 30 (p = 1/30):
sum over k = 3..5 of C(5, k) p^k (1-p)^(5-k) = (10 x 29^2 + 5 x 29 + 1) / 30^5 = 8556 / 24300000.
"""
from math import sqrt

import pytest

from mizar_ladder import scoring
from mizar_ladder.programs.common import pick_on

CHANCE = 8556 / 30 ** 5
FIRST, SECOND, ALL = "2 to 3 cited", "4 to 6 cited", "all problems"
SETS, TOPOLOGY = "sets, relations and functions", "topology"

MODEL_RIGHT = {"p1": 5, "p2": 3, "p3": 2, "p4": 0, "p5": 4, "p6": 1, "p7": 3, "p8": 5, "p9": 0, "p10": 2}
RECALL = {"p1": [1], "p2": [2, 12], "p3": [3], "p4": [14], "p5": [5, 15], "p6": [6], "p7": [7, 17, 18],
          "p8": [8], "p9": [9], "p10": [20]}
# Unreadable tries: p3 try 5, p4 tries 4 and 5, all of p9. Forced: p1 tries 1 and 2, all of p6.
UNREADABLE = {("p3", 5), ("p4", 4), ("p4", 5)} | {("p9", t) for t in range(1, 6)}
FORCED = {("p1", 1), ("p1", 2)} | {("p6", t) for t in range(1, 6)}


def made_up():
    problems = [{"id": f"p{n}", "held_back": n, "cited_count": 2 if n <= 5 else 5,
                 "group": SETS if n <= 5 else TOPOLOGY} for n in range(1, 11)]
    picks = []
    for problem in problems:
        recall = pick_on(RECALL[problem["id"]])
        picks.append({"problem_id": problem["id"], "program": "recall", "weights": recall,
                      "score": scoring.score_pick(recall, [problem["held_back"]])})
        picks.append({"problem_id": problem["id"], "program": "guessing", "weights": [1 / 30] * 30,
                      "score": 1 / 30})
    answers = []
    for problem in problems:
        first_rows = problem["cited_count"] == 2
        for t in range(1, 6):
            right = t <= MODEL_RIGHT[problem["id"]]
            text = (f"FACT: {problem['held_back']}" if right
                    else "I am not sure." if (problem["id"], t) in UNREADABLE else "FACT: 30")
            forced = (problem["id"], t) in FORCED
            thinking = 8000 if forced else 1000 if first_rows else 2000
            # The stored `option` and `right` are deliberately wrong: scoring must read the answer text afresh.
            # A forced answer's thinking tokens count the server's end text (20 tokens) too; the model's own
            # thinking is the 8,000 before it.
            answers.append({"problem_id": problem["id"], "try": t, "answer_text": text, "option": 29,
                            "right": not right, "forced": forced,
                            "cut_off_but_readable": (problem["id"], t) == ("p2", 1), "failed": False,
                            "thinking_tokens": thinking + 20 * forced, "thinking_tokens_before_end_text": thinking,
                            "tokens_used": thinking + 10})
    return problems, picks, answers


def test_the_rows_of_a_problem():
    assert scoring.row_names({"cited_count": 2, "group": SETS}) == [ALL, FIRST, SETS]
    assert scoring.row_names({"cited_count": 3, "group": TOPOLOGY}) == [ALL, FIRST, TOPOLOGY]
    assert scoring.row_names({"cited_count": 6, "group": "orderings and lattices"})[1] == SECOND
    assert scoring.row_names({"cited_count": 7, "group": SETS})[1] == "7 or more cited"
    assert scoring.row_names({"cited_count": 40, "group": SETS})[1] == "7 or more cited"
    problems = made_up()[0]
    assert list(scoring.rows(problems)) == [ALL, FIRST, SECOND, SETS, TOPOLOGY]
    assert scoring.rows(problems)[TOPOLOGY] == [f"p{n}" for n in range(6, 11)]
    with pytest.raises(scoring.ScoringError, match="no row for None"):
        scoring.rows([{"id": "train-1", "cited_count": 2, "group": None}])


def test_scores_by_row():
    table = scoring.scores_by_row(*made_up())
    one, two, every = table[FIRST], table[SECOND], table[ALL]
    assert table[SETS] == one and table[TOPOLOGY] == two
    assert one["problems"] == two["problems"] == 5 and every["problems"] == 10
    assert one["model"] == pytest.approx(0.56) and two["model"] == pytest.approx(0.44)
    assert every["model"] == pytest.approx(0.5)
    assert one["programs"]["recall"] == pytest.approx(0.6) and two["programs"]["recall"] == pytest.approx(2 / 3)
    assert every["programs"]["recall"] == pytest.approx(19 / 30)
    assert all(row["programs"]["guessing"] == pytest.approx(1 / 30) for row in table.values())
    assert one["best_programs"] == two["best_programs"] == every["best_programs"] == ["recall"]
    assert one["room"] == pytest.approx(0.4) and two["room"] == pytest.approx(1 / 3)
    assert every["room"] == pytest.approx(11 / 30)
    # 3 of 25 unreadable in the first rows, 5 of 25 in the second, 8 of 50 in all; forced 2, 5 and 7.
    assert one["unreadable_share"] == pytest.approx(3 / 25) and two["unreadable_share"] == pytest.approx(5 / 25)
    assert every["unreadable_share"] == pytest.approx(8 / 50) and every["forced_share"] == pytest.approx(7 / 50)
    assert one["forced_share"] == pytest.approx(2 / 25) and two["forced_share"] == pytest.approx(5 / 25)
    assert one["failed_share"] == 0 and one["answers"] == 25 and every["answers"] == 50
    assert one["cut_off_but_readable_share"] == pytest.approx(1 / 25) and two["cut_off_but_readable_share"] == 0
    # Thinking tokens: (23 x 1000 + 2 x 8000) / 25 = 1560 and (20 x 2000 + 5 x 8000) / 25 = 3200; together 2380.
    assert one["thinking_tokens_mean"] == pytest.approx(1560) and two["thinking_tokens_mean"] == pytest.approx(3200)
    assert every["thinking_tokens_mean"] == pytest.approx(2380)
    assert one["tokens_used_mean"] == pytest.approx(1570) and two["tokens_used_mean"] == pytest.approx(3210)


def test_standard_errors_worked_by_hand():
    # Each is the sample standard deviation (divisor n - 1) over sqrt(n).
    # Model, first rows: scores 1 .6 .4 0 .8, mean .56; squared deviations .1936 .0016 .0256 .3136 .0576 sum to
    # .592; variance .148; standard error sqrt(.148 / 5) = sqrt(.0296). The second rows (.2 .6 1 0 .4) the same.
    # All ten: mean .5, squared deviations .25 .01 .01 .25 .09 .09 .01 .25 .25 .01 sum to 1.22:
    # sqrt(1.22 / 9 / 10).
    # recall, first rows: 1 .5 1 0 .5, mean .6, squares sum to .70: sqrt(.175 / 5) = sqrt(.035).
    # Second: 1 1/3 1 1 0, mean 2/3, squares sum to 8/9: sqrt((2/9) / 5) = sqrt(2/45).
    # All ten: mean 19/30, squares sum to 1.6: sqrt(1.6 / 9 / 10) = 4/30.
    # Guessing: 1/30 everywhere, so 0.
    table = scoring.scores_by_row(*made_up())
    one, two, every = table[FIRST], table[SECOND], table[ALL]
    assert one["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert two["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert every["model_standard_error"] == pytest.approx(sqrt(1.22 / 90))
    assert one["programs_standard_error"] == {"guessing": pytest.approx(0, abs=1e-15),
                                              "recall": pytest.approx(sqrt(0.035))}
    assert two["programs_standard_error"]["recall"] == pytest.approx(sqrt(2 / 45))
    assert every["programs_standard_error"]["recall"] == pytest.approx(4 / 30)
    # Room's margin is the best program's: recall in every row.
    assert one["room_standard_error_of"] == "recall" and one["room_standard_error"] == pytest.approx(sqrt(0.035))
    assert two["room_standard_error"] == pytest.approx(sqrt(2 / 45))
    # Model minus recall, first rows: differences 0 .1 -.6 0 .3, mean -.04, squares about the mean
    # .0016 .0196 .3136 .0016 .1156 sum to .452: sqrt(.113 / 5) = sqrt(.0226).
    # Second: differences -12 4 0 -15 6 fifteenths, mean -3.4/15, squares sum to 363.2 / 15^2:
    # sqrt(363.2 / 4 / 225 / 5) = sqrt(90.8 / 1125).
    # All ten, in thirtieths: 0 3 -18 0 9 -24 8 0 -30 12, mean -4/30; squares about the mean 16 49 196 16 169
    # 400 144 16 676 256 sum to 1938 / 900: sqrt(1938 / 900 / 9 / 10) = sqrt(1938 / 81000).
    assert one["model_minus_program"]["recall"] == {"mean": pytest.approx(-0.04),
                                                    "standard_error": pytest.approx(sqrt(0.0226))}
    assert two["model_minus_program"]["recall"] == {"mean": pytest.approx(-3.4 / 15),
                                                    "standard_error": pytest.approx(sqrt(90.8 / 1125))}
    assert every["model_minus_program"]["recall"] == {"mean": pytest.approx(-4 / 30),
                                                      "standard_error": pytest.approx(sqrt(1938 / 81000))}
    # Model minus guessing: guessing is the same on every problem, so the margin is the model's.
    assert one["model_minus_program"]["guessing"] == {"mean": pytest.approx(0.56 - 1 / 30),
                                                      "standard_error": pytest.approx(sqrt(0.0296))}


def test_a_row_with_one_problem_has_no_standard_error():
    problems, picks, answers = made_up()
    problems = [p if p["id"] != "p1" else {**p, "cited_count": 7} for p in problems]
    table = scoring.scores_by_row(problems, picks, answers)
    seven = table["7 or more cited"]
    assert list(table) == [ALL, FIRST, SECOND, "7 or more cited", SETS, TOPOLOGY]
    assert seven["problems"] == 1 and seven["model"] == 1 and table[FIRST]["problems"] == 4
    assert seven["model_standard_error"] is None and seven["room_standard_error"] is None
    assert set(seven["programs_standard_error"].values()) == {None}
    assert seven["model_minus_program"]["recall"] == {"mean": 0, "standard_error": None}
    four = scoring.problem_by_problem(problems, picks, answers)["recall"]["7 or more cited"]
    assert four["only_model_if_independent_standard_error"] is None
    assert scoring.standard_error([0.5]) is None and scoring.standard_error([]) is None


def test_scores_by_row_without_the_model():
    problems, picks, _ = made_up()
    table = scoring.scores_by_row(problems, picks)
    assert "model" not in table[FIRST] and table[SECOND]["room"] == pytest.approx(1 / 3)


def test_problem_by_problem():
    table = scoring.problem_by_problem(*made_up())
    # recall, first rows: model gets p1 p2 p5, program gets p1 p3: both p1; only model p2 p5; only program p3;
    # neither p4. Chance counts over p2 p4 p5 (program misses), each with 1 right option.
    # If independent: problems the program misses (3) x share of problems the model gets (3 of 5) = 1.8.
    assert table["recall"][FIRST] == {"both": 1, "only_model": 2, "only_program": 1, "neither": 1,
                                      "only_model_expected_by_chance": pytest.approx(3 * CHANCE),
                                      "only_model_expected_if_independent": pytest.approx(3 * 3 / 5),
                                      "only_model_if_independent_standard_error": pytest.approx(sqrt(3 * 0.6 * 0.4))}
    # Second rows: model gets p7 p8, program gets p6 p8 p9: both p8; only model p7; only program p6 p9;
    # neither p10. Chance over p7 and p10. If independent: 2 misses x 2 of 5 = 0.8.
    assert table["recall"][SECOND] == {"both": 1, "only_model": 1, "only_program": 2, "neither": 1,
                                       "only_model_expected_by_chance": pytest.approx(2 * CHANCE),
                                       "only_model_expected_if_independent": pytest.approx(2 * 2 / 5),
                                       "only_model_if_independent_standard_error": pytest.approx(sqrt(2 * 0.4 * 0.6))}
    # All ten: the two rows added; 5 misses x 5 of 10 = 2.5.
    assert table["recall"][ALL] == {"both": 2, "only_model": 3, "only_program": 3, "neither": 2,
                                    "only_model_expected_by_chance": pytest.approx(5 * CHANCE),
                                    "only_model_expected_if_independent": pytest.approx(2.5),
                                    "only_model_if_independent_standard_error": pytest.approx(sqrt(5 * 0.5 * 0.5))}
    assert table["recall"][SETS] == table["recall"][FIRST] and table["recall"][TOPOLOGY] == table["recall"][SECOND]
    # Guessing gets nothing. First rows: chance over all five problems; 5 x 3/5 = 3 if independent.
    assert table["guessing"][FIRST] == {"both": 0, "only_model": 3, "only_program": 0, "neither": 2,
                                        "only_model_expected_by_chance": pytest.approx(5 * CHANCE),
                                        "only_model_expected_if_independent": pytest.approx(3),
                                        "only_model_if_independent_standard_error": pytest.approx(sqrt(5 * 0.6 * 0.4))}
    assert table["guessing"][SECOND] == {"both": 0, "only_model": 2, "only_program": 0, "neither": 3,
                                         "only_model_expected_by_chance": pytest.approx(5 * CHANCE),
                                         "only_model_expected_if_independent": pytest.approx(2),
                                         "only_model_if_independent_standard_error": pytest.approx(sqrt(5 * 0.4 * 0.6))}


def test_chance_formula():
    assert scoring.chance_model_gets(1, 5) == pytest.approx(CHANCE)
    # Three right of 30, p = .1: 10 x .001 x .81 + 5 x .0001 x .9 + .00001 = .00856.
    assert scoring.chance_model_gets(3, 5) == pytest.approx(0.00856)
    assert scoring.chance_model_gets(30, 5) == pytest.approx(1)
    assert scoring.chance_model_gets(15, 1) == pytest.approx(0.5)


def test_score_pick_and_bad_picks():
    assert scoring.score_pick(pick_on([1, 2, 3]), [2, 30]) == pytest.approx(1 / 3)
    assert scoring.right_options({"held_back": 17}) == [17]
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([0.5] * 30, [1])
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([1 / 29] * 29, [1])


def test_best_programs_name_every_tie():
    problems = [{"id": "a", "held_back": 1, "cited_count": 2, "group": SETS},
                {"id": "b", "held_back": 2, "cited_count": 2, "group": SETS}]
    picks = []
    for name, options in (("zeta", [1, 2]), ("alpha", [1, 2]), ("beta", [1])):
        for problem, chosen in zip(problems, (options[:1], options[-1:])):
            pick = pick_on(chosen)
            picks.append({"problem_id": problem["id"], "program": name, "weights": pick,
                          "score": scoring.score_pick(pick, [problem["held_back"]])})
    row = scoring.scores_by_row(problems, picks)[ALL]
    assert row["programs"] == {"alpha": 1.0, "beta": 0.5, "zeta": 1.0}
    assert row["best_programs"] == ["alpha", "zeta"] and row["room"] == 0


@pytest.mark.parametrize("break_it, message", [
    (lambda p, k, a: a.pop(), "tries"),
    (lambda p, k, a: a[0].update(failed=True), "failed"),
    (lambda p, k, a: k.pop(), "0 picks"),
    (lambda p, k, a: k.append(dict(k[0])), "2 picks"),
    (lambda p, k, a: k[0].update(score=0.25), "does not match"),
    (lambda p, k, a: a.append({**a[0], "problem_id": "p99"}), "not a test problem"),
])
def test_missing_or_broken_records_stop_the_scoring(break_it, message):
    problems, picks, answers = made_up()
    break_it(problems, picks, answers)
    with pytest.raises(scoring.ScoringError, match=message):
        scoring.scores_by_row(problems, picks, answers)
