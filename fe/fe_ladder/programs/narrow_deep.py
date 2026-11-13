"""Search, narrow and deep: keep the few best pages at each step and go on for several moves.

Start with the page of the equation. At each step, from every page kept, work out every option. If one proves
the goal, stop and pick the first move of its path (equal weight on the first moves if several paths prove it
at the same step). Otherwise keep the `paths` pages with the best page score and go on. After `most_moves`
steps with no proof, pick the first move of the best-scoring page kept. A page reached along several kept
paths is one page carrying all their first moves. Pages tied for the last place kept are chosen at random,
with a generator made from the run's seed and the problem's id, so the same seed gives the same picks and no
substitution is favoured for its place in the list.
"""
import random
from dataclasses import dataclass

from fe_ladder.programs.common import Problem, next_identities, page_score, pick_on
from fe_ladder.proof import Span

PATHS, MOST_MOVES = 3, 5


@dataclass
class _Kept:
    """What is known about one page: its span and the first moves of the kept paths that reach it."""
    span: Span
    firsts: set


def _keep(problem, candidates, paths, rng):
    """The `paths` best pages of `candidates` ({page: _Kept}), ties for the last place at random."""
    scores = {page: page_score(problem, page) for page in candidates}
    ranked = sorted(set(scores.values()), reverse=True)
    kept = []
    for value in ranked:
        # A page is a set, and sets have no fixed order: the tied pages are put in a fixed order before the
        # random draw, so that the draw alone, made from the seed and the problem's id, decides which are kept.
        tied = sorted((page for page in candidates if scores[page] == value), key=lambda p: tuple(sorted(p)))
        if len(kept) + len(tied) <= paths:
            kept += tied
        else:
            kept += rng.sample(tied, paths - len(kept))
        if len(kept) == paths:
            break
    return {page: candidates[page] for page in kept}


def search(record, seed, paths=PATHS, most_moves=MOST_MOVES):
    """Returns (pick, number of identities worked out: the options found from every page kept, at every step)."""
    problem = Problem(record)
    count = len(problem.options)
    rng = random.Random(f"{seed}:{problem.id}")
    kept = {frozenset([problem.equation]): _Kept(Span().add(problem.equation), set())}
    worked_out = 0
    for step in range(1, most_moves + 1):
        candidates = {}
        for page, here in kept.items():
            children = next_identities(page)
            worked_out += len(children)
            for child in sorted(children):
                grown = page | {child}
                reach = {problem.position[child]} if step == 1 else here.firsts
                if grown in candidates:
                    candidates[grown].firsts |= reach
                else:
                    candidates[grown] = _Kept(here.span.add(child), set(reach))
        if not candidates:
            raise ValueError(f"{problem.id}: no move is available after {step - 1} moves")
        proving = [c.firsts for c in candidates.values() if c.span.contains(problem.goal)]
        if proving:
            return pick_on(count, set().union(*proving)), worked_out
        kept = _keep(problem, candidates, paths, rng)
    scores = {page: page_score(problem, page) for page in kept}
    best = max(scores.values())
    return pick_on(count, set().union(*(kept[p].firsts for p in kept if scores[p] == best))), worked_out


def picks(records, seed, paths=PATHS, most_moves=MOST_MOVES):
    return [search(record, seed, paths, most_moves)[0] for record in records]
