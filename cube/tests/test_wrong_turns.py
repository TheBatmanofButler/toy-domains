"""Tests of wrong_turns.py on a made-up set small enough to work every figure out by hand.

Five cubes (right turns), and the model's tries:
  distance 1: a [R]: U, U, R          wrong tries U, U
              b [F]: L, unreadable, failed, F     wrong try L (the unreadable and failed tries are left out)
              c [D]: D, D, D          every try right: left out
  distance 2: d [R U]: F, R           wrong try F
              e [L]: L, unreadable    no wrong try: left out
So distance 1 has 3 wrong tries on 2 cubes (a, b) and distance 2 has 1 wrong try on 1 cube (d), where no
standard error can be given. Every stored `turn` and `right` is deliberately wrong (`turn` is always "B"):
the figures must come from the answer text.

Picks (equal weight on the turns named):
  lookahead_1: a U F B (a three-way tie), b F (right where the model is wrong), c U, d F D, e F
  recall_top:  a U, b U, c L, d R, e U
recall_top is a control (its name is taken from the picks); lookahead_1 is not.

lookahead_1, distance 1. Match: a (1/3 + 1/3) / 2 = 1/3; b 0 (all its weight is on F, the right turn).
  Match rate (1/3 + 0) / 2 = 1/6. With two values the standard error is half their gap: 1/6.
  Uniform: a has 17 wrong turns and all its weight is on wrong ones: 1/17; b's weight is all on the right turn: 0.
  Mean 1/34.
  Shuffle: a's turn U on the other cubes b (0) and c (1): 1/2, for both of a's tries, so 1/2; b's turn L on a
  (0) and c (0): 0. Mean 1/4.
  Excess: a 1/3 - 1/2 = -1/6, b 0 - 0 = 0. Mean -1/12, standard error 1/12.
recall_top, distance 1. Match: a 1, b 0 (its weight is on U). Rate 1/2, standard error 1/2.
  Uniform: a 1/17, b 1/17 (U is wrong on both). Mean 1/17.
  Shuffle: a's U on b (1) and c (0): 1/2; b's L on a (0) and c (1): 1/2. Mean 1/2.
  Excess: a 1/2, b -1/2. Mean 0, standard error 1/2.
lookahead_1 over recall_top, distance 1: a -1/6 - 1/2 = -2/3, b 0 - (-1/2) = 1/2. Mean -1/12, standard error
  (1/2 + 2/3) / 2 = 7/12.
Distance 2, one cube (d, 2 right turns, so 16 wrong turns), no standard errors:
  lookahead_1: match 1/2 (F of F D); uniform 1/16 (all its weight on wrong turns); shuffle: F on e = 1;
  excess -1/2. recall_top: match 0 (R, right); uniform 0; shuffle: F on e (U) = 0; excess 0.
  lookahead_1 over recall_top: -1/2.
"""
import json

import pytest

from cube_ladder import scoring, wrong_turns
from cube_ladder.programs.common import pick_on

RIGHT_TURNS = {"a": ["R"], "b": ["F"], "c": ["D"], "d": ["R", "U"], "e": ["L"]}
DISTANCE = {"a": 1, "b": 1, "c": 1, "d": 2, "e": 2}
TRIES = {"a": ["U", "U", "R"], "b": ["L", "unreadable", "failed", "F"], "c": ["D", "D", "D"],
         "d": ["F", "R"], "e": ["L", "unreadable"]}
PICKS = {"lookahead_1": {"a": ["U", "F", "B"], "b": ["F"], "c": ["U"], "d": ["F", "D"], "e": ["F"]},
         "recall_top": {"a": ["U"], "b": ["U"], "c": ["L"], "d": ["R"], "e": ["U"]}}


def made_up():
    states = [{"id": s, "distance": DISTANCE[s], "right_turns": r} for s, r in RIGHT_TURNS.items()]
    picks = []
    for program, chosen in PICKS.items():
        for state in states:
            weights = pick_on(chosen[state["id"]])
            picks.append({"state_id": state["id"], "program": program, "weights": weights,
                          "score": scoring.score_pick(weights, state["right_turns"])})
    answers = []
    for state_id, tries in TRIES.items():
        for n, turn in enumerate(tries, start=1):
            text = "I am not sure." if turn in ("unreadable", "failed") else f"MOVE: {turn}"
            answers.append({"state_id": state_id, "try": n, "answer_text": text, "failed": turn == "failed",
                            "turn": "B", "right": turn not in RIGHT_TURNS[state_id]})
    return states, picks, answers


def test_wrong_tries_leave_out_right_unreadable_and_failed_tries():
    states, _, answers = made_up()
    assert wrong_turns.wrong_tries(states, answers) == {"a": ["U", "U"], "b": ["L"], "d": ["F"]}


def test_controls_are_taken_from_the_program_names():
    names = ["guessing", "lookahead_1", "recall_bottom", "recall_top", "surface_relaxed", "surface_strict"]
    assert wrong_turns.control_programs(names) == ["recall_bottom", "recall_top", "surface_strict"]


def test_every_figure_worked_by_hand():
    table = wrong_turns.same_wrong_turns(*made_up())
    assert table["lookahead_1"][1] == {
        "cubes": 2, "wrong_tries": 3, "match_rate": pytest.approx(1 / 6), "match_rate_standard_error": pytest.approx(1 / 6),
        "uniform": pytest.approx(1 / 34), "shuffle": pytest.approx(1 / 4),
        "excess": pytest.approx(-1 / 12), "excess_standard_error": pytest.approx(1 / 12),
        "excess_over_control": {"recall_top": {"mean": pytest.approx(-1 / 12), "standard_error": pytest.approx(7 / 12)}}}
    assert table["recall_top"][1] == {
        "cubes": 2, "wrong_tries": 3, "match_rate": pytest.approx(1 / 2), "match_rate_standard_error": pytest.approx(1 / 2),
        "uniform": pytest.approx(1 / 17), "shuffle": pytest.approx(1 / 2),
        "excess": pytest.approx(0, abs=1e-15), "excess_standard_error": pytest.approx(1 / 2),
        "excess_over_control": {}}   # a control is not set against itself
    assert table["lookahead_1"][2] == {
        "cubes": 1, "wrong_tries": 1, "match_rate": pytest.approx(1 / 2), "match_rate_standard_error": None,
        "uniform": pytest.approx(1 / 16), "shuffle": pytest.approx(1), "excess": pytest.approx(-1 / 2),
        "excess_standard_error": None,
        "excess_over_control": {"recall_top": {"mean": pytest.approx(-1 / 2), "standard_error": None}}}
    assert table["recall_top"][2] == {
        "cubes": 1, "wrong_tries": 1, "match_rate": 0, "match_rate_standard_error": None, "uniform": 0,
        "shuffle": 0, "excess": 0, "excess_standard_error": None, "excess_over_control": {}}


def test_the_stored_turn_is_not_trusted():
    states, picks, answers = made_up()
    before = wrong_turns.same_wrong_turns(states, picks, answers)
    # Storing the turns the text does give changes nothing ...
    for record in answers:
        record["turn"] = scoring.model_turn(record)
    assert wrong_turns.same_wrong_turns(states, picks, answers) == before
    # ... and changing the text does: c's first try now reads as a wrong turn.
    answers[next(n for n, r in enumerate(answers) if r["state_id"] == "c")]["answer_text"] = "MOVE: U"
    assert wrong_turns.same_wrong_turns(states, picks, answers)["lookahead_1"][1]["cubes"] == 3


def test_a_distance_with_no_wrong_try_or_no_other_cube():
    states, picks, answers = made_up()
    # c alone at distance 3 (all its tries right); a alone at distance 4 (wrong tries, but no other cube).
    states = [{**s, "distance": {"c": 3, "a": 4}.get(s["id"], s["distance"])} for s in states]
    table = wrong_turns.same_wrong_turns(states, picks, answers)
    empty = {"cubes": 0, "wrong_tries": 0, "match_rate": None, "match_rate_standard_error": None, "uniform": None,
             "shuffle": None, "excess": None, "excess_standard_error": None,
             "excess_over_control": {"recall_top": {"mean": None, "standard_error": None}}}
    assert table["lookahead_1"][3] == empty
    alone = table["lookahead_1"][4]
    assert alone["cubes"] == 1 and alone["wrong_tries"] == 2
    assert alone["match_rate"] == pytest.approx(1 / 3) and alone["uniform"] == pytest.approx(1 / 17)
    assert alone["shuffle"] is None and alone["excess"] is None
    assert alone["excess_over_control"] == {"recall_top": {"mean": None, "standard_error": None}}
    # Distance 1 now holds only b, so it has no shuffle either; its match (0) is unchanged.
    assert table["lookahead_1"][1]["shuffle"] is None and table["lookahead_1"][1]["match_rate"] == 0


def test_controls_can_be_given_and_the_table_survives_json():
    table = wrong_turns.same_wrong_turns(*made_up(), controls=["lookahead_1"])
    assert table["lookahead_1"][1]["excess_over_control"] == {}
    # recall_top over lookahead_1 at distance 1: a 1/2 - (-1/6) = 2/3, b -1/2 - 0 = -1/2.
    assert table["recall_top"][1]["excess_over_control"]["lookahead_1"] == {
        "mean": pytest.approx(1 / 12), "standard_error": pytest.approx(7 / 12)}
    assert json.loads(json.dumps(table))["recall_top"]["2"]["cubes"] == 1


def test_broken_picks_or_answers_stop_it():
    states, picks, answers = made_up()
    with pytest.raises(scoring.ScoringError, match="0 picks"):
        wrong_turns.same_wrong_turns(states, picks[1:], answers)
    with pytest.raises(scoring.ScoringError, match="not a test state"):
        wrong_turns.same_wrong_turns(states, picks, answers + [{**answers[0], "state_id": "z"}])
