"""Tests of scoring.py on ten made-up problems, every figure worked out by hand and written in below.

Each problem has 18 options (made_up.py), numbered 0 to 17. Problems (right moves), and the model's right tries
out of 5:
  depth 1: s1 [6] 5, s2 [0] 3, s3 [13] 2, s4 [11] 0, s5 [3] 4
  depth 2: s6 [6 0] 1, s7 [15] 3, s8 [7 9 14] 5, s9 [2] 0, s10 [4 17] 2
Model problem scores are right/5, so depth 1 = (1 + .6 + .4 + 0 + .8) / 5 = .56 and depth 2 =
(.2 + .6 + 1 + 0 + .4) / 5 = .44. The model gets (3 or more right) s1 s2 s5 and s7 s8.

Program "lookahead_1" puts weight on: s1 6 (score 1), s2 0 and 1 (.5), s3 13 (1), s4 6 (0), s5 3 and 0 (.5);
s6 6 (1), s7 15 12 0 (1/3), s8 7 9 (1), s9 2 (1), s10 6 (0). Means: depth 1 = 3/5 = .6;
depth 2 = (1 + 1/3 + 1 + 1 + 0) / 5 = 2/3. It gets (more than .5) s1 s3 and s6 s8 s9; a score of
exactly .5 (s2, s5) does not count. Guessing scores right moves / 18: depth 1 = 1/18, depth 2 =
(2 + 1 + 3 + 1 + 2) / 18 / 5 = .1. Room = 1 - .6 = .4 at depth 1 and 1 - 2/3 = 1/3 at depth 2.

Chance that a guessing model is right on 3 or more of 5 tries, with r right moves of 18 options (p = r/18):
sum over k = 3..5 of C(5, k) p^k (1-p)^(5-k) = (10 r^3 (18-r)^2 + 5 r^4 (18-r) + r^5) / 18^5, so
r=1: 2976 / 1889568, r=2: 21792 / 1889568, r=3: 67068 / 1889568.
"""
from math import sqrt

import pytest

from made_up import NOT_AVAILABLE, OPTIONS, move_text, pick

from fe_ladder import scoring

FIFTH_POWER = 18 ** 5
CHANCE = {1: 2976 / FIFTH_POWER, 2: 21792 / FIFTH_POWER, 3: 67068 / FIFTH_POWER}

RIGHT_MOVES = {"s1": [6], "s2": [0], "s3": [13], "s4": [11], "s5": [3],
               "s6": [6, 0], "s7": [15], "s8": [7, 9, 14], "s9": [2], "s10": [4, 17]}
MODEL_RIGHT = {"s1": 5, "s2": 3, "s3": 2, "s4": 0, "s5": 4, "s6": 1, "s7": 3, "s8": 5, "s9": 0, "s10": 2}
LOOKAHEAD_MOVES = {"s1": [6], "s2": [0, 1], "s3": [13], "s4": [6], "s5": [3, 0],
                   "s6": [6], "s7": [15, 12, 0], "s8": [7, 9], "s9": [2], "s10": [6]}
SEQUENCES = {"s1": 18, "s2": 18, "s3": 18, "s4": 18, "s5": 18, "s6": 18, "s7": 288, "s8": 288, "s9": 18, "s10": 288}
# Unreadable tries: s3 try 5, s4 tries 4 and 5, all of s9. Not available: s4 try 1 (a wrong move either way).
# Forced: s1 tries 1 and 2, all of s6.
UNREADABLE = {("s3", 5), ("s4", 4), ("s4", 5)} | {("s9", t) for t in range(1, 6)}
FORCED = {("s1", 1), ("s1", 2)} | {("s6", t) for t in range(1, 6)}


def made_up():
    problems = [{"id": s, "depth": 1 if n < 5 else 2, "options": OPTIONS, "right_moves": r}
                for n, (s, r) in enumerate(RIGHT_MOVES.items())]
    picks = []
    for problem in problems:
        lookahead = pick(LOOKAHEAD_MOVES[problem["id"]])
        picks.append({"problem_id": problem["id"], "program": "lookahead_1", "weights": lookahead,
                      "score": scoring.score_pick(lookahead, problem["right_moves"], 18),
                      "sequences_examined": SEQUENCES[problem["id"]]})
        picks.append({"problem_id": problem["id"], "program": "guessing", "weights": pick(range(18)),
                      "score": len(problem["right_moves"]) / 18})
    answers = []
    for problem in problems:
        for t in range(1, 6):
            right = t <= MODEL_RIGHT[problem["id"]]
            text = (move_text(problem["right_moves"][0]) if right
                    else "I am not sure." if (problem["id"], t) in UNREADABLE
                    else NOT_AVAILABLE if (problem["id"], t) == ("s4", 1) else move_text(12))
            forced = (problem["id"], t) in FORCED
            thinking = 8000 if forced else 1000 * problem["depth"]
            # The stored `move`, `option` and `right` are deliberately wrong: scoring must read the answer text
            # afresh. A forced answer's thinking tokens count the server's end text (20 tokens) too; the model's
            # own thinking is the 8,000 before it.
            answers.append({"problem_id": problem["id"], "try": t, "answer_text": text, "move": [1, "y=0"],
                            "option": 0, "right": not right,
                            "forced": forced, "cut_off_but_readable": (problem["id"], t) == ("s2", 1), "failed": False,
                            "thinking_tokens": thinking + 20 * forced, "thinking_tokens_before_end_text": thinking,
                            "tokens_used": thinking + 10})
    return problems, picks, answers


def test_scores_by_depth():
    table = scoring.scores_by_depth(*made_up())
    one, two = table[1], table[2]
    assert one["problems"] == two["problems"] == 5
    assert one["model"] == pytest.approx(0.56) and two["model"] == pytest.approx(0.44)
    assert one["programs"]["lookahead_1"] == pytest.approx(0.6) and two["programs"]["lookahead_1"] == pytest.approx(2 / 3)
    assert one["programs"]["guessing"] == pytest.approx(1 / 18) and two["programs"]["guessing"] == pytest.approx(0.1)
    assert one["best_programs"] == two["best_programs"] == ["lookahead_1"]
    assert one["room"] == pytest.approx(0.4) and two["room"] == pytest.approx(1 / 3)
    # 3 of 25 unreadable at depth 1, 5 of 25 at 2; 1 of 25 not available at 1; 2 of 25 forced at 1, 5 of 25 at 2.
    assert one["unreadable_share"] == pytest.approx(3 / 25) and two["unreadable_share"] == pytest.approx(5 / 25)
    assert one["forced_share"] == pytest.approx(2 / 25) and two["forced_share"] == pytest.approx(5 / 25)
    assert one["not_available_share"] == pytest.approx(1 / 25) and two["not_available_share"] == 0
    assert one["failed_share"] == 0 and one["answers"] == 25
    assert one["cut_off_but_readable_share"] == pytest.approx(1 / 25) and two["cut_off_but_readable_share"] == 0
    # Thinking tokens: (23 x 1000 + 2 x 8000) / 25 = 1560 and (20 x 2000 + 5 x 8000) / 25 = 3200.
    assert one["thinking_tokens_mean"] == pytest.approx(1560) and two["thinking_tokens_mean"] == pytest.approx(3200)
    assert one["tokens_used_mean"] == pytest.approx(1570) and two["tokens_used_mean"] == pytest.approx(3210)
    assert one["sequences_examined_mean"] == {"lookahead_1": 18}
    assert two["sequences_examined_mean"] == {"lookahead_1": (18 + 288 + 288 + 18 + 288) / 5}


def test_forced_and_unforced_answers_apart():
    # Depth 1: forced are s1 tries 1 and 2, both right; the other 23 hold 14 - 2 = 12 right tries.
    # Depth 2: forced are the five tries of s6, one right; the other 20 hold 11 - 1 = 10 right tries.
    one, two = scoring.scores_by_depth(*made_up()).values()
    assert (one["forced_answers"], one["forced_share_right"]) == (2, 1.0)
    assert one["unforced_answers"] == 23 and one["unforced_share_right"] == pytest.approx(12 / 23)
    assert (two["forced_answers"], two["forced_share_right"]) == (5, pytest.approx(0.2))
    assert two["unforced_answers"] == 20 and two["unforced_share_right"] == pytest.approx(0.5)
    problems, _, answers = made_up()
    by_id = {p["id"]: p for p in problems}
    assert scoring.forced_and_unforced([a for a in answers if not a["forced"]][:3], by_id)["forced_share_right"] is None


def test_standard_errors_worked_by_hand():
    # Each is the sample standard deviation (divisor n - 1 = 4) over sqrt(5).
    # Model, depth 1: scores 1 .6 .4 0 .8, mean .56; squared deviations .1936 .0016 .0256 .3136 .0576 sum to
    # .592; variance .148; standard error sqrt(.148 / 5) = sqrt(.0296). Depth 2 (.2 .6 1 0 .4) is the same.
    # lookahead_1, depth 1: 1 .5 1 0 .5, mean .6, squares sum to .70: sqrt(.175 / 5) = sqrt(.035).
    # Depth 2: 1 1/3 1 1 0, mean 2/3, squares sum to 8/9: sqrt((2/9) / 5) = sqrt(2/45).
    # Guessing, depth 1: all 1/18, so 0. Depth 2: 2 1 3 1 2 eighteenths, squares sum to 2.8 / 18^2:
    # sqrt(.7 / 18^2 / 5) = sqrt(.14) / 18.
    table = scoring.scores_by_depth(*made_up())
    one, two = table[1], table[2]
    assert one["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert two["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert one["programs_standard_error"] == {"guessing": pytest.approx(0, abs=1e-15),
                                              "lookahead_1": pytest.approx(sqrt(0.035))}
    assert two["programs_standard_error"] == {"guessing": pytest.approx(sqrt(0.14) / 18),
                                              "lookahead_1": pytest.approx(sqrt(2 / 45))}
    # Room's margin is the best program's: lookahead_1 at both depths.
    assert one["room_standard_error_of"] == "lookahead_1" and one["room_standard_error"] == pytest.approx(sqrt(0.035))
    assert two["room_standard_error"] == pytest.approx(sqrt(2 / 45))
    # Model minus lookahead_1, depth 1: differences 0 .1 -.6 0 .3, mean -.04, squares about the mean
    # .0016 .0196 .3136 .0016 .1156 sum to .452: sqrt(.113 / 5) = sqrt(.0226).
    # Depth 2: differences -12 4 0 -15 6 fifteenths, mean -3.4/15, squares sum to 363.2 / 15^2:
    # sqrt(363.2 / 4 / 225 / 5) = sqrt(90.8 / 1125).
    assert one["model_minus_program"]["lookahead_1"] == {"mean": pytest.approx(-0.04),
                                                         "standard_error": pytest.approx(sqrt(0.0226))}
    assert two["model_minus_program"]["lookahead_1"] == {"mean": pytest.approx(-3.4 / 15),
                                                         "standard_error": pytest.approx(sqrt(90.8 / 1125))}
    # Model minus guessing at depth 1: guessing is the same on every problem, so the margin is the model's.
    assert one["model_minus_program"]["guessing"] == {"mean": pytest.approx(0.56 - 1 / 18),
                                                      "standard_error": pytest.approx(sqrt(0.0296))}


def test_a_depth_with_one_problem_has_no_standard_error():
    problems, picks, answers = made_up()
    problems = [s if s["id"] != "s1" else {**s, "depth": 7} for s in problems]
    table = scoring.scores_by_depth(problems, picks, answers)
    seven = table[7]
    assert seven["problems"] == 1 and seven["model"] == 1
    assert seven["model_standard_error"] is None and seven["room_standard_error"] is None
    assert set(seven["programs_standard_error"].values()) == {None}
    assert seven["model_minus_program"]["lookahead_1"] == {"mean": 0, "standard_error": None}
    four = scoring.problem_by_problem(problems, picks, answers)["lookahead_1"][7]
    assert four["only_model_if_independent_standard_error"] is None
    assert scoring.standard_error([0.5]) is None and scoring.standard_error([]) is None


def test_scores_by_depth_without_the_model():
    problems, picks, _ = made_up()
    table = scoring.scores_by_depth(problems, picks)
    assert "model" not in table[1] and table[2]["room"] == pytest.approx(1 / 3)


def test_problem_by_problem():
    table = scoring.problem_by_problem(*made_up())
    # lookahead_1, depth 1: model gets s1 s2 s5, program gets s1 s3: both s1; only model s2 s5;
    # only program s3; neither s4. Chance counts over s2 s4 s5 (program misses), each with 1 right move.
    # If independent: problems the program misses (3) x share of problems the model gets (3 of 5) = 1.8.
    assert table["lookahead_1"][1] == {"both": 1, "only_model": 2, "only_program": 1, "neither": 1,
                                       "only_model_expected_by_chance": pytest.approx(3 * CHANCE[1]),
                                       "only_model_expected_if_independent": pytest.approx(3 * 3 / 5),
                                       "only_model_if_independent_standard_error": pytest.approx(sqrt(3 * 0.6 * 0.4))}
    # depth 2: model gets s7 s8, program gets s6 s8 s9: both s8; only model s7; only program s6 s9;
    # neither s10. Chance over s7 (1 right move) and s10 (2).
    # If independent: 2 misses x 2 of 5 = 0.8.
    assert table["lookahead_1"][2] == {"both": 1, "only_model": 1, "only_program": 2, "neither": 1,
                                       "only_model_expected_by_chance": pytest.approx(CHANCE[1] + CHANCE[2]),
                                       "only_model_expected_if_independent": pytest.approx(2 * 2 / 5),
                                       "only_model_if_independent_standard_error": pytest.approx(sqrt(2 * 0.4 * 0.6))}
    # Guessing gets nothing. Depth 1: chance over all five problems (1 right move each).
    # Guessing misses all 5: 5 x 3/5 = 3 and 5 x 2/5 = 2 if independent.
    assert table["guessing"][1] == {"both": 0, "only_model": 3, "only_program": 0, "neither": 2,
                                    "only_model_expected_by_chance": pytest.approx(5 * CHANCE[1]),
                                    "only_model_expected_if_independent": pytest.approx(3),
                                    "only_model_if_independent_standard_error": pytest.approx(sqrt(5 * 0.6 * 0.4))}
    assert table["guessing"][2] == {"both": 0, "only_model": 2, "only_program": 0, "neither": 3,
                                    "only_model_expected_by_chance": pytest.approx(2 * CHANCE[2] + 2 * CHANCE[1] + CHANCE[3]),
                                    "only_model_expected_if_independent": pytest.approx(2),
                                    "only_model_if_independent_standard_error": pytest.approx(sqrt(5 * 0.4 * 0.6))}


def test_chance_formula():
    assert scoring.chance_model_gets(1, 18, 5) == pytest.approx(CHANCE[1])
    assert scoring.chance_model_gets(3, 18, 5) == pytest.approx(CHANCE[3])
    assert scoring.chance_model_gets(18, 18, 5) == pytest.approx(1)
    assert scoring.chance_model_gets(9, 18, 1) == pytest.approx(0.5)
    assert scoring.chance_model_gets(1, 2, 1) == pytest.approx(0.5)     # the options differ from problem to problem


def test_score_pick_and_bad_picks():
    assert scoring.score_pick(pick([6, 0, 12]), [0, 15], 18) == pytest.approx(1 / 3)
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([0.5] * 18, [6], 18)
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([1.0] * 17, [6], 18)
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick(pick([6]), [6], 13)       # one weight per option of the problem


def test_best_programs_name_every_tie():
    problems = [{"id": "a", "depth": 2, "options": OPTIONS, "right_moves": [6]},
                {"id": "b", "depth": 2, "options": OPTIONS, "right_moves": [0]}]
    picks = []
    for name, moves in (("zeta", [6, 0]), ("alpha", [6, 0]), ("beta", [6])):
        for problem, chosen in zip(problems, (moves[:1], moves[-1:])):
            weights = pick(chosen)
            picks.append({"problem_id": problem["id"], "program": name, "weights": weights,
                          "score": scoring.score_pick(weights, problem["right_moves"], 18)})
    row = scoring.scores_by_depth(problems, picks)[2]
    assert row["programs"] == {"alpha": 1.0, "beta": 0.5, "zeta": 1.0}
    assert row["best_programs"] == ["alpha", "zeta"] and row["room"] == 0


@pytest.mark.parametrize("break_it, message", [
    (lambda s, p, a: a.pop(), "tries"),
    (lambda s, p, a: a[0].update(failed=True), "failed"),
    (lambda s, p, a: p.pop(), "0 picks"),
    (lambda s, p, a: p.append(dict(p[0])), "2 picks"),
    (lambda s, p, a: p[0].update(score=0.25), "does not match"),
    (lambda s, p, a: a.append({**a[0], "problem_id": "s99"}), "not a test problem"),
])
def test_missing_or_broken_records_stop_the_scoring(break_it, message):
    problems, picks, answers = made_up()
    break_it(problems, picks, answers)
    with pytest.raises(scoring.ScoringError, match=message):
        scoring.scores_by_depth(problems, picks, answers)


def test_chance_uses_each_problem_s_own_number_of_options():
    # Two problems the program misses, with 2 and 4 options and one right move each. A guessing model is right on
    # 3 or more of 5 tries with chance 1/2 on the first, and (10 x 3^2 + 5 x 3 + 1) / 4^5 = 106 / 1024 on the
    # second.
    problems = [{"id": "a", "depth": 1, "options": OPTIONS[:2], "right_moves": [0]},
                {"id": "b", "depth": 1, "options": OPTIONS[:4], "right_moves": [0]}]
    picks = [{"problem_id": "a", "program": "p", "weights": [0.0, 1.0], "score": 0.0},
             {"problem_id": "b", "program": "p", "weights": [0.0, 1.0, 0.0, 0.0], "score": 0.0}]
    answers = [{"problem_id": i, "try": t, "answer_text": "no", "failed": False} for i in "ab" for t in range(1, 6)]
    row = scoring.problem_by_problem(problems, picks, answers)["p"][1]
    assert row["only_model_expected_by_chance"] == pytest.approx(0.5 + 106 / 1024)


def test_room_s_standard_error_comes_from_the_first_tied_best_program_by_name():
    # zeta and alpha both average 0.5; alpha's scores are 1 and 0 (standard error 0.5), zeta's 0.5 and 0.5 (0).
    problems = [{"id": "a", "depth": 2, "options": OPTIONS, "right_moves": [6]},
                {"id": "b", "depth": 2, "options": OPTIONS, "right_moves": [0]}]
    chosen = {"zeta": ([6, 1], [0, 1]), "alpha": ([6], [1]), "beta": ([1], [1])}
    picks = [{"problem_id": p["id"], "program": name, "weights": pick(moves),
              "score": scoring.score_pick(pick(moves), p["right_moves"], 18)}
             for name, both in chosen.items() for p, moves in zip(problems, both)]
    row = scoring.scores_by_depth(problems, picks)[2]
    assert row["best_programs"] == ["alpha", "zeta"]
    assert row["room_standard_error_of"] == "alpha" and row["room_standard_error"] == pytest.approx(0.5)
