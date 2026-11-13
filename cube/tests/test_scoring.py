"""Tests of scoring.py on ten made-up states, every figure worked out by hand and written in below.

States (right turns), and the model's right tries out of 5:
  distance 1: s1 [R] 5, s2 [U] 3, s3 [F'] 2, s4 [L2] 0, s5 [D] 4
  distance 2: s6 [R U] 1, s7 [B] 3, s8 [R' L F2] 5, s9 [U2] 0, s10 [D' B2] 2
Model state scores are right/5, so distance 1 = (1 + .6 + .4 + 0 + .8) / 5 = .56 and distance 2 =
(.2 + .6 + 1 + 0 + .4) / 5 = .44. The model gets (3 or more right) s1 s2 s5 and s7 s8.

Program "lookahead_1" puts weight on: s1 R (score 1), s2 U and U' (.5), s3 F' (1), s4 R (0), s5 D and U (.5);
s6 R (1), s7 B F U (1/3), s8 R' L (1), s9 U2 (1), s10 R (0). Means: distance 1 = 3/5 = .6;
distance 2 = (1 + 1/3 + 1 + 1 + 0) / 5 = 2/3. It gets (more than .5) s1 s3 and s6 s8 s9; a score of
exactly .5 (s2, s5) does not count. Guessing scores right turns / 18: distance 1 = 1/18, distance 2 =
(2 + 1 + 3 + 1 + 2) / 18 / 5 = .1. Room = 1 - .6 = .4 at distance 1 and 1 - 2/3 = 1/3 at distance 2.

Chance that a guessing model is right on 3 or more of 5 tries, with r right turns of 18 (p = r/18):
sum over k = 3..5 of C(5, k) p^k (1-p)^(5-k) = (10 r^3 (18-r)^2 + 5 r^4 (18-r) + r^5) / 18^5, so
r=1: 2976 / 1889568, r=2: 21792 / 1889568, r=3: 67068 / 1889568.
"""
from math import sqrt

import pytest

from cube_ladder import scoring
from cube_ladder.cube import TURNS
from cube_ladder.programs.common import pick_on

FIFTH_POWER = 18 ** 5
CHANCE = {1: 2976 / FIFTH_POWER, 2: 21792 / FIFTH_POWER, 3: 67068 / FIFTH_POWER}

RIGHT_TURNS = {"s1": ["R"], "s2": ["U"], "s3": ["F'"], "s4": ["L2"], "s5": ["D"],
               "s6": ["R", "U"], "s7": ["B"], "s8": ["R'", "L", "F2"], "s9": ["U2"], "s10": ["D'", "B2"]}
MODEL_RIGHT = {"s1": 5, "s2": 3, "s3": 2, "s4": 0, "s5": 4, "s6": 1, "s7": 3, "s8": 5, "s9": 0, "s10": 2}
LOOKAHEAD_TURNS = {"s1": ["R"], "s2": ["U", "U'"], "s3": ["F'"], "s4": ["R"], "s5": ["D", "U"],
                   "s6": ["R"], "s7": ["B", "F", "U"], "s8": ["R'", "L"], "s9": ["U2"], "s10": ["R"]}
POSITIONS = {"s1": 18, "s2": 18, "s3": 18, "s4": 18, "s5": 18, "s6": 18, "s7": 288, "s8": 288, "s9": 18, "s10": 288}
# Unreadable tries: s3 try 5, s4 tries 4 and 5, all of s9. Forced: s1 tries 1 and 2, all of s6.
UNREADABLE = {("s3", 5), ("s4", 4), ("s4", 5)} | {("s9", t) for t in range(1, 6)}
FORCED = {("s1", 1), ("s1", 2)} | {("s6", t) for t in range(1, 6)}


def made_up():
    states = [{"id": s, "distance": 1 if n < 5 else 2, "right_turns": r} for n, (s, r) in enumerate(RIGHT_TURNS.items())]
    picks = []
    for state in states:
        lookahead = pick_on(LOOKAHEAD_TURNS[state["id"]])
        picks.append({"state_id": state["id"], "program": "lookahead_1", "weights": lookahead,
                      "score": scoring.score_pick(lookahead, state["right_turns"]), "positions_examined": POSITIONS[state["id"]]})
        picks.append({"state_id": state["id"], "program": "guessing", "weights": pick_on(TURNS),
                      "score": len(state["right_turns"]) / 18})
    answers = []
    for state in states:
        for t in range(1, 6):
            right = t <= MODEL_RIGHT[state["id"]]
            text = (f"MOVE: {state['right_turns'][0]}" if right
                    else "I am not sure." if (state["id"], t) in UNREADABLE else "MOVE: F")
            forced = (state["id"], t) in FORCED
            thinking = 8000 if forced else 1000 * state["distance"]
            # The stored `turn` and `right` are deliberately wrong: scoring must read the answer text afresh.
            answers.append({"state_id": state["id"], "try": t, "answer_text": text, "turn": "U", "right": not right,
                            "forced": forced, "cut_off_but_readable": (state["id"], t) == ("s2", 1), "failed": False,
                            "thinking_tokens": thinking, "tokens_used": thinking + 10})
    return states, picks, answers


def test_scores_by_distance():
    table = scoring.scores_by_distance(*made_up())
    one, two = table[1], table[2]
    assert one["states"] == two["states"] == 5
    assert one["model"] == pytest.approx(0.56) and two["model"] == pytest.approx(0.44)
    assert one["programs"]["lookahead_1"] == pytest.approx(0.6) and two["programs"]["lookahead_1"] == pytest.approx(2 / 3)
    assert one["programs"]["guessing"] == pytest.approx(1 / 18) and two["programs"]["guessing"] == pytest.approx(0.1)
    assert one["best_programs"] == two["best_programs"] == ["lookahead_1"]
    assert one["room"] == pytest.approx(0.4) and two["room"] == pytest.approx(1 / 3)
    # 3 of 25 unreadable at distance 1, 5 of 25 at 2; 2 of 25 forced at 1, 5 of 25 at 2.
    assert one["unreadable_share"] == pytest.approx(3 / 25) and two["unreadable_share"] == pytest.approx(5 / 25)
    assert one["forced_share"] == pytest.approx(2 / 25) and two["forced_share"] == pytest.approx(5 / 25)
    assert one["failed_share"] == 0 and one["answers"] == 25
    assert one["cut_off_but_readable_share"] == pytest.approx(1 / 25) and two["cut_off_but_readable_share"] == 0
    # Thinking tokens: (23 x 1000 + 2 x 8000) / 25 = 1560 and (20 x 2000 + 5 x 8000) / 25 = 3200.
    assert one["thinking_tokens_mean"] == pytest.approx(1560) and two["thinking_tokens_mean"] == pytest.approx(3200)
    assert one["tokens_used_mean"] == pytest.approx(1570) and two["tokens_used_mean"] == pytest.approx(3210)
    assert one["positions_examined_mean"] == {"lookahead_1": 18}
    assert two["positions_examined_mean"] == {"lookahead_1": (18 + 288 + 288 + 18 + 288) / 5}


def test_standard_errors_worked_by_hand():
    # Each is the sample standard deviation (divisor n - 1 = 4) over sqrt(5).
    # Model, distance 1: scores 1 .6 .4 0 .8, mean .56; squared deviations .1936 .0016 .0256 .3136 .0576 sum to
    # .592; variance .148; standard error sqrt(.148 / 5) = sqrt(.0296). Distance 2 (.2 .6 1 0 .4) is the same.
    # lookahead_1, distance 1: 1 .5 1 0 .5, mean .6, squares sum to .70: sqrt(.175 / 5) = sqrt(.035).
    # Distance 2: 1 1/3 1 1 0, mean 2/3, squares sum to 8/9: sqrt((2/9) / 5) = sqrt(2/45).
    # Guessing, distance 1: all 1/18, so 0. Distance 2: 2 1 3 1 2 eighteenths, squares sum to 2.8 / 18^2:
    # sqrt(.7 / 18^2 / 5) = sqrt(.14) / 18.
    table = scoring.scores_by_distance(*made_up())
    one, two = table[1], table[2]
    assert one["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert two["model_standard_error"] == pytest.approx(sqrt(0.0296))
    assert one["programs_standard_error"] == {"guessing": pytest.approx(0, abs=1e-15),
                                              "lookahead_1": pytest.approx(sqrt(0.035))}
    assert two["programs_standard_error"] == {"guessing": pytest.approx(sqrt(0.14) / 18),
                                              "lookahead_1": pytest.approx(sqrt(2 / 45))}
    # Room's margin is the best program's: lookahead_1 at both distances.
    assert one["room_standard_error_of"] == "lookahead_1" and one["room_standard_error"] == pytest.approx(sqrt(0.035))
    assert two["room_standard_error"] == pytest.approx(sqrt(2 / 45))
    # Model minus lookahead_1, distance 1: differences 0 .1 -.6 0 .3, mean -.04, squares about the mean
    # .0016 .0196 .3136 .0016 .1156 sum to .452: sqrt(.113 / 5) = sqrt(.0226).
    # Distance 2: differences -12 4 0 -15 6 fifteenths, mean -3.4/15, squares sum to 363.2 / 15^2:
    # sqrt(363.2 / 4 / 225 / 5) = sqrt(90.8 / 1125).
    assert one["model_minus_program"]["lookahead_1"] == {"mean": pytest.approx(-0.04),
                                                         "standard_error": pytest.approx(sqrt(0.0226))}
    assert two["model_minus_program"]["lookahead_1"] == {"mean": pytest.approx(-3.4 / 15),
                                                         "standard_error": pytest.approx(sqrt(90.8 / 1125))}
    # Model minus guessing at distance 1: guessing is the same on every state, so the margin is the model's.
    assert one["model_minus_program"]["guessing"] == {"mean": pytest.approx(0.56 - 1 / 18),
                                                      "standard_error": pytest.approx(sqrt(0.0296))}


def test_a_distance_with_one_state_has_no_standard_error():
    states, picks, answers = made_up()
    states = [s if s["id"] != "s1" else {**s, "distance": 7} for s in states]
    table = scoring.scores_by_distance(states, picks, answers)
    seven = table[7]
    assert seven["states"] == 1 and seven["model"] == 1
    assert seven["model_standard_error"] is None and seven["room_standard_error"] is None
    assert set(seven["programs_standard_error"].values()) == {None}
    assert seven["model_minus_program"]["lookahead_1"] == {"mean": 0, "standard_error": None}
    four = scoring.state_by_state(states, picks, answers)["lookahead_1"][7]
    assert four["only_model_if_independent_standard_error"] is None
    assert scoring.standard_error([0.5]) is None and scoring.standard_error([]) is None


def test_scores_by_distance_without_the_model():
    states, picks, _ = made_up()
    table = scoring.scores_by_distance(states, picks)
    assert "model" not in table[1] and table[2]["room"] == pytest.approx(1 / 3)


def test_state_by_state():
    table = scoring.state_by_state(*made_up())
    # lookahead_1, distance 1: model gets s1 s2 s5, program gets s1 s3: both s1; only model s2 s5;
    # only program s3; neither s4. Chance counts over s2 s4 s5 (program misses), each with 1 right turn.
    # If independent: states the program misses (3) x share of states the model gets (3 of 5) = 1.8.
    assert table["lookahead_1"][1] == {"both": 1, "only_model": 2, "only_program": 1, "neither": 1,
                                       "only_model_expected_by_chance": pytest.approx(3 * CHANCE[1]),
                                       "only_model_expected_if_independent": pytest.approx(3 * 3 / 5),
                                       "only_model_if_independent_standard_error": pytest.approx(sqrt(3 * 0.6 * 0.4))}
    # distance 2: model gets s7 s8, program gets s6 s8 s9: both s8; only model s7; only program s6 s9;
    # neither s10. Chance over s7 (1 right turn) and s10 (2).
    # If independent: 2 misses x 2 of 5 = 0.8.
    assert table["lookahead_1"][2] == {"both": 1, "only_model": 1, "only_program": 2, "neither": 1,
                                       "only_model_expected_by_chance": pytest.approx(CHANCE[1] + CHANCE[2]),
                                       "only_model_expected_if_independent": pytest.approx(2 * 2 / 5),
                                       "only_model_if_independent_standard_error": pytest.approx(sqrt(2 * 0.4 * 0.6))}
    # Guessing gets nothing. Distance 1: chance over all five states (1 right turn each).
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
    assert scoring.chance_model_gets(1, 5) == pytest.approx(CHANCE[1])
    assert scoring.chance_model_gets(3, 5) == pytest.approx(CHANCE[3])
    assert scoring.chance_model_gets(18, 5) == pytest.approx(1)
    assert scoring.chance_model_gets(9, 1) == pytest.approx(0.5)


def test_score_pick_and_bad_picks():
    assert scoring.score_pick(pick_on(["R", "U", "F"]), ["U", "B"]) == pytest.approx(1 / 3)
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([0.5] * 18, ["R"])
    with pytest.raises(scoring.ScoringError):
        scoring.score_pick([1.0] * 17, ["R"])


def answer(text, failed=False, forced=False, thinking=1000, used=1100, cut_off_readable=False):
    return {"failed": failed, "answer_text": text, "forced": forced, "thinking_tokens": thinking,
            "tokens_used": used, "cut_off_but_readable": cut_off_readable}


def test_answer_use_counts_failed_answers_apart():
    answers = [answer(None, failed=True, thinking=None, used=0),
               answer("no idea", forced=True, thinking=8000, used=8100),
               answer("MOVE: R", thinking=2000, used=2100, cut_off_readable=True),
               answer("MOVE: U", thinking=3000, used=3100)]
    assert scoring.answer_use(answers) == {"answers": 4, "failed_share": 0.25, "unreadable_share": 0.25,
                                           "forced_share": 0.25, "cut_off_but_readable_share": 0.25,
                                           "thinking_tokens_mean": pytest.approx(13000 / 3),
                                           "tokens_used_mean": pytest.approx(13300 / 3)}
    use = scoring.answer_use(answers[:1])
    assert use["thinking_tokens_mean"] is None and use["tokens_used_mean"] is None
    # One answer without exact thinking tokens makes the exact mean unknown; tokens used are still counted.
    assert scoring.answer_use([answer("MOVE: R"), answer("MOVE: U", thinking=None)])["thinking_tokens_mean"] is None


def test_best_programs_name_every_tie():
    states = [{"id": "a", "distance": 2, "right_turns": ["R"]}, {"id": "b", "distance": 2, "right_turns": ["U"]}]
    picks = []
    for name, turns in (("zeta", ["R", "U"]), ("alpha", ["R", "U"]), ("beta", ["R"])):
        for state, chosen in zip(states, (turns[:1], turns[-1:])):
            pick = pick_on(chosen)
            picks.append({"state_id": state["id"], "program": name, "weights": pick,
                          "score": scoring.score_pick(pick, state["right_turns"])})
    row = scoring.scores_by_distance(states, picks)[2]
    assert row["programs"] == {"alpha": 1.0, "beta": 0.5, "zeta": 1.0}
    assert row["best_programs"] == ["alpha", "zeta"] and row["room"] == 0


def test_budget_figures():
    assert scoring.most_cubes_written(tokens_used=3000, tokens_per_cube=60) == 50


@pytest.mark.parametrize("break_it, message", [
    (lambda s, p, a: a.pop(), "tries"),
    (lambda s, p, a: a[0].update(failed=True), "failed"),
    (lambda s, p, a: p.pop(), "0 picks"),
    (lambda s, p, a: p.append(dict(p[0])), "2 picks"),
    (lambda s, p, a: p[0].update(score=0.25), "does not match"),
    (lambda s, p, a: a.append({**a[0], "state_id": "s99"}), "not a test state"),
])
def test_missing_or_broken_records_stop_the_scoring(break_it, message):
    states, picks, answers = made_up()
    break_it(states, picks, answers)
    with pytest.raises(scoring.ScoringError, match=message):
        scoring.scores_by_distance(states, picks, answers)
