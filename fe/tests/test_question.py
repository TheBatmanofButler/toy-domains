"""Tests of question.py: the saved text, the earlier run's layout, and nothing about the answer in the text."""
import json

from conftest import FIXTURES, read_fixture

from fe_ladder.question import RULE, SYSTEM_TEXT, build_question


def earlier():
    return json.loads((FIXTURES / "earlier_question.json").read_text())


def test_text_for_a_fixed_problem_equals_the_saved_copy():
    old = earlier()
    assert build_question(old["equation"], old["goal"]) == (FIXTURES / "question_for_fixed_problem.txt").read_text()


def test_everything_before_the_last_paragraph_is_the_earlier_run_s_text():
    old = earlier()
    new = build_question(old["equation"], old["goal"])
    before_new, last_new = new.rsplit("\n\n", 1)
    before_old, _ = old["user_text"].rsplit("\n\n", 1)
    assert before_new == before_old
    assert last_new == RULE
    assert SYSTEM_TEXT == old["system_text"]


def test_the_rule_is_worded_as_planned():
    # Copied from fe_plan.md, section "The model".
    assert RULE == ("A move is correct if it is the first move of a shortest possible proof of the goal. Each "
                    "substitution applied to one identity counts as one move. Give one correct move, with the "
                    "substitution written exactly as it appears in the list. Answer with "
                    "`MOVE: (<identity number>) <substitution>`.")


def test_text_carries_no_depth_no_right_move_and_nothing_planted():
    # The text is built from the equation and goal alone. Removing them must leave the same words for every
    # problem, at every depth, whatever its right moves and planted proof.
    fixed_parts = set()
    for p in read_fixture("earlier_problems.jsonl"):
        text = build_question(p["equation"], p["goal"])
        fixed_parts.add(text.replace(p["equation"], "").replace(p["goal"], ""))
        assert "depth" not in text.lower() and "planted" not in text.lower() and "chain" not in text.lower()
    assert len(fixed_parts) == 1
    assert build_question.__code__.co_argcount == 2
