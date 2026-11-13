"""Makes one candidate problem from a seed and an attempt number. Taken from the earlier run's second generator.

It picks a family of functions, builds an equation true for the family (a textbook equation plus random
identities that also hold for it), then builds a goal from two short chains of random substitutions: the first
chain starts from the equation, the second from the equation or from the first chain's first result, and the
goal combines the last result of each, sometimes with the equation. The chains are a planted proof; the search
measures the depth afterwards, and it can be shorter. Every equation and goal is checked to hold for its
family, exactly and at 20 random rational points; one that does not is an error in this code.
"""
import random
from fractions import Fraction

from fe_ladder.families import (NAMES, WEIGHTS, combine, holds, holds_at_points, make_family,
                                random_valid_identity)
from fe_ladder.identities import F_TERM, ONE, SUBSTITUTIONS, apply, fixed_form
from fe_ladder.identity_text import read_identity

PLANTED_LENGTH_WEIGHTS = {3: 0.30, 4: 0.35, 5: 0.35}
# How a planted proof of each length is split between the two chains.
SPLITS = {3: [(2, 1)], 4: [(3, 1), (2, 2)], 5: [(3, 2), (2, 3)]}
MULTIPLES = [1, -1, 2, -2, Fraction(1, 2), Fraction(-1, 2), 3, -3]
NOT_MADE_EQUATION, NOT_MADE_GOAL = "no equation found", "no goal found"


class GeneratorError(Exception):
    pass


def textbook_equations(family):
    """(name, equation) for the textbook equations that hold for the family."""
    d0, b0 = family.numbers.get("d0"), family.numbers.get("b0")
    texts = [("cauchy", "f(x+y)=f(x)+f(y)"), ("cauchy_f0", "f(x+y)=f(x)+f(y)-f(0)"),
             ("jensen", "f((x+y)/2)=(f(x)+f(y))/2"), ("dalembert", "f(x+y)+f(x-y)=2f(x)+2f(y)"),
             ("dalembert_sym", "f(x+y)+f(x-y)=2f(x)+f(y)+f(-y)"), ("midpoint", "f(x+y)+f(x-y)=2f(x)"),
             ("const_shift", "f(x+y)=f(x)"), ("const_xy", "f(x)=f(y)"), ("const_shift2", "f(x+y)=f(y)")]
    if d0 is not None:
        texts.append(("cauchy_poly", f"f(x+y)=f(x)+f(y)+({2 * d0})*x*y"))
        texts.append(("dalembert_poly", f"f(x+y)+f(x-y)=2f(x)+2f(y)+({-2 * d0})*(x^2)+({2 * d0})*y^2"))
    if b0 is not None:
        texts.append(("cauchy_const", f"f(x+y)=f(x)+f(y)-({b0})"))
    found = [(name, read_identity(text)) for name, text in texts]
    return [(name, e) for name, e in found if e is not None and holds(family, e)]


def _f_signs(identity):
    return (sum(1 for t, c in identity if t[0] == F_TERM and c > 0),
            sum(1 for t, c in identity if t[0] == F_TERM and c < 0))


def build_equation(family, rng, tries=60):
    """(textbook name, equation): at least 4 different f(...) terms, at least 2 of each sign, at most 14 terms,
    at least one added identity with f(...) terms, and one with powers if the family allows it. None if 60
    tries give none."""
    textbook = textbook_equations(family)
    if not textbook:
        return None
    powers_allowed = bool(family.fixed)
    for _ in range(tries):
        name, equation = rng.choice(textbook)
        added_f = added_powers = 0
        for _ in range(rng.randint(2, 4)):
            want_powers = powers_allowed and added_powers == 0
            extra = random_valid_identity(family, rng, (2, 4), (1, 2) if want_powers else (0, 0))
            if extra is None:
                continue
            times = Fraction(rng.choice([1, -1, 2, -2, 1, -1]), rng.choice([1, 1, 2]))
            longer = fixed_form(combine(equation, extra, ONE, times))
            if longer is None:
                continue
            equation = longer
            if any(t[0] != F_TERM for t, _ in extra):
                added_powers += 1
            else:
                added_f += 1
        if added_f == 0:
            extra = random_valid_identity(family, rng, (2, 4), (0, 0))
            if extra is not None:
                longer = fixed_form(combine(equation, extra, ONE, Fraction(rng.choice([1, -1, 2]))))
                if longer is not None:
                    equation, added_f = longer, 1
        if powers_allowed and added_powers == 0:
            continue
        positive, negative = _f_signs(equation)
        if sum(1 for t, _ in equation if t[0] == F_TERM) < 4 or len(equation) > 14:
            continue
        if positive < 2 or negative < 2 or added_f == 0 or not holds(family, equation):
            continue
        return name, equation
    return None


def _random_step(identity, rng, avoid):
    """A random substitution whose result is not empty, not in `avoid`, and has at least two terms."""
    order = list(range(len(SUBSTITUTIONS)))
    rng.shuffle(order)
    for n in order:
        result = apply(identity, SUBSTITUTIONS[n])
        if result is not None and result not in avoid and len(result) >= 2:
            return SUBSTITUTIONS[n], result
    return None


def _chain(start, length, rng, avoid):
    steps, results = [], []
    for _ in range(length):
        step = _random_step(start, rng, avoid)
        if step is None:
            return None
        steps.append(step[0])
        results.append(step[1])
        avoid.add(step[1])
        start = step[1]
    return steps, results


def build_goal(equation, rng, planted_length):
    """(goal, planted) or None."""
    first_length, second_length = rng.choice(SPLITS[planted_length])
    avoid = {equation}
    first = _chain(equation, first_length, rng, avoid)
    if first is None:
        return None
    second_start = rng.choice([equation, first[1][0]])
    second = _chain(second_start, second_length, rng, avoid)
    if second is None:
        return None
    first_times, second_times = Fraction(rng.choice(MULTIPLES)), Fraction(rng.choice(MULTIPLES))
    goal = combine(first[1][-1], second[1][-1], first_times, second_times)
    if rng.random() < 0.5:
        equation_times = Fraction(rng.choice(MULTIPLES))
        for term, c in equation:
            goal[term] = goal.get(term, 0) + equation_times * c
    goal = fixed_form(goal)
    if goal is None:
        return None
    return goal, {"first_chain": first[0], "second_chain": second[0],
                  "second_starts_from": "equation" if second_start == equation else "first result of the first chain"}


def generate(seed, attempt):
    """{"family", "equation", "goal", "planted"}, or {"family", "not_made": reason} when no problem is made."""
    rng = random.Random(f"{seed}:{attempt}")
    family_name = rng.choices(NAMES, WEIGHTS)[0]
    family = make_family(family_name, rng)
    built = build_equation(family, rng)
    if built is None:
        return {"family": family_name, "not_made": NOT_MADE_EQUATION}
    _, equation = built
    planted_length = rng.choices(list(PLANTED_LENGTH_WEIGHTS), list(PLANTED_LENGTH_WEIGHTS.values()))[0]
    goal = None
    for _ in range(20):
        goal = build_goal(equation, rng, planted_length)
        if goal is not None:
            break
    if goal is None:
        return {"family": family_name, "not_made": NOT_MADE_GOAL}
    goal, planted = goal
    for name, identity in (("equation", equation), ("goal", goal)):
        if not holds(family, identity) or not holds_at_points(family, identity, rng):
            raise GeneratorError(f"seed {seed} attempt {attempt}: the {name} does not hold for {family_name}")
    return {"family": family_name, "equation": equation, "goal": goal, "planted": planted}
