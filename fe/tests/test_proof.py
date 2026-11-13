"""Tests of proof.py: hand cases, random combinations of a page, and agreement with the earlier run's engine."""
import random
from fractions import Fraction

from reference import earlier_core

from fe_ladder.generator import generate
from fe_ladder.identities import SUBSTITUTIONS, apply, fixed_form
from fe_ladder.identity_text import read_identity
from fe_ladder.proof import Span, as_vector, is_proved, same_up_to_scale

CAUCHY = read_identity("f(x + y) = f(x) + f(y)")
DOUBLE = read_identity("f(2x) = 2f(x)")
ZERO_AT_ZERO = read_identity("f(0) = 0")


def combination(identities, factors):
    vector = {}
    for identity, factor in zip(identities, factors):
        for term, c in identity:
            vector[term] = vector.get(term, 0) + factor * c
    return fixed_form(vector)


def test_the_goal_on_the_page_is_proved():
    assert is_proved([CAUCHY, DOUBLE], read_identity("2f(2x) - 4f(x) = 0"))


def test_a_combination_of_two_identities_is_proved_and_one_alone_is_not():
    goal = read_identity("f(2x) - 2f(x) + 3f(0) = 0")
    assert is_proved([CAUCHY, DOUBLE, ZERO_AT_ZERO], goal)
    assert not is_proved([CAUCHY, DOUBLE], goal)
    assert not is_proved([CAUCHY, ZERO_AT_ZERO], goal)


def test_a_goal_with_a_term_found_nowhere_on_the_page_is_not_proved():
    assert not is_proved([CAUCHY, DOUBLE, ZERO_AT_ZERO], read_identity("f(3x) - 3f(x) = 0"))
    assert not is_proved([CAUCHY], read_identity("f(x + y) - f(x) - f(y) = x"))


def test_one_more_identity_proves_the_goal_when_what_is_left_of_it_is_a_multiple():
    span = Span().add(CAUCHY).add(DOUBLE)
    goal_left = span.reduce(as_vector(read_identity("f(2x) - 2f(x) + 3f(0) = 0")))
    assert same_up_to_scale(span.reduce(as_vector(ZERO_AT_ZERO)), goal_left)
    assert not same_up_to_scale(span.reduce(as_vector(read_identity("f(0) = 1"))), goal_left)
    assert not same_up_to_scale(span.reduce(as_vector(read_identity("f(-x) = 0"))), goal_left)


def random_page(rng, attempt):
    made = generate(21, attempt)
    if "equation" not in made:
        return None
    page = [made["equation"]]
    for _ in range(rng.randint(1, 4)):
        result = apply(rng.choice(page), rng.choice(SUBSTITUTIONS))
        if result is not None and result not in page:
            page.append(result)
    return page


def test_random_combinations_of_a_page_are_proved():
    rng = random.Random(4)
    checked = 0
    for attempt in range(80):
        page = random_page(rng, attempt)
        if page is None:
            continue
        factors = [Fraction(rng.randint(-4, 4), rng.choice([1, 2, 3])) for _ in page]
        goal = combination(page, factors)
        if goal is not None:
            assert is_proved(page, goal)
            checked += 1
    assert checked > 50


def test_agrees_with_the_earlier_run_on_500_random_pages():
    rng = random.Random(9)
    checked, proved = 0, 0
    attempt = 0
    while checked < 500:
        attempt += 1
        page = random_page(rng, attempt)
        if page is None or len(page) < 2:
            continue
        # A combination of all but the last identity, sometimes plus the last one, sometimes plus a stray term.
        goal = combination(page[:-1], [Fraction(rng.randint(-3, 3)) for _ in page[:-1]])
        if goal is None:
            continue
        kind = rng.randrange(3)
        if kind == 1:
            goal = combination([goal, page[-1]], [1, Fraction(rng.randint(1, 3))])
        elif kind == 2:
            goal = combination([goal, read_identity("f(7x + 5) = 0")], [1, 1])
        if goal is None:
            continue
        mine = is_proved(page, goal)
        assert mine == earlier_core.engine_closes(page, goal)
        checked += 1
        proved += mine
    assert 100 < proved < 450   # both answers occur often
