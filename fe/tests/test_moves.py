"""Tests of moves.py: options worked out by hand on small pages."""
from fe_ladder.identity_text import read_identity, write_identity
from fe_ladder.moves import options

CAUCHY = read_identity("f(x + y) = f(x) + f(y)")


def listed(page):
    return [(write_identity(o.result), o.moves) for o in options(page)]


def test_options_of_cauchy_by_hand():
    # x=0, y=0 and y=0 and x=0 all give f(0) = 0: one option. y=1 and x=1 give the same after renaming y to x.
    # swap x,y gives the equation itself: not available.
    assert listed([CAUCHY]) == [
        ("f(0) = 0", [(1, "x=0, y=0"), (1, "y=0"), (1, "x=0")]),
        ("f(2x) - 2f(x) = 0", [(1, "y=x")]),
        ("f(x) - f(0) + f(-x) = 0", [(1, "y=-x")]),
        ("f(x + 1) - f(x) - f(1) = 0", [(1, "y=1"), (1, "x=1")]),
        ("f(x + y) - f(x) + f(-y) = 0", [(1, "x=x+y, y=-y")]),
        ("f(2x + y) - f(x + y) - f(x) = 0", [(1, "y=x+y")]),
        ("f(y) - f(-x + y) + f(-x) = 0", [(1, "x=-x")]),
        ("f(x) - f(x - y) + f(-y) = 0", [(1, "y=-y")]),
        ("f(2x) - f(x + y) - f(x - y) = 0", [(1, "x=x-y, y=x+y")]),
    ]


def test_results_already_on_the_page_are_not_options():
    # f(0) = 0 and f(2x) = 2f(x) are on the page, so no move that gives them is an option. Every move on
    # identity 2 gives it back. On identity 3, y=... leaves it as it is; x=x+y, y=-y gives f(2x + 2y) = 2f(x + y).
    page = [CAUCHY, read_identity("f(0) = 0"), read_identity("f(2x) = 2f(x)")]
    assert listed(page) == [
        ("f(x) - f(0) + f(-x) = 0", [(1, "y=-x")]),
        ("f(x + 1) - f(x) - f(1) = 0", [(1, "y=1"), (1, "x=1")]),
        ("f(x + y) - f(x) + f(-y) = 0", [(1, "x=x+y, y=-y")]),
        ("f(2x + y) - f(x + y) - f(x) = 0", [(1, "y=x+y")]),
        ("f(y) - f(-x + y) + f(-x) = 0", [(1, "x=-x")]),
        ("f(x) - f(x - y) + f(-y) = 0", [(1, "y=-y")]),
        ("f(2x) - f(x + y) - f(x - y) = 0", [(1, "x=x-y, y=x+y")]),
        ("f(2x + 2y) - 2f(x + y) = 0", [(3, "x=x+y, y=-y")]),
        ("f(2) - 2f(1) = 0", [(3, "x=1")]),
        ("2f(-x) - f(-2x) = 0", [(3, "x=-x")]),
        ("f(2x - 2y) - 2f(x - y) = 0", [(3, "x=x-y, y=x+y")]),
    ]


def test_moves_that_give_nothing_or_the_identity_itself_are_not_options():
    assert options([read_identity("f(0) = 0")]) == []
    # x=0 and x=0, y=0 give 0 = 0; y=..., swap x,y and x=-x give the identity back (after renaming y to x).
    assert listed([read_identity("f(x) - f(-x) = 2x")]) == [
        ("f(x + y) - f(-x - y) = 2x + 2y", [(1, "x=x+y, y=-y")]),
        ("f(1) - f(-1) = 2", [(1, "x=1")]),
        ("f(x - y) - f(-x + y) = 2x - 2y", [(1, "x=x-y, y=x+y")]),
    ]


def test_one_option_can_hold_moves_on_two_identities():
    page = [CAUCHY, read_identity("f(x) = 0")]
    found = listed(page)
    assert found[0] == ("f(0) = 0", [(1, "x=0, y=0"), (1, "y=0"), (1, "x=0"), (2, "x=0, y=0"), (2, "x=0")])
    assert [result for result, moves in found if moves[0][0] == 2] == ["f(x + y) = 0", "f(1) = 0", "f(-x) = 0",
                                                                      "f(x - y) = 0"]
