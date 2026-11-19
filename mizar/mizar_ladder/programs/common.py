"""What the simple programs share: the form of a pick, the guard that keeps test theorems out of training, and every
count a program takes from the library.

A pick is 30 weights, one per option in the order shown, adding up to 1. Every count taken from the library leaves
out the theorems of the test set (the 300 drawn, given to `Counts.for_test_set`; the other theorems of the 33
articles are counted) and, for a training problem, its own theorem: how many theorems cite a fact, how many cite it
together with a given fact, and how many facts contain a symbol.
"""
import math

from mizar_ladder import statements
from mizar_ladder.library import article, kind
from mizar_ladder.problems import OPTIONS

# Values closer than this count as tied.
TIE_TOLERANCE = 1e-9


def pick_on(numbers):
    """Equal weight on each of the option numbers (1 to 30), nothing elsewhere."""
    chosen = set(numbers)
    if not chosen or not chosen <= set(range(1, OPTIONS + 1)):
        raise ValueError(f"a pick needs at least one option number from 1 to {OPTIONS}: {sorted(chosen)}")
    return [1.0 / len(chosen) if n in chosen else 0.0 for n in range(1, OPTIONS + 1)]


def pick_best(values):
    """Equal weight on the options whose value is highest (30 values, in the options' order)."""
    best = max(values)
    return pick_on([n for n, value in enumerate(values, 1) if value >= best - TIE_TOLERANCE])


def check_training_problems(problems, test_theorems):
    """Refuse a training set that holds a test problem's theorem (`test_theorems`: the 300 drawn), under any id;
    and refuse anything whose id is not that of a training problem."""
    test_theorems = set(test_theorems)
    for problem in problems:
        if not str(problem["id"]).startswith("train-"):
            raise ValueError(f"refusing to train on {problem['id']}: only training problems (ids train-...)")
        if problem["theorem"] in test_theorems:
            raise ValueError(f"refusing to train on {problem['id']}: {problem['theorem']} is a test problem's theorem")


def ranks(values):
    """Each value's rank among `values`: 1 for the highest; tied values share the best rank they could have."""
    return [1 + sum(other > value + TIE_TOLERANCE for other in values) for value in values]


class Counts:
    """The library as the programs see it. `facts` is every (name, statement) in the library's order;
    `references` is {theorem: its cited facts} for every theorem; `left_out` is the theorems no count may use:
    the test set's (see `for_test_set`)."""

    def __init__(self, facts, references, left_out):
        self.left_out = set(left_out)
        self.statement = dict(facts)
        self.position = {name: n for n, (name, _) in enumerate(facts)}
        self.article_start = {}
        for name, _ in facts:
            if kind(name) != "other":
                self.article_start.setdefault(article(name), self.position[name])
        self.citers = {}
        for theorem, cited in references.items():
            if theorem not in self.left_out:
                for fact in set(cited):
                    self.citers.setdefault(fact, set()).add(theorem)
        self.symbols = {name: set(statements.symbols(statement)) for name, statement in facts}
        counted = [name for name, _ in facts if name not in self.left_out]
        self.fact_total = len(counted)
        self.facts_with = {}
        for name in counted:
            for symbol in self.symbols[name]:
                self.facts_with[symbol] = self.facts_with.get(symbol, 0) + 1

    @classmethod
    def for_test_set(cls, library, test_problems):
        """The counts with the theorems of `test_problems` (the test set as stage 1 drew it) left out."""
        return cls(library.facts(), {t: library.cited(t) for t in library.theorems()},
                   {p["theorem"] for p in test_problems})

    def citations(self, fact, own=None):
        """How many theorems cite `fact`, leaving out `left_out` and the problem's own theorem."""
        return len(self.citers.get(fact, set()) - {own})

    def cited_with(self, fact, given, own=None):
        """How many theorems, other than `own` and those left out, cite `fact` and at least one of `given`."""
        together = set().union(*(self.citers.get(g, set()) for g in given)) if given else set()
        return len((self.citers.get(fact, set()) & together) - {own})

    def symbol_weight(self, symbol, own=None):
        """log(facts in the library / facts containing the symbol), over the facts not left out and not `own`.
        A symbol in no counted fact is weighed as if it were in one."""
        total, having = self.fact_total, self.facts_with.get(symbol, 0)
        if own is not None and own not in self.left_out:
            total -= 1
            having -= symbol in self.symbols[own]
        return math.log(total / max(having, 1))

    def shared_sum(self, fact, others, own=None):
        """The sum of the weights of the symbols `fact` shares with any of the facts `others`."""
        shared = self.symbols[fact] & set().union(*(self.symbols[o] for o in others))
        return sum(self.symbol_weight(symbol, own) for symbol in shared)

    def from_article_start(self, fact):
        """How many facts stand between `fact` and the first theorem, lemma or definition of its article."""
        return self.position[fact] - self.article_start[article(fact)]

    def between(self, fact, theorem):
        """How many facts stand between `fact` and `theorem`."""
        return self.position[theorem] - self.position[fact] - 1


def option_names(problem):
    return [option["name"] for option in problem["options"]]
