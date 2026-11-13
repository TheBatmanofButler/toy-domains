"""Tests of answers.py: hand-written answers, and finding the option a move belongs to."""
from conftest import record

from fe_ladder.answers import option_of, read_move


def test_hand_written_answers():
    assert read_move("Thinking done.\nMOVE: (1) y=x") == (1, "y=x")
    assert read_move("MOVE: (1) y=0\nOn second thought:\nMOVE: (1) swap x,y") == (1, "swap x,y")   # the last
    assert read_move("move: (1) y=-x") == (1, "y=-x")                                              # lower case
    assert read_move("Move : ( 2 ) x=1") == (2, "x=1")
    assert read_move("MOVE: 1 y=0") is None                                                       # no brackets
    assert read_move("MOVE: (1) x=x+y,y=-y") == (1, "x=x+y, y=-y")                                # without spaces
    assert read_move("MOVE: (1) x = x + y, y = -y") == (1, "x=x+y, y=-y")                         # with more
    assert read_move("MOVE: (1) x=x+y, y=-y") == (1, "x=x+y, y=-y")
    assert read_move("MOVE: (1) σ4") is None                                                      # its number only
    assert read_move("MOVE: (1) 4") is None
    assert read_move("MOVE: (1) y=2") is None                                                     # does not exist
    assert read_move("MOVE: (1) y=x.") == (1, "y=x")                                             # a full stop
    assert read_move("MOVE: (1) y=x, as it doubles x") == (1, "y=x")                             # a comma and words
    assert read_move("MOVE: (1) y=x because it doubles x") == (1, "y=x")                         # a reason in words
    assert read_move("MOVE: (1) x=0, y=0; then compare") == (1, "x=0, y=0")
    assert read_move("MOVE: (1) x=0, since y stays") == (1, "x=0")                               # the longest that fits
    assert read_move("MOVE: (1) swap x,y.") == (1, "swap x,y")
    assert read_move("**MOVE:** `(1) y=x`") == (1, "y=x")                                        # markdown marks
    assert read_move("MOVE: `(1) y=x`") == (1, "y=x")
    assert read_move("The answer is MOVE: (1) y=x") is None                                       # not at the start
    assert read_move("I would apply y=x to (1).") is None                                         # no MOVE: line
    assert read_move("") is None and read_move(None) is None


def test_moves_are_found_among_the_options_or_said_to_be_unavailable():
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    assert option_of(r, (1, "x=0")) == 0 and option_of(r, (1, "y=0")) == 0     # one option, two moves
    assert option_of(r, (1, "x=x-y, y=x+y")) == 8
    assert option_of(r, (1, "swap x,y")) is None                                 # gives the equation back
    assert option_of(r, (2, "y=x")) is None                                      # no identity 2 on the page


def test_y_equals_x_plus_y_is_never_read_as_y_equals_x():
    assert read_move("MOVE: (1) y=x+y") == (1, "y=x+y")
    assert read_move("MOVE: (1) y = x + y.") == (1, "y=x+y")
    assert read_move("MOVE: (1) y=x+y because") == (1, "y=x+y")
    assert read_move("MOVE: (1) y=x+") is None             # not a listed substitution, and not y=x
    assert read_move("MOVE: (1) y=xy") is None
    assert read_move("MOVE: (1) x=x+y, y=-y.") == (1, "x=x+y, y=-y")
    assert read_move("MOVE: (1) x=x-y, y=x+y") == (1, "x=x-y, y=x+y")


def test_what_may_follow_the_move():
    # After the substitution: the end of the line, one of . , ; (then anything), or spaces and then a letter
    # or an opening bracket. Anything else after spaces (an operator, a digit) makes the answer unreadable.
    assert read_move("MOVE: (1) y=x - y") is None
    assert read_move("MOVE: (1) y=x 2") is None
    assert read_move("MOVE: (1) y=x * 2") is None
    assert read_move("MOVE: (1) y = x + y") == (1, "y=x+y")
    assert read_move("MOVE: (1) y=-x because it cancels") == (1, "y=-x")
    assert read_move("MOVE: (1) y=-x (cancels f(2x))") == (1, "y=-x")
    assert read_move("MOVE: (1) x=0, y=0.") == (1, "x=0, y=0")
    assert read_move("MOVE: (1) x=0, then y=1") == (1, "x=0")
    assert read_move("MOVE: (1) y=x   ") == (1, "y=x")                                   # trailing spaces
