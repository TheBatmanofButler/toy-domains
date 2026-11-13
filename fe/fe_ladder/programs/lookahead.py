"""Lookahead (search): try every sequence of up to `depth` moves and score the page it leads to.

If some sequence proves the goal, the shortest such sequences win and the search stops there, as the cube's
lookahead stops at a solved cube. Otherwise the winners are the sequences of exactly `depth` moves whose page
has the best page score. The pick is equal weight on the different first moves of the winners. A page reached
by the same moves in another order is the same page, so it is scored once and carries every first move that
reaches it; the count of sequences examined still counts every order.
"""
from dataclasses import dataclass

from fe_ladder.programs.common import Problem, next_identities, page_score, pick_on
from fe_ladder.proof import Span


@dataclass
class _Reached:
    """What is known about one page: its span, the first moves that reach it, and in how many orders."""
    span: Span
    firsts: set
    orders: int


def search(record, depth):
    """Returns (pick, number of move sequences examined)."""
    if depth < 1:
        raise ValueError("depth must be at least 1")
    problem = Problem(record)
    count = len(problem.options)
    root = frozenset([problem.equation])
    level = {root: _Reached(Span().add(problem.equation), set(), 1)}
    examined = 0
    for moves_made in range(1, depth + 1):
        following = {}
        for page, here in level.items():
            children = next_identities(page)
            examined += here.orders * len(children)
            for child in children:
                grown = page | {child}
                reach = {problem.position[child]} if moves_made == 1 else here.firsts
                if grown in following:
                    following[grown].firsts |= reach
                    following[grown].orders += here.orders
                else:
                    following[grown] = _Reached(here.span.add(child), set(reach), here.orders)
        if not following:
            raise ValueError(f"{problem.id}: no move is available after {moves_made - 1} moves")
        proving = [r.firsts for r in following.values() if r.span.contains(problem.goal)]
        if proving:
            return pick_on(count, set().union(*proving)), examined
        level = following
    scores = {page: page_score(problem, page) for page in level}
    best = max(scores.values())
    return pick_on(count, set().union(*(level[p].firsts for p in level if scores[p] == best))), examined


def picks(records, depth):
    return [search(record, depth)[0] for record in records]
