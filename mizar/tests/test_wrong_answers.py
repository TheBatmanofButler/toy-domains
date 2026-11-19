"""Tests of wrong_answers.py on a made-up set small enough to work every figure out by hand.

Five problems (right option), and the model's tries:
  2 cited facts, sets:     a [1]: 2, 2, 1          wrong tries 2, 2
                           b [6]: 3, unreadable, failed, 6     wrong try 3 (the unreadable and failed tries are left out)
                           c [4]: 4, 4, 4          every try right: left out
  5 cited facts, topology: d [1]: 6, 1             wrong try 6
                           e [3]: 3, unreadable    no wrong try: left out
So the first rows (2 to 3 cited; sets) have 3 wrong tries on 2 problems (a, b), the second rows (4 to 6 cited;
topology) 1 wrong try on 1 problem (d), where no standard error can be given, and all problems 4 wrong tries on
3 problems. Every stored `option` and `right` is deliberately wrong (`option` is always 29): the figures must
come from the answer text.

Picks (equal weight on the options named):
  surface_trained: a 2 6 7 (a three-way tie), b 6 (right where the model is wrong), c 2, d 6 5, e 6
  recall:          a 2, b 2, c 3, d 1, e 2
recall is a control; surface_trained is not.

surface_trained, first rows. Match: a (1/3 + 1/3) / 2 = 1/3; b 0 (all its weight is on 6, the right option).
  Match rate (1/3 + 0) / 2 = 1/6. With two values the standard error is half their gap: 1/6.
  Uniform: a has 29 wrong options and all its weight is on wrong ones: 1/29; b's weight is all on the right one:
  0. Mean 1/58.
  Shuffle: a's option 2 on the other problems b (0) and c (1): 1/2, for both of a's tries, so 1/2; b's option 3
  on a (0) and c (0): 0. Mean 1/4.
  Excess: a 1/3 - 1/2 = -1/6, b 0 - 0 = 0. Mean -1/12, standard error 1/12.
recall, first rows. Match: a 1, b 0 (its weight is on 2). Rate 1/2, standard error 1/2.
  Uniform: a 1/29, b 1/29 (2 is wrong on both). Mean 1/29.
  Shuffle: a's 2 on b (1) and c (0): 1/2; b's 3 on a (0) and c (1): 1/2. Mean 1/2.
  Excess: a 1/2, b -1/2. Mean 0, standard error 1/2.
surface_trained over recall, first rows: a -1/6 - 1/2 = -2/3, b 0 - (-1/2) = 1/2. Mean -1/12, standard error
  (1/2 + 2/3) / 2 = 7/12.
Second rows, one problem (d), no standard errors:
  surface_trained: match 1/2 (6 of 6 5); uniform 1/29 (all its weight on wrong options); shuffle: 6 on e = 1;
  excess -1/2. recall: match 0 (1, right); uniform 0; shuffle: 6 on e (2) = 0; excess 0.
  surface_trained over recall: -1/2.
All problems (a, b, d, each set against the four others):
  surface_trained: match a 1/3, b 0, d 1/2: mean 5/18; squares about it (1 + 25 + 16) / 324, so the standard
  error is sqrt(42 / 324 / 2 / 3) = sqrt(7) / 18. Uniform (1/29 + 0 + 1/29) / 3 = 2/87.
  Shuffle: a's 2 on b c d e: (0 + 1 + 0 + 0) / 4 = 1/4; b's 3: 0; d's 6 on a b c e: (1/3 + 1 + 0 + 1) / 4 = 7/12.
  Mean 5/18. Excess: a 1/12, b 0, d -1/12: mean 0, standard error sqrt(2/144 / 2 / 3) = 1 / (12 sqrt 3).
  recall: match a 1, b 0, d 0: mean 1/3, standard error sqrt((4/9 + 1/9 + 1/9) / 2 / 3) = 1/3. Uniform
  (1/29 + 1/29 + 0) / 3 = 2/87. Shuffle: a's 2 on b c d e: (1 + 0 + 0 + 1) / 4 = 1/2; b's 3: (0 + 1 + 0 + 0) / 4
  = 1/4; d's 6: 0. Mean 1/4. Excess: a 1/2, b -1/4, d 0: mean 1/12, standard error sqrt(42/144 / 2 / 3) =
  sqrt(7) / 12.
  surface_trained over recall: a 1/12 - 1/2 = -5/12, b 0 + 1/4 = 3/12, d -1/12: mean -1/12, standard error
  sqrt(32/144 / 2 / 3) = 1 / (3 sqrt 3).
"""
import json
from math import sqrt

import pytest

from mizar_ladder import scoring, wrong_answers
from mizar_ladder.programs.common import pick_on

FIRST, SECOND, ALL = "2 to 3 cited", "4 to 6 cited", "all problems"
RIGHT = {"a": 1, "b": 6, "c": 4, "d": 1, "e": 3}
TRIES = {"a": [2, 2, 1], "b": [3, "unreadable", "failed", 6], "c": [4, 4, 4], "d": [6, 1], "e": [3, "unreadable"]}
PICKS = {"surface_trained": {"a": [2, 6, 7], "b": [6], "c": [2], "d": [6, 5], "e": [6]},
         "recall": {"a": [2], "b": [2], "c": [3], "d": [1], "e": [2]}}


def made_up():
    problems = [{"id": p, "held_back": r, "cited_count": 2 if p in "abc" else 5,
                 "group": "sets, relations and functions" if p in "abc" else "topology"} for p, r in RIGHT.items()]
    picks = []
    for program, chosen in PICKS.items():
        for problem in problems:
            weights = pick_on(chosen[problem["id"]])
            picks.append({"problem_id": problem["id"], "program": program, "weights": weights,
                          "score": scoring.score_pick(weights, [problem["held_back"]])})
    answers = []
    for problem_id, tries in TRIES.items():
        for n, option in enumerate(tries, start=1):
            text = "I am not sure." if option in ("unreadable", "failed") else f"FACT: {option}"
            answers.append({"problem_id": problem_id, "try": n, "answer_text": text, "failed": option == "failed",
                            "option": 29, "right": option != RIGHT[problem_id]})
    return problems, picks, answers


def test_wrong_tries_leave_out_right_unreadable_and_failed_tries():
    problems, _, answers = made_up()
    assert wrong_answers.wrong_tries(problems, answers) == {"a": [2, 2], "b": [3], "d": [6]}


def test_controls_are_taken_from_the_program_names():
    names = ["guessing", "options_only", "recall", "search", "surface_symbols", "surface_trained"]
    assert wrong_answers.control_programs(names) == ["recall", "surface_symbols"]


def test_every_figure_worked_by_hand():
    table = wrong_answers.same_wrong_answers(*made_up())
    assert table["surface_trained"][FIRST] == {
        "problems": 2, "wrong_tries": 3, "match_rate": pytest.approx(1 / 6),
        "match_rate_standard_error": pytest.approx(1 / 6), "uniform": pytest.approx(1 / 58),
        "shuffle": pytest.approx(1 / 4), "excess": pytest.approx(-1 / 12), "excess_standard_error": pytest.approx(1 / 12),
        "excess_over_control": {"recall": {"mean": pytest.approx(-1 / 12), "standard_error": pytest.approx(7 / 12)}}}
    assert table["recall"][FIRST] == {
        "problems": 2, "wrong_tries": 3, "match_rate": pytest.approx(1 / 2),
        "match_rate_standard_error": pytest.approx(1 / 2), "uniform": pytest.approx(1 / 29),
        "shuffle": pytest.approx(1 / 2), "excess": pytest.approx(0, abs=1e-15),
        "excess_standard_error": pytest.approx(1 / 2), "excess_over_control": {}}   # not set against itself
    assert table["surface_trained"][SECOND] == {
        "problems": 1, "wrong_tries": 1, "match_rate": pytest.approx(1 / 2), "match_rate_standard_error": None,
        "uniform": pytest.approx(1 / 29), "shuffle": pytest.approx(1), "excess": pytest.approx(-1 / 2),
        "excess_standard_error": None,
        "excess_over_control": {"recall": {"mean": pytest.approx(-1 / 2), "standard_error": None}}}
    assert table["recall"][SECOND] == {
        "problems": 1, "wrong_tries": 1, "match_rate": 0, "match_rate_standard_error": None, "uniform": 0,
        "shuffle": 0, "excess": 0, "excess_standard_error": None, "excess_over_control": {}}
    assert table["surface_trained"]["sets, relations and functions"] == table["surface_trained"][FIRST]
    assert table["recall"]["topology"] == table["recall"][SECOND]


def test_the_row_of_all_problems_worked_by_hand():
    table = wrong_answers.same_wrong_answers(*made_up())
    assert table["surface_trained"][ALL] == {
        "problems": 3, "wrong_tries": 4, "match_rate": pytest.approx(5 / 18),
        "match_rate_standard_error": pytest.approx(sqrt(7) / 18), "uniform": pytest.approx(2 / 87),
        "shuffle": pytest.approx(5 / 18), "excess": pytest.approx(0, abs=1e-15),
        "excess_standard_error": pytest.approx(1 / (12 * sqrt(3))),
        "excess_over_control": {"recall": {"mean": pytest.approx(-1 / 12),
                                           "standard_error": pytest.approx(1 / (3 * sqrt(3)))}}}
    assert table["recall"][ALL] == {
        "problems": 3, "wrong_tries": 4, "match_rate": pytest.approx(1 / 3),
        "match_rate_standard_error": pytest.approx(1 / 3), "uniform": pytest.approx(2 / 87),
        "shuffle": pytest.approx(1 / 4), "excess": pytest.approx(1 / 12),
        "excess_standard_error": pytest.approx(sqrt(7) / 12), "excess_over_control": {}}


def test_the_stored_option_is_not_trusted():
    problems, picks, answers = made_up()
    before = wrong_answers.same_wrong_answers(problems, picks, answers)
    # Storing the options the text does give changes nothing ...
    for record in answers:
        record["option"] = scoring.model_option(record)
    assert wrong_answers.same_wrong_answers(problems, picks, answers) == before
    # ... and changing the text does: c's first try now reads as a wrong option.
    answers[next(n for n, r in enumerate(answers) if r["problem_id"] == "c")]["answer_text"] = "FACT: 2"
    assert wrong_answers.same_wrong_answers(problems, picks, answers)["surface_trained"][FIRST]["problems"] == 3


def test_a_row_with_no_wrong_try_or_no_other_problem():
    problems, picks, answers = made_up()
    # c alone among the problems citing 7 or more facts (all its tries right); a alone in its article group
    # (wrong tries, but no other problem there); b alone left in the group of sets.
    problems = [{**p, "cited_count": 7} if p["id"] == "c" else {**p, "group": "orderings and lattices"}
                if p["id"] == "a" else p for p in problems]
    table = wrong_answers.same_wrong_answers(problems, picks, answers)
    empty = {"problems": 0, "wrong_tries": 0, "match_rate": None, "match_rate_standard_error": None, "uniform": None,
             "shuffle": None, "excess": None, "excess_standard_error": None,
             "excess_over_control": {"recall": {"mean": None, "standard_error": None}}}
    assert table["surface_trained"]["7 or more cited"] == empty
    alone = table["surface_trained"]["orderings and lattices"]
    assert alone["problems"] == 1 and alone["wrong_tries"] == 2
    assert alone["match_rate"] == pytest.approx(1 / 3) and alone["uniform"] == pytest.approx(1 / 29)
    assert alone["shuffle"] is None and alone["excess"] is None
    assert alone["excess_over_control"] == {"recall": {"mean": None, "standard_error": None}}
    # The group of sets now holds only b and c, b the only one with a wrong try: its shuffle is over c alone.
    sets = table["surface_trained"]["sets, relations and functions"]
    assert sets["problems"] == 1 and sets["match_rate"] == 0 and sets["shuffle"] == 0


def test_controls_can_be_given_and_the_table_survives_json():
    table = wrong_answers.same_wrong_answers(*made_up(), controls=["surface_trained"])
    assert table["surface_trained"][FIRST]["excess_over_control"] == {}
    # recall over surface_trained, first rows: a 1/2 - (-1/6) = 2/3, b -1/2 - 0 = -1/2.
    assert table["recall"][FIRST]["excess_over_control"]["surface_trained"] == {
        "mean": pytest.approx(1 / 12), "standard_error": pytest.approx(7 / 12)}
    assert json.loads(json.dumps(table))["recall"][SECOND]["problems"] == 1


def test_broken_picks_or_answers_stop_it():
    problems, picks, answers = made_up()
    with pytest.raises(scoring.ScoringError, match="0 picks"):
        wrong_answers.same_wrong_answers(problems, picks[1:], answers)
    with pytest.raises(scoring.ScoringError, match="not a test problem"):
        wrong_answers.same_wrong_answers(problems, picks, answers + [{**answers[0], "problem_id": "z"}])
