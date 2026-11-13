"""Tests of wrong_moves.py on a made-up set small enough to work every figure out by hand.

Five problems with the 18 made-up options of made_up.py, named here by six letters as labels
(U 0, D 3, R 6, L 9, F 12, B 15), with their right moves, and the model's tries:
  depth 1: a [R]: U, U, R          wrong tries U, U
              b [F]: L, unreadable, failed, F     wrong try L (the unreadable and failed tries are left out)
              c [D]: D, D, D          every try right: left out
  depth 2: d [R U]: F, R           wrong try F
              e [L]: L, unreadable    no wrong try: left out
So depth 1 has 3 wrong tries on 2 problems (a, b) and depth 2 has 1 wrong try on 1 problem (d), where no
standard error can be given. Every stored `move`, `option` and `right` is deliberately wrong (`move` is always
option B's): the figures must come from the answer text.

Picks (equal weight on the moves named):
  lookahead_1: a U F B (a three-way tie), b F (right where the model is wrong), c U, d F D, e F
  recall:  a U, b U, c L, d R, e U
recall is a control (its name is taken from the picks); lookahead_1 is not.

lookahead_1, depth 1. Match: a (1/3 + 1/3) / 2 = 1/3; b 0 (all its weight is on F, the right move).
  Match rate (1/3 + 0) / 2 = 1/6. With two values the standard error is half their gap: 1/6.
  Uniform: a has 17 wrong moves and all its weight is on wrong ones: 1/17; b's weight is all on the right move: 0.
  Mean 1/34.
  Shuffle: a's move U on the other problems b (0) and c (1): 1/2, for both of a's tries, so 1/2; b's move L on a
  (0) and c (0): 0. Mean 1/4.
  Excess: a 1/3 - 1/2 = -1/6, b 0 - 0 = 0. Mean -1/12, standard error 1/12.
recall, depth 1. Match: a 1, b 0 (its weight is on U). Rate 1/2, standard error 1/2.
  Uniform: a 1/17, b 1/17 (U is wrong on both). Mean 1/17.
  Shuffle: a's U on b (1) and c (0): 1/2; b's L on a (0) and c (1): 1/2. Mean 1/2.
  Excess: a 1/2, b -1/2. Mean 0, standard error 1/2.
lookahead_1 over recall, depth 1: a -1/6 - 1/2 = -2/3, b 0 - (-1/2) = 1/2. Mean -1/12, standard error
  (1/2 + 2/3) / 2 = 7/12.
Depth 2, one problem (d, 2 right moves, so 16 wrong moves), no standard errors:
  lookahead_1: match 1/2 (F of F D); uniform 1/16 (all its weight on wrong moves); shuffle: F on e = 1;
  excess -1/2. recall: match 0 (R, right); uniform 0; shuffle: F on e (U) = 0; excess 0.
  lookahead_1 over recall: -1/2.
"""
import json

import pytest
from made_up import NOT_AVAILABLE, OPTIONS, move_text, pick

from fe_ladder import scoring, wrong_moves
from fe_ladder.identities import SUBSTITUTIONS

U, D, R, L, F, B = 0, 3, 6, 9, 12, 15
RIGHT_MOVES = {"a": [R], "b": [F], "c": [D], "d": [R, U], "e": [L]}
DEPTH = {"a": 1, "b": 1, "c": 1, "d": 2, "e": 2}
TRIES = {"a": [U, U, R], "b": [L, "unreadable", "failed", F], "c": [D, D, D],
         "d": [F, R], "e": [L, "unreadable"]}
PICKS = {"lookahead_1": {"a": [U, F, B], "b": [F], "c": [U], "d": [F, D], "e": [F]},
         "recall": {"a": [U], "b": [U], "c": [L], "d": [R], "e": [U]}}


def made_up():
    problems = [{"id": s, "depth": DEPTH[s], "options": OPTIONS, "right_moves": r} for s, r in RIGHT_MOVES.items()]
    picks = []
    for program, chosen in PICKS.items():
        for problem in problems:
            weights = pick(chosen[problem["id"]])
            picks.append({"problem_id": problem["id"], "program": program, "weights": weights,
                          "score": scoring.score_pick(weights, problem["right_moves"], 18)})
    answers = []
    for problem_id, tries in TRIES.items():
        for n, move in enumerate(tries, start=1):
            text = "I am not sure." if move in ("unreadable", "failed") else move_text(move)
            answers.append({"problem_id": problem_id, "try": n, "answer_text": text, "failed": move == "failed",
                            "move": OPTIONS[B]["moves"][0], "option": B, "right": move not in RIGHT_MOVES[problem_id]})
    return problems, picks, answers


def moves(*options):
    return [tuple(OPTIONS[n]["moves"][0]) for n in options]


def test_wrong_tries_leave_out_right_unreadable_and_failed_tries():
    problems, _, answers = made_up()
    assert wrong_moves.wrong_tries(problems, answers) == {"a": moves(U, U), "b": moves(L), "d": moves(F)}


def test_a_move_that_is_not_available_is_left_out_too():
    problems, _, answers = made_up()
    answers[0]["answer_text"] = NOT_AVAILABLE
    assert wrong_moves.wrong_tries(problems, answers) == {"a": moves(U), "b": moves(L), "d": moves(F)}
    # How many tries were left out for that reason is counted, per depth, for every program.
    problems, picks, _ = made_up()
    table = wrong_moves.same_wrong_moves(problems, picks, answers)
    assert table["lookahead_1"][1]["not_available_left_out"] == 1 and table["recall"][1]["not_available_left_out"] == 1
    assert table["lookahead_1"][1]["wrong_tries"] == 2 and table["lookahead_1"][2]["not_available_left_out"] == 0
    assert wrong_moves.not_available_tries(problems, answers) == {"a": 1}


def test_controls_are_taken_from_the_program_names():
    names = ["guessing", "lookahead_1", "narrow_deep", "recall", "surface_relaxed", "surface_strict"]
    assert wrong_moves.control_programs(names) == ["recall", "surface_strict"]


def test_every_figure_worked_by_hand():
    table = wrong_moves.same_wrong_moves(*made_up())
    assert table["lookahead_1"][1] == {
        "problems": 2, "wrong_tries": 3, "not_available_left_out": 0, "match_rate": pytest.approx(1 / 6), "match_rate_standard_error": pytest.approx(1 / 6),
        "uniform": pytest.approx(1 / 34), "shuffle": pytest.approx(1 / 4),
        "excess": pytest.approx(-1 / 12), "excess_standard_error": pytest.approx(1 / 12),
        "excess_over_control": {"recall": {"mean": pytest.approx(-1 / 12), "standard_error": pytest.approx(7 / 12)}}}
    assert table["recall"][1] == {
        "problems": 2, "wrong_tries": 3, "not_available_left_out": 0, "match_rate": pytest.approx(1 / 2), "match_rate_standard_error": pytest.approx(1 / 2),
        "uniform": pytest.approx(1 / 17), "shuffle": pytest.approx(1 / 2),
        "excess": pytest.approx(0, abs=1e-15), "excess_standard_error": pytest.approx(1 / 2),
        "excess_over_control": {}}   # a control is not set against itself
    assert table["lookahead_1"][2] == {
        "problems": 1, "wrong_tries": 1, "not_available_left_out": 0, "match_rate": pytest.approx(1 / 2), "match_rate_standard_error": None,
        "uniform": pytest.approx(1 / 16), "shuffle": pytest.approx(1), "excess": pytest.approx(-1 / 2),
        "excess_standard_error": None,
        "excess_over_control": {"recall": {"mean": pytest.approx(-1 / 2), "standard_error": None}}}
    assert table["recall"][2] == {
        "problems": 1, "wrong_tries": 1, "not_available_left_out": 0, "match_rate": 0, "match_rate_standard_error": None, "uniform": 0,
        "shuffle": 0, "excess": 0, "excess_standard_error": None, "excess_over_control": {}}


def test_the_shuffle_matches_a_move_to_the_options_of_each_other_problem():
    # Problem x has the 18 options; on problem y, (1, y=x) is option 1 of 3 and (1, y=0) is not available.
    # The model's wrong move on x is (1, y=x) (option 3 there). The program puts 1/2 on y's option 1, so the
    # shuffle figure for x is 1/2, though y's option 3 does not exist; a move not available on y would weigh 0.
    other = [{"result": "", "moves": [[1, "y=-x"]]}, {"result": "", "moves": [[1, "y=x"]]},
             {"result": "", "moves": [[1, "swap x,y"]]}]
    problems = [{"id": "x", "depth": 1, "options": OPTIONS, "right_moves": [0]},
                {"id": "y", "depth": 1, "options": other, "right_moves": [0]}]
    picks = [{"problem_id": "x", "program": "p", "weights": pick([0]), "score": 1.0},
             {"problem_id": "y", "program": "p", "weights": [0.5, 0.5, 0], "score": 0.5}]
    answers = [{"problem_id": "x", "try": 1, "answer_text": f"MOVE: (1) {SUBSTITUTIONS[3]}", "failed": False},
               {"problem_id": "y", "try": 1, "answer_text": "MOVE: (1) y=-x", "failed": False}]
    row = wrong_moves.same_wrong_moves(problems, picks, answers)["p"][1]
    assert row["problems"] == 1 and row["match_rate"] == 0 and row["shuffle"] == 0.5
    answers[0]["answer_text"] = f"MOVE: (1) {SUBSTITUTIONS[1]}"     # (1, y=0): option 1 on x, none on y
    assert wrong_moves.same_wrong_moves(problems, picks, answers)["p"][1]["shuffle"] == 0


def test_the_stored_move_is_not_trusted():
    problems, picks, answers = made_up()
    before = wrong_moves.same_wrong_moves(problems, picks, answers)
    # Storing the moves the text does give changes nothing ...
    for record in answers:
        record["move"] = scoring.model_move(record)
    assert wrong_moves.same_wrong_moves(problems, picks, answers) == before
    # ... and changing the text does: c's first try now reads as a wrong move.
    answers[next(n for n, r in enumerate(answers) if r["problem_id"] == "c")]["answer_text"] = move_text(U)
    assert wrong_moves.same_wrong_moves(problems, picks, answers)["lookahead_1"][1]["problems"] == 3


def test_a_depth_with_no_wrong_try_or_no_other_problem():
    problems, picks, answers = made_up()
    # c alone at depth 3 (all its tries right); a alone at depth 4 (wrong tries, but no other problem).
    problems = [{**s, "depth": {"c": 3, "a": 4}.get(s["id"], s["depth"])} for s in problems]
    table = wrong_moves.same_wrong_moves(problems, picks, answers)
    empty = {"problems": 0, "wrong_tries": 0, "not_available_left_out": 0, "match_rate": None, "match_rate_standard_error": None, "uniform": None,
             "shuffle": None, "excess": None, "excess_standard_error": None,
             "excess_over_control": {"recall": {"mean": None, "standard_error": None}}}
    assert table["lookahead_1"][3] == empty
    alone = table["lookahead_1"][4]
    assert alone["problems"] == 1 and alone["wrong_tries"] == 2
    assert alone["match_rate"] == pytest.approx(1 / 3) and alone["uniform"] == pytest.approx(1 / 17)
    assert alone["shuffle"] is None and alone["excess"] is None
    assert alone["excess_over_control"] == {"recall": {"mean": None, "standard_error": None}}
    # Depth 1 now holds only b, so it has no shuffle either; its match (0) is unchanged.
    assert table["lookahead_1"][1]["shuffle"] is None and table["lookahead_1"][1]["match_rate"] == 0


def test_controls_can_be_given_and_the_table_survives_json():
    table = wrong_moves.same_wrong_moves(*made_up(), controls=["lookahead_1"])
    assert table["lookahead_1"][1]["excess_over_control"] == {}
    # recall over lookahead_1 at depth 1: a 1/2 - (-1/6) = 2/3, b -1/2 - 0 = -1/2.
    assert table["recall"][1]["excess_over_control"]["lookahead_1"] == {
        "mean": pytest.approx(1 / 12), "standard_error": pytest.approx(7 / 12)}
    assert json.loads(json.dumps(table))["recall"]["2"]["problems"] == 1


def test_broken_picks_or_answers_stop_it():
    problems, picks, answers = made_up()
    with pytest.raises(scoring.ScoringError, match="0 picks"):
        wrong_moves.same_wrong_moves(problems, picks[1:], answers)
    with pytest.raises(scoring.ScoringError, match="not a test problem"):
        wrong_moves.same_wrong_moves(problems, picks, answers + [{**answers[0], "problem_id": "z"}])
