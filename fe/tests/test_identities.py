"""Tests of identities.py and identity_text.py: substitutions by hand, the fixed form, the text form, a cubic
that keeps satisfying its identities, agreement with the earlier run's code, and the key for the same problem."""
import random
from fractions import Fraction

import pytest
from conftest import read_fixture
from reference import earlier_core

from fe_ladder.families import at_argument, value
from fe_ladder.generator import generate
from fe_ladder.identities import (F_TERM, POWER, SUBSTITUTIONS, apply, fixed_form, problem_key, scale_f, swap,
                                  terms)
from fe_ladder.identity_text import read_identity, write_identity

CAUCHY = read_identity("f(x + y) = f(x) + f(y)")
BY_HAND = {
    "x=0, y=0": "f(0) = 0",
    "y=0": "f(0) = 0",
    "x=0": "f(0) = 0",
    "y=x": "f(2x) - 2f(x) = 0",
    "y=-x": "f(x) - f(0) + f(-x) = 0",
    "swap x,y": "f(x + y) - f(x) - f(y) = 0",
    "y=1": "f(x + 1) - f(x) - f(1) = 0",
    "x=x+y, y=-y": "f(x + y) - f(x) + f(-y) = 0",
    "y=x+y": "f(2x + y) - f(x + y) - f(x) = 0",
    "x=1": "f(x + 1) - f(x) - f(1) = 0",          # f(1 + y) = f(1) + f(y), then y alone is renamed x
    "x=-x": "f(y) - f(-x + y) + f(-x) = 0",
    "y=-y": "f(x - y) - f(x) - f(-y) = 0",
    "x=x-y, y=x+y": "f(2x) - f(x + y) - f(x - y) = 0",
}


@pytest.mark.parametrize("substitution", SUBSTITUTIONS)
def test_each_substitution_on_cauchy_by_hand(substitution):
    assert apply(CAUCHY, substitution) == read_identity(BY_HAND[substitution])


def test_substitutions_on_powers_by_hand():
    identity = read_identity("f(x) = x^2y + 3")
    assert apply(identity, "x=x+y, y=-y") == read_identity("f(x + y) = -x^2y - 2xy^2 - y^3 + 3")
    assert apply(identity, "x=x-y, y=x+y") == read_identity("f(x - y) = x^3 - x^2y - xy^2 + y^3 + 3")
    assert apply(identity, "y=1") == read_identity("f(x) = x^2 + 3")
    assert apply(identity, "x=0, y=0") == read_identity("f(0) = 3")
    assert apply(read_identity("f(x) - f(-x) = 2x"), "x=0") is None   # 0 = 0 is nothing


def test_there_are_13_substitutions_in_the_listed_order():
    assert SUBSTITUTIONS == ("x=0, y=0", "y=0", "x=0", "y=x", "y=-x", "swap x,y", "y=1", "x=x+y, y=-y", "y=x+y",
                             "x=1", "x=-x", "y=-y", "x=x-y, y=x+y")


def made_identities(how_many=200):
    found = []
    for attempt in range(how_many):
        made = generate(5, attempt)
        if "equation" in made:
            found += [made["equation"], made["goal"]]
    return found


@pytest.fixture(scope="module")
def generated():
    return made_identities(60)


def test_swap_and_sign_changes_twice_change_nothing(generated):
    for identity in generated:
        for substitution in ("swap x,y", "x=-x", "y=-y"):
            once = apply(identity, substitution)
            assert apply(once, substitution) == identity


def test_writing_then_reading_gives_the_identity_back(generated):
    for identity in generated:
        for s in SUBSTITUTIONS:
            result = apply(identity, s)
            if result is not None:
                assert read_identity(write_identity(result)) == result
        assert read_identity(write_identity(identity)) == identity


def test_the_writer_writes_as_the_earlier_run_did():
    for problem in read_fixture("earlier_problems.jsonl"):
        texts = [problem["equation"], problem["goal"]] + [o["result"] for o in problem["options"]]
        for text in texts:
            assert write_identity(read_identity(text)) == text


def test_scaling_an_identity_does_not_change_its_fixed_form(generated):
    for identity in generated:
        for factor in (Fraction(-3), Fraction(2, 7), Fraction(-1, 2)):
            assert fixed_form({t: c * factor for t, c in identity}) == identity
        assert identity[0][1] == 1


def test_the_fixed_form_renames_y_to_x_only_when_y_is_alone():
    assert read_identity("f(y) - f(-y) = 2y") == read_identity("f(x) - f(-x) = 2x")
    assert read_identity("f(x + y) = f(y)") != read_identity("f(x + y) = f(x)")
    assert terms(read_identity("f(y) = y^2")) == {(F_TERM, 1, 0, 0), (POWER, 2, 0)}


def random_cubic_identity(rng, cubic):
    """A random identity that the function `cubic` ({power: coefficient}) satisfies."""
    vector = {}
    for _ in range(rng.randint(1, 5)):
        argument = tuple(Fraction(rng.randint(-3, 3), rng.choice([1, 1, 2])) for _ in range(3))
        c = Fraction(rng.randint(-4, 4) or 1, rng.choice([1, 3]))
        vector[(F_TERM,) + argument] = vector.get((F_TERM,) + argument, 0) + c
        for (i, j), d in at_argument(cubic, argument).items():
            vector[(POWER, i, j)] = vector.get((POWER, i, j), 0) - c * d
    return fixed_form(vector)


def test_a_cubic_that_satisfies_an_identity_satisfies_every_substitution_of_it():
    rng = random.Random(11)
    cubic = {0: Fraction(1), 1: Fraction(-2), 3: Fraction(1, 2)}
    function = lambda t: sum(c * t ** k for k, c in cubic.items())  # noqa: E731
    points = [(Fraction(rng.randint(-9, 9), rng.randint(1, 4)), Fraction(rng.randint(-9, 9), rng.randint(1, 4)))
              for _ in range(50)]
    for _ in range(40):
        identity = random_cubic_identity(rng, cubic)
        if identity is None:
            continue
        assert all(value(identity, function, x, y) == 0 for x, y in points)
        for s in SUBSTITUTIONS:
            result = apply(identity, s)
            if result is not None:
                assert all(value(result, function, x, y) == 0 for x, y in points), s


def random_identity(rng):
    vector = {}
    for _ in range(rng.randint(1, 6)):
        argument = tuple(Fraction(rng.randint(-3, 3), rng.choice([1, 2])) for _ in range(3))
        vector[(F_TERM,) + argument] = Fraction(rng.randint(-5, 5), rng.choice([1, 2, 3]))
    for _ in range(rng.randint(0, 3)):
        i = rng.randint(0, 3)
        vector[(POWER, i, rng.randint(0, 3 - i))] = Fraction(rng.randint(-5, 5), rng.choice([1, 2]))
    return vector


def test_agrees_with_the_earlier_run_on_1000_random_identities_and_substitutions():
    rng = random.Random(3)
    checked = 0
    while checked < 1000:
        vector = random_identity(rng)
        identity = fixed_form(vector)
        assert identity == earlier_core.canon(dict(vector))
        if identity is None:
            continue
        n = rng.randrange(13)
        assert apply(identity, SUBSTITUTIONS[n]) == earlier_core._apply(identity, n + 1)
        checked += 1


def test_problem_key_is_equal_for_the_same_problem():
    equation = read_identity("f(x + y) - f(x) - f(y) = 2xy + y")
    goal = read_identity("f(2x) - 2f(x) = 2x^2 + x")
    key = problem_key(equation, goal)
    assert problem_key(swap(equation), swap(goal)) == key
    assert problem_key(scale_f(equation, Fraction(3)), scale_f(goal, Fraction(3))) == key
    assert problem_key(scale_f(swap(equation), Fraction(-1, 2)), scale_f(swap(goal), Fraction(-1, 2))) == key
    # Written by hand: f scaled by 2 and the variables swapped.
    assert problem_key(read_identity("2f(x + y) - 2f(x) - 2f(y) = 2xy + x"), read_identity("2f(2x) - 4f(x) = 2x^2 + x")) == key


def test_problem_key_differs_for_different_problems():
    equation = read_identity("f(x + y) - f(x) - f(y) = 2xy + y")
    goal = read_identity("f(2x) - 2f(x) = 2x^2 + x")
    key = problem_key(equation, goal)
    assert problem_key(equation, read_identity("f(2x) - 2f(x) = 2x^2")) != key
    assert problem_key(scale_f(equation, Fraction(3)), goal) != key          # f scaled in one of the two only
    both = read_identity("f(x + 2y) - f(x) = y")
    swapped_equation = read_identity("f(x + y) - f(x) - f(y) = 2xy + x")
    assert problem_key(swapped_equation, both) != problem_key(equation, both)   # swapped in one of the two only
    assert problem_key(swapped_equation, swap(both)) == problem_key(equation, both)
    without_powers = read_identity("f(x + y) = f(x) + f(y)")
    assert problem_key(without_powers, read_identity("f(2x) = 2f(x)")) == problem_key(
        scale_f(without_powers, Fraction(5)), read_identity("f(2x) = 2f(x)"))
