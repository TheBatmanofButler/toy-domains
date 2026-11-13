"""Tests of question.py: the saved text, the old run's layout, and nothing about the answer in the text."""
import json

from conftest import FIXTURES, read_fixture

from cube_ladder.question import RULE, SYSTEM_TEXT, build_question, colours, flat_drawing


def test_text_for_a_fixed_cube_equals_the_saved_copy():
    old = json.loads((FIXTURES / "old_run_question.json").read_text())
    assert build_question(old["cube"]) == (FIXTURES / "question_for_fixed_cube.txt").read_text()


def test_everything_before_the_last_paragraph_is_the_old_run_s_text():
    old = json.loads((FIXTURES / "old_run_question.json").read_text())
    new = build_question(old["cube"])
    before_new, last_new = new.rsplit("\n\n", 1)
    before_old, _ = old["user_text"].rsplit("\n\n", 1)
    assert before_new == before_old
    assert last_new == RULE
    assert SYSTEM_TEXT == old["system_text"]


def test_the_rule_is_worded_as_planned():
    # Copied from cube_plan.md, section "The model".
    assert RULE == ("A move is correct if it is the first move of a shortest possible solution. Each of the 18 "
                    "allowed moves counts as one move, so a 180 degree turn counts as one. Give one correct move, "
                    "written exactly as it appears in the list of allowed moves. Answer with `MOVE: <move>`.")


def test_text_carries_no_distance_and_no_right_turn():
    # The text is built from the cube alone. Removing the two parts that show the cube must leave the
    # same words for every state, at every distance, whatever its right turns.
    states = read_fixture("pilot_path_states.jsonl")
    fixed_parts = set()
    for state in states:
        text = build_question(state["cube"])
        fixed_parts.add(text.replace(flat_drawing(state["cube"]), "").replace(colours(state["cube"]), ""))
        assert "distance" not in text.lower() and "solved in" not in text.lower()
    assert len(fixed_parts) == 1
    assert len({s["distance"] for s in states}) == 18
