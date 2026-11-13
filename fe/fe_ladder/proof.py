"""The proof check: is the goal a combination, with rational coefficients, of the identities on the page?

Each distinct term is its own unknown, and the check is exact elimination over fractions, as in the earlier
run. Span keeps the page in echelon form so that the search can add one identity at a time and ask whether one
more identity would finish a proof without starting the elimination again.
"""
from heapq import heapify, heappop, heappush

from fe_ladder.identities import apply

# Terms are numbered in the order first seen; elimination works on the numbers because they compare quickly.
# The numbering is shared by everything in one process until `forget_earlier_problems` clears it. Which term is a
# pivot depends on it; whether the goal is proved does not.
_TERM_NUMBER = {}


def forget_earlier_problems():
    """Clear the numbering of terms and the table of substitution results, which otherwise grow with every
    problem (by tens of megabytes for a problem searched to depth 5). Called at the start of each problem, as the
    earlier run cleared its tables; no Span made before the call may be used after it."""
    _TERM_NUMBER.clear()
    apply.cache_clear()


def as_vector(identity):
    """{term number: coefficient} for an identity in the fixed form."""
    out = {}
    for term, c in identity:
        number = _TERM_NUMBER.get(term)
        if number is None:
            number = _TERM_NUMBER[term] = len(_TERM_NUMBER)
        out[number] = c
    return out


class Span:
    """The combinations of some identities, held as rows each with a pivot: its lowest term number, with
    coefficient 1. No two rows share a pivot, so what `reduce` leaves is the same whichever way the rows were
    found. Adding a row returns a new Span; the old one is unchanged."""
    __slots__ = ("rows",)

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else {}

    def reduce(self, vector):
        """What is left of `vector` once every pivot term is eliminated: empty exactly when it is in the span.

        Why this works: every row's terms are numbered at or above its pivot. Removing a pivot therefore brings in
        only higher-numbered terms, so taking pivots lowest first (the heap) meets each at most once and stops.
        What is left has no pivot term, and that remainder is the same whichever combination of rows removed
        them, because a non-zero combination of the rows always holds the pivot of its lowest row; so it is
        empty exactly when the vector is a combination of the rows, and two vectors that differ by such a
        combination leave the same remainder."""
        rows = self.rows
        left = dict(vector)
        waiting = [number for number in left if number in rows]
        heapify(waiting)
        done = set()
        while waiting:
            pivot = heappop(waiting)
            if pivot in done:
                continue
            done.add(pivot)
            c = left.get(pivot)
            if not c:
                continue
            for number, d in rows[pivot].items():
                value = left.get(number, 0) - c * d
                if value:
                    left[number] = value
                    if number in rows and number not in done:
                        heappush(waiting, number)
                else:
                    left.pop(number, None)
        return left

    def add_vector(self, vector):
        # The new row is reduced first, so its pivot (its lowest term) is no other row's pivot; the older rows
        # may still hold that term, which `reduce` allows for.
        left = self.reduce(vector)
        if not left:
            return self
        pivot = min(left)
        lead = left[pivot]
        rows = dict(self.rows)
        rows[pivot] = {number: c / lead for number, c in left.items()}
        return Span(rows)

    def add(self, identity):
        return self.add_vector(as_vector(identity))

    def contains(self, identity):
        return not self.reduce(as_vector(identity))


def span_of(page):
    span = Span()
    for identity in page:
        span = span.add(identity)
    return span


def is_proved(page, goal):
    return span_of(page).contains(goal)


def same_up_to_scale(left, target):
    """True if `left` is a non-zero multiple of `target` (both reduced vectors, `target` not empty). Adding an
    identity whose reduced vector is such a multiple to a page proves the goal whose reduced vector is `target`."""
    if len(left) != len(target):
        return False
    pivot = min(target)
    if pivot not in left:
        return False
    ratio = left[pivot] / target[pivot]
    return all(left.get(number) == c * ratio for number, c in target.items())
