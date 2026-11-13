"""What every simple program shares: the form of a pick, and the guard that keeps test states out of training.

A pick is a list of 18 weights, one per turn in the order of cube.TURNS, adding up to 1.
"""
from cube_ladder.cube import TURNS

# Values closer than this count as tied. Learned scores that differ by less are treated as equal.
TIE_TOLERANCE = 1e-9


def pick_on(turns):
    """Equal weight on each of `turns`, nothing elsewhere."""
    chosen = set(turns)
    if not chosen:
        raise ValueError("a pick needs at least one turn")
    return [1.0 / len(chosen) if turn in chosen else 0.0 for turn in TURNS]


def pick_best(values):
    """Equal weight on the turns whose value is highest (18 values, in the order of TURNS)."""
    best = max(values)
    return pick_on([turn for turn, value in zip(TURNS, values) if value >= best - TIE_TOLERANCE])


def check_training_states(training_states, test_cubes):
    """Refuse to train on anything that is not from the training set: by its id, and by its content, so a
    test cube that reached the training data under another name is caught too."""
    test_cubes = set(test_cubes)
    for state in training_states:
        if not str(state["id"]).startswith("train-"):
            raise ValueError(f"refusing to train on {state['id']}: only training states (ids train-...) are allowed")
        if state["cube"] in test_cubes:
            raise ValueError(f"refusing to train on {state['id']}: its cube is a test cube")
