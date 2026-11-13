"""Tests of programs/common.py: picks, the page score worked by hand, and the guard on training problems."""
import pytest
from conftest import record

from fe_ladder.identity_text import read_identity
from fe_ladder.programs.common import (Problem, check_training_problems, page_score, pick_best, pick_on, score)


def test_picks_and_their_score():
    assert pick_on(4, [1, 3]) == [0, 0.5, 0, 0.5]
    assert pick_best([0.2, 0.7, 0.7 + 1e-12, 0.1]) == [0, 0.5, 0.5, 0]
    assert score([0.25, 0.25, 0.5, 0], [0, 2]) == 0.75
    with pytest.raises(ValueError):
        pick_on(3, [])


def test_page_score_by_hand():
    p = Problem(record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)"))
    assert page_score(p, [p.equation]) == (1, -3)                       # f(x) present; 3 terms
    assert page_score(p, [p.equation, read_identity("f(3x) = f(2x) + f(x)")]) == (2 - 1, -5)
    assert page_score(p, [p.equation, read_identity("f(x + y) = f(x) + f(y) + f(0)")]) == (1 - 1, -4)
    # A term of the equation added again is not foreign.
    assert page_score(p, [p.equation, read_identity("f(y) = f(x)")]) == (1, -3)


def test_a_record_whose_options_are_not_its_equation_s_is_refused():
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    r["options"] = r["options"][1:]
    with pytest.raises(ValueError, match="recorded options"):
        Problem(r)


def test_training_on_test_problems_is_refused():
    train = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)", "train-3-0001")
    test = record("f(x + y) = f(x) + f(y)", "f(2x) = 2f(x)", "test-1-0001")
    check_training_problems([train], [test])
    with pytest.raises(ValueError, match="only training problems"):
        check_training_problems([test], [train])
    # The same problem under another name, with x and y swapped and f scaled, is caught by its content.
    disguised = record("2f(x + y) = 2f(y) + 2f(x)", "2f(2x) = 4f(x)", "train-1-0009")
    with pytest.raises(ValueError, match="same problem as a test problem"):
        check_training_problems([disguised], [test])
