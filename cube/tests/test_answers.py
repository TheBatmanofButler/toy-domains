"""Tests of answers.py: twenty hand-written answers."""
import pytest

from cube_ladder.answers import read_turn

ANSWERS = [
    ("MOVE: R", "R"),
    ("MOVE: U'", "U'"),
    ("MOVE: F2", "F2"),
    ("I think R is best.\nMOVE: R'", "R'"),
    ("MOVE: R\nOn second thought...\nMOVE: L2", "L2"),                 # two MOVE: lines: the last counts
    ("move: R", "R"),                                                 # lower-case label is read
    ("MOVE: r", None),                                                # r is a wide turn, not one of the 18
    ("MOVE:    D2   ", "D2"),                                         # extra spaces
    ("MOVE :B", "B"),                                                 # space before the colon
    ("MOVE: X", None),                                                # a turn that does not exist
    ("MOVE: M'", None),                                               # a slice turn is not allowed
    ("The answer is R.", None),                                       # no MOVE: line
    ("", None),
    ("**MOVE: U2**", "U2"),                                           # markdown bold
    ("`MOVE: D'`", "D'"),                                             # backticks
    ("MOVE: <F>", "F"),                                               # angle brackets copied from the format
    ("MOVE: R’", "R'"),                                          # typographic prime
    ("MOVE: R U", "R"),                                               # extra words after the turn
    ("REMOVE: R", None),                                              # not the MOVE label
    ("remove: R", None),                                              # not the label in lower case either
    ("MOVE: R2'", None),                                              # not one of the 18 names
    ("Move: R", "R"),                                                 # title-case label is read
    ("move: r", None),                                                # but a lower-case turn is not
    ("MOVE: R\nmove: u2", None),                                       # the last label line counts, even if bad
    ("Move: L'\nI am done.", "L'"),
    ("MOVE: R\nIn the format MOVE: <move> I gave R.", "R"),           # stray MOVE: in prose is ignored
    ("Final answer: MOVE: U", None),                                  # the label must start the line
    ("  MOVE: B'", "B'"),                                             # spaces before the label
    ("MOVE: F\nMOVE: <move>", None),                                  # a later MOVE: line counts, even if bad
]


def test_there_are_at_least_twenty_answers():
    assert len(ANSWERS) >= 20


@pytest.mark.parametrize("text, turn", ANSWERS)
def test_reads_the_turn(text, turn):
    assert read_turn(text) == turn


def test_none_is_unreadable():
    assert read_turn(None) is None
