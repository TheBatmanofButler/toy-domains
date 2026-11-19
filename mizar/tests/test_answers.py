"""Tests of answers.py: hand-written answers."""
import pytest

from mizar_ladder.answers import read_option

ANSWERS = [
    ("FACT: 7", 7),
    ("FACT: 30", 30),
    ("FACT: 1", 1),
    ("I think option 4 fits.\nFACT: 12", 12),
    ("FACT: 3\nOn second thought...\nFACT: 14", 14),                  # two FACT: lines: the last counts
    ("fact: 5", 5),                                                   # the label in any letter case
    ("Fact: 6", 6),
    ("FACT: 31", None),                                               # out of range
    ("FACT: 0", None),
    ("FACT: seven", None),                                            # a number written as a word
    ("FACT: 7 because it gives the union", None),                     # a number followed by a reason
    ("FACT: 7, since it is used", None),
    ("The answer is 7.", None),                                       # no FACT: line
    ("", None),
    ("**FACT: 9**", 9),                                               # asterisks
    ("`FACT: 10`", 10),                                               # backticks
    ("FACT: 11.", 11),                                                # a closing full stop
    ("FACT:    8   ", 8),                                             # extra spaces
    ("FACT :2", 2),                                                   # a space before the colon
    ("  FACT: 4", 4),                                                 # spaces before the label
    ("Final answer: FACT: 4", None),                                  # the label must start the line
    ("FACT: 4\nIn the format FACT: <number> I gave 4.", 4),           # a stray FACT: in prose is not a label line
    ("FACT: 4\nFACT: <number>", None),                                # the last FACT: line counts, even if bad
    ("FACT: <4>", None),
    ("FACT: 4.5", None),
    ("FACT: -3", None),
    ("FACT: 07", 7),
    ("FACTS: 7", None),                                               # not the label
]


def test_there_are_at_least_twenty_answers():
    assert len(ANSWERS) >= 20


@pytest.mark.parametrize("text, option", ANSWERS)
def test_reads_the_option(text, option):
    assert read_option(text) == option


def test_none_is_unreadable():
    assert read_option(None) is None
