"""Finds a problem's depth and right moves by trying every sequence of moves. Ported from the earlier run's search.

The page reached does not depend on the order in which its moves were made, so the search works level by level
on pages held as sets of identities, and a page reached in several orders is searched once while the counts
still count every order. At the last level a page need not be built at all: one more identity proves the goal
exactly when what is left of it, after elimination against the page, is a non-zero multiple of what is left of
the goal. PlainSearch gives the same answers by walking every sequence in order; it is for the tests only.
"""
import time
from dataclasses import dataclass, field

from fe_ladder.identities import SUBSTITUTIONS, apply
from fe_ladder.moves import options
from fe_ladder.proof import Span, as_vector, forget_earlier_problems, is_proved, same_up_to_scale

DEPTH, ALREADY_PROVED, DEEPER, OUT_OF_TIME = "depth", "already proved", "deeper than most_moves", "out of time"
TEN_MINUTES = 600.0


@dataclass
class Solution:
    outcome: str                      # one of DEPTH, ALREADY_PROVED, DEEPER, OUT_OF_TIME
    depth: int = None                 # the fewest moves that prove the goal (outcome DEPTH only)
    right: list = field(default_factory=list)   # positions, in options([equation]), of the right options
    proofs: int = None                # sequences of `depth` moves that prove the goal, every order counted
    sequences: int = None             # sequences of `depth` moves in all
    pages: list = field(default_factory=list)   # different pages at each level searched
    seconds: float = 0.0


class _OutOfTime(Exception):
    pass


class _Identities:
    """Numbers each identity met in one search, and remembers its vector, its terms and its results."""

    def __init__(self):
        self.number, self.identity, self.vector, self.terms, self.results = {}, [], [], [], []

    def add(self, identity):
        n = self.number.get(identity)
        if n is None:
            n = self.number[identity] = len(self.identity)
            self.identity.append(identity)
            self.vector.append(as_vector(identity))
            self.terms.append(frozenset(self.vector[n]))
            self.results.append(None)
        return n

    def children(self, page):
        """Numbers of the results of the available moves on a page (a frozenset of numbers)."""
        out = set()
        for n in page:
            if self.results[n] is None:
                found = (apply(self.identity[n], s) for s in SUBSTITUTIONS)
                self.results[n] = [self.add(r) for r in found if r is not None]
            out.update(r for r in self.results[n] if r not in page)
        return out


def _finishers(table, page, span, goal_left, goal_terms, children):
    """The children whose identity, added to the page, proves the goal."""
    allowed = goal_terms.union(*(table.terms[n] for n in page))
    found = []
    for r in children:
        # A finisher is (goal - combination of the page) / number, so its terms are the goal's or the page's.
        if table.terms[r] <= allowed and same_up_to_scale(span.reduce(table.vector[r]), goal_left):
            found.append(r)
    return found


def solve(equation, goal, most_moves=5, time_limit=TEN_MINUTES):
    started = time.monotonic()
    forget_earlier_problems()
    table = _Identities()
    root = frozenset([table.add(equation)])
    goal_vector = as_vector(goal)
    goal_terms = frozenset(goal_vector)
    level = {root: Span().add_vector(table.vector[min(root)])}
    if not level[root].reduce(goal_vector):
        return Solution(ALREADY_PROVED, pages=[1], seconds=time.monotonic() - started)
    orders = {root: 1}        # how many move sequences reach each page of the level
    parents = []              # parents[j][page at level j + 1] = [(page at level j, child), ...]
    pages = [1]
    try:
        for moves_made in range(most_moves):
            finishing, children_of, sequences = {}, {}, 0
            for page, span in level.items():
                _check_time(started, time_limit)
                children = table.children(page)
                sequences += orders[page] * len(children)
                found = _finishers(table, page, span, span.reduce(goal_vector), goal_terms, children)
                if found:
                    finishing[page] = set(found)
                children_of[page] = children
            if finishing:
                right = _right_options(equation, table, root, parents, finishing)
                proofs = sum(orders[page] * len(found) for page, found in finishing.items())
                return Solution(DEPTH, moves_made + 1, right, proofs, sequences, pages, time.monotonic() - started)
            if moves_made == most_moves - 1:
                break
            level, orders, parents_here = _next_level(table, level, orders, children_of, started, time_limit)
            parents.append(parents_here)
            pages.append(len(level))
    except _OutOfTime:
        return Solution(OUT_OF_TIME, pages=pages, seconds=time.monotonic() - started)
    return Solution(DEEPER, pages=pages, seconds=time.monotonic() - started)


def _check_time(started, time_limit):
    if time.monotonic() - started > time_limit:
        raise _OutOfTime()


def _next_level(table, level, orders, children_of, started, time_limit):
    following, following_orders, parents_here = {}, {}, {}
    for page, children in children_of.items():
        _check_time(started, time_limit)
        for r in children:
            grown = page | {r}
            if grown in parents_here:
                parents_here[grown].append((page, r))
                following_orders[grown] += orders[page]
            else:
                parents_here[grown] = [(page, r)]
                following[grown] = level[page].add_vector(table.vector[r])
                following_orders[grown] = orders[page]
    return following, following_orders, parents_here


def _right_options(equation, table, root, parents, finishing):
    """Walk back from the pages one move from a proof to the first moves that lead there."""
    on_the_way = finishing
    for parents_here in reversed(parents):
        earlier = {}
        for page in on_the_way:
            for parent, r in parents_here[page]:
                earlier.setdefault(parent, set()).add(r)
        on_the_way = earlier
    first_results = {table.identity[r] for r in on_the_way[root]}
    return [n for n, option in enumerate(options([equation])) if option.result in first_results]


class PlainSearch:
    """The same answers as `solve`, by trying every sequence of options in order on pages kept as lists, and
    asking `is_proved` of each. For depths up to 3; used by the tests and by nothing else."""

    def solve(self, equation, goal, most_moves=3):
        if most_moves > 3:
            raise ValueError("the plain search is for depths up to 3")
        if is_proved([equation], goal):
            return Solution(ALREADY_PROVED)
        for depth in range(1, most_moves + 1):
            count = {"proofs": 0, "sequences": 0, "right": set()}
            self._walk([equation], goal, depth, None, count)
            if count["proofs"]:
                return Solution(DEPTH, depth, sorted(count["right"]), count["proofs"], count["sequences"])
        return Solution(DEEPER)

    def _walk(self, page, goal, moves_left, first, count):
        for n, option in enumerate(options(page)):
            longer = page + [option.result]
            if moves_left == 1:
                count["sequences"] += 1
                if is_proved(longer, goal):
                    count["proofs"] += 1
                    count["right"].add(n if first is None else first)
            else:
                self._walk(longer, goal, moves_left - 1, n if first is None else first, count)
