"""Tests of generator.py and families.py: the same seed and attempt give the same problem, every equation and
goal holds for its family, and the earlier run's seed gives the earlier run's problems."""
import random
from fractions import Fraction

from conftest import read_fixture

from fe_ladder.families import holds, holds_at_points, make_family, random_valid_identity, value
from fe_ladder.generator import NOT_MADE_EQUATION, NOT_MADE_GOAL, generate, textbook_equations
from fe_ladder.identity_text import read_identity, write_identity


def test_same_seed_and_attempt_give_the_same_problem():
    for attempt in range(10):
        assert generate(20261112, attempt) == generate(20261112, attempt)
    assert generate(20261112, 1) != generate(20261112, 2)
    assert generate(20261112, 1) != generate(20261113, 1)


def member(family, rng):
    m = family.random_member(rng)
    return lambda t: sum(c * t ** k for k, c in m.items())


def test_every_equation_and_goal_in_500_attempts_holds_for_its_family():
    rng = random.Random(2)
    made = not_made = 0
    for attempt in range(500):
        problem = generate(31, attempt)
        if "not_made" in problem:
            assert problem["not_made"] in (NOT_MADE_EQUATION, NOT_MADE_GOAL)
            not_made += 1
            continue
        # The family's fixed number (if it has one) is the attempt's second random draw, after the choice of
        # family: the family is rebuilt from the same draws.
        rebuilt = random.Random(f"31:{attempt}")
        rebuilt.choices(["any"], [1])
        family = make_family(problem["family"], rebuilt)
        for identity in (problem["equation"], problem["goal"]):
            assert holds(family, identity)
            function = member(family, rng)
            for _ in range(5):
                x, y = Fraction(rng.randint(-9, 9), rng.randint(1, 4)), Fraction(rng.randint(-9, 9), rng.randint(1, 4))
                assert value(identity, function, x, y) == 0
        made += 1
    assert made > 480


def test_an_identity_that_does_not_hold_is_caught():
    rng = random.Random(0)
    affine = make_family("affine", rng)
    assert holds(affine, read_identity("f(x + y) + f(0) = f(x) + f(y)"))
    assert not holds(affine, read_identity("f(x + y) = f(x) + f(y)"))
    assert not holds_at_points(affine, read_identity("f(x + y) = f(x) + f(y)"), rng)
    assert holds_at_points(affine, read_identity("f(x + y) + f(0) = f(x) + f(y)"), rng)
    quad = make_family("quad", rng)
    assert holds(quad, read_identity("f(x + y) + f(x - y) = 2f(x) + 2f(y)"))
    assert [name for name, _ in textbook_equations(quad)] == ["dalembert", "dalembert_sym"]
    for _ in range(20):
        found = random_valid_identity(quad, rng)
        assert found is None or holds(quad, found)


def test_the_earlier_run_s_seed_gives_the_earlier_run_s_problems():
    for earlier in read_fixture("earlier_attempts.jsonl"):
        problem = generate(earlier["seed"], earlier["attempt"])
        assert problem["family"] == earlier["family"], earlier["id"]
        assert write_identity(problem["equation"]) == earlier["equation"], earlier["id"]
        assert write_identity(problem["goal"]) == earlier["goal"], earlier["id"]
        assert problem["planted"]["first_chain"] == earlier["first_chain"]
        assert problem["planted"]["second_chain"] == earlier["second_chain"]
