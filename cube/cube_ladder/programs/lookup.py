"""Lookup: always the turn that is right most often in the training set, all distances together.

This is also the reader that sees only the options: the 18 options are the same for every cube, so the
best it can do is the same as lookup. A score well above guessing would mean the options leak something.
"""
from cube_ladder.cube import TURNS
from cube_ladder.programs.common import check_training_states, pick_on


def train(training_states, test_cubes):
    """How many training states each turn is right in, over the whole training set. `test_cubes`: the
    cubes of the test set, none of which may be in the training set."""
    check_training_states(training_states, test_cubes)
    counts = {turn: 0 for turn in TURNS}
    for state in training_states:
        for turn in state["right_turns"]:
            counts[turn] += 1
    return counts


def picks(cubes, counts):
    most = max(counts.values())
    pick = pick_on([turn for turn in TURNS if counts[turn] == most])
    return [list(pick) for _ in cubes]
