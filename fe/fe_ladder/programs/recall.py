"""Recall: the textbook order. The first substitution in the list whose move on the equation is available.

Options are ordered by the earliest substitution among their moves, so this is always the first option; it is
worked out from the moves all the same, so that the rule reads as stated.
"""
from fe_ladder.identities import SUBSTITUTIONS
from fe_ladder.programs.common import pick_on


def first_available(record):
    """The position of the option holding the move (1, s) for the first substitution s that has one."""
    for substitution in SUBSTITUTIONS:
        for n, option in enumerate(record["options"]):
            if [1, substitution] in option["moves"]:
                return n
    raise ValueError(f"{record['id']}: no move on the equation is available")


def picks(records):
    return [pick_on(len(r["options"]), [first_available(r)]) for r in records]
