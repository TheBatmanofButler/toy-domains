"""What the simple programs share: the form of a pick, the page score, the problem as identities, and the guard
that keeps test problems out of training.

A pick is a list of weights, one per option of the problem in the order of its `options`, adding up to 1. The
page score is the earlier run's: the goal's terms present on the page, less the terms added since the equation
that belong to neither the goal nor the equation; between pages equal on that, fewer different terms is better.
"""
from fe_ladder.identities import SUBSTITUTIONS, apply, problem_key, terms
from fe_ladder.identity_text import read_identity, write_identity
from fe_ladder.moves import options
from fe_ladder.proof import forget_earlier_problems

# Values closer than this count as tied. Learned scores that differ by less are treated as equal.
TIE_TOLERANCE = 1e-9


def pick_on(count, chosen):
    """Equal weight on the option positions in `chosen`, out of `count` options."""
    chosen = set(chosen)
    if not chosen:
        raise ValueError("a pick needs at least one option")
    return [1.0 / len(chosen) if n in chosen else 0.0 for n in range(count)]


def pick_best(values):
    """Equal weight on the options whose value is highest."""
    best = max(values)
    return pick_on(len(values), [n for n, value in enumerate(values) if value >= best - TIE_TOLERANCE])


def score(pick, right_moves):
    """The total weight on right moves."""
    return sum(pick[n] for n in right_moves)


class Problem:
    """A problem record read back into identities, with its options checked against the record."""

    def __init__(self, record):
        forget_earlier_problems()   # one problem's tables at a time
        self.id = record["id"]
        self.equation = read_identity(record["equation"])
        self.goal = read_identity(record["goal"])
        self.options = options([self.equation])
        recorded = [o["result"] for o in record["options"]]
        if [write_identity(o.result) for o in self.options] != recorded:
            raise ValueError(f"{self.id}: the recorded options are not the options of its equation")
        self.position = {o.result: n for n, o in enumerate(self.options)}
        self.equation_terms = terms(self.equation)
        self.goal_terms = terms(self.goal)


def page_score(problem, page):
    """`page`: a collection of identities holding the equation. Larger is better."""
    added = set()
    for identity in page:
        if identity != problem.equation:
            added |= terms(identity)
    every = added | problem.equation_terms
    foreign = added - problem.goal_terms - problem.equation_terms
    return (len(problem.goal_terms & every) - len(foreign), -len(every))


def next_identities(page):
    """The results of the available moves on a page (any collection of identities), as a set."""
    found = {apply(identity, s) for identity in page for s in SUBSTITUTIONS}
    found.discard(None)
    return found - set(page)


def check_training_problems(training_problems, test_problems):
    """Refuse to train on anything that is not from the training set: by its id, and by its content, so a test
    problem that reached the training data under another name, or the same problem in another form, is caught."""
    test_keys = {problem_key(read_identity(p["equation"]), read_identity(p["goal"])) for p in test_problems}
    for p in training_problems:
        if not str(p["id"]).startswith("train-"):
            raise ValueError(f"refusing to train on {p['id']}: only training problems (ids train-...) are allowed")
        if problem_key(read_identity(p["equation"]), read_identity(p["goal"])) in test_keys:
            raise ValueError(f"refusing to train on {p['id']}: it is the same problem as a test problem")
