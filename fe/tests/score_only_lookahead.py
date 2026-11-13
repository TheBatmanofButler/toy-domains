"""The earlier run's lookahead, kept for the tests only: it scores the page at the end of every sequence of
exactly `depth` moves by the page score alone and never asks whether the goal is proved. The pick is equal
weight on the first moves of the best-scoring sequences. It is not on the ladder; the slow test checks that it
gives the earlier run's score on the earlier run's problems, which checks the page score and the options."""
from fe_ladder.programs.common import Problem, next_identities, page_score, pick_on


def search(record, depth):
    problem = Problem(record)
    level = {frozenset([problem.equation]): set()}
    for moves_made in range(1, depth + 1):
        following = {}
        for page, firsts in level.items():
            for child in next_identities(page):
                reach = {problem.position[child]} if moves_made == 1 else firsts
                following.setdefault(page | {child}, set()).update(reach)
        level = following
    scores = {page: page_score(problem, page) for page in level}
    best = max(scores.values())
    return pick_on(len(problem.options), set().union(*(level[p] for p in level if scores[p] == best)))
