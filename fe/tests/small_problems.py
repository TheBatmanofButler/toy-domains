"""Small problems for the tests: a textbook equation and a goal made from one to three random moves.

They are quick to search to depth 3, so the plain search can check the real one on many of them.
"""
import random
from fractions import Fraction

from fe_ladder.families import NAMES, make_family
from fe_ladder.generator import textbook_equations
from fe_ladder.identities import SUBSTITUTIONS, apply, fixed_form


def small_problem(rng):
    """(equation, goal), or None if the random moves gave nothing usable."""
    family = make_family(rng.choice(NAMES), rng)
    _, equation = rng.choice(textbook_equations(family))
    page = [equation]
    for _ in range(rng.choice([1, 2, 2, 3])):
        result = apply(rng.choice(page), rng.choice(SUBSTITUTIONS))
        if result is not None and result not in page:
            page.append(result)
    goal = {}
    for identity in page[1:] + [equation]:
        factor = rng.choice([1, -1, 2, Fraction(1, 2), 0])
        for term, c in identity:
            goal[term] = goal.get(term, 0) + factor * c
    goal = fixed_form(goal)
    return None if goal is None else (equation, goal)


def small_problems(how_many, seed=1):
    rng = random.Random(seed)
    found = []
    while len(found) < how_many:
        problem = small_problem(rng)
        if problem is not None:
            found.append(problem)
    return found
