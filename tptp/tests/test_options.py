"""Tests for options.py: the draw is fixed by the seed and the problem's id, never holds the goal, and needs
30 facts."""
from tptp_count.equations import key_up_to_variables, read_equation
from tptp_count.options import COUNT, draw

FACTS = [read_equation(f"f(X,g{i}(X))=X") for i in range(40)]
GOAL = read_equation("f(Y,g3(Y))=Y")      # a renaming of fact 3


def test_same_seed_and_id_same_draw():
    assert draw(FACTS, GOAL, 20261112, "GRP001-1") == draw(list(FACTS), GOAL, 20261112, "GRP001-1")


def test_a_different_id_or_seed_a_different_draw():
    first = draw(FACTS, GOAL, 20261112, "GRP001-1")
    assert draw(FACTS, GOAL, 20261112, "GRP001-2") != first
    assert draw(FACTS, GOAL, 1, "GRP001-1") != first


def test_the_draw_is_30_different_facts_in_the_order_drawn():
    drawn = draw(FACTS, GOAL, 20261112, "GRP001-1")
    assert len(drawn) == COUNT == 30 and len({key_up_to_variables(f) for f in drawn}) == 30
    assert drawn != [f for f in FACTS if f in drawn]     # not simply the order of the list


def test_the_goal_is_never_among_the_30():
    for number in range(50):
        drawn = draw(FACTS, GOAL, number, "GRP001-1")
        assert key_up_to_variables(GOAL) not in {key_up_to_variables(f) for f in drawn}


def test_exactly_29_facts_is_too_few():
    assert draw(FACTS[:29], read_equation("a=b"), 20261112, "x") is None
    assert draw(FACTS[:30], read_equation("a=b"), 20261112, "x") is not None
    assert draw(FACTS[:30], GOAL, 20261112, "x") is None      # 30, but one is the goal


def test_the_draw_is_the_one_recorded():
    """The first five drawn, recorded when the code was written, so that any change in how the generator is
    made (which would change every problem's options) is seen."""
    drawn = draw(FACTS, read_equation("a=b"), 20261112, "GRP001-1")
    assert [int(str(f[0][2][0])[1:]) for f in drawn[:5]] == EXPECTED_FIRST_FIVE


EXPECTED_FIRST_FIVE = [11, 17, 14, 6, 22]


def test_with_exactly_30_facts_the_order_is_still_drawn():
    drawn = draw(FACTS[:30], read_equation("a=b"), 20261112, "GRP001-1")
    assert sorted(map(key_up_to_variables, drawn)) == sorted(map(key_up_to_variables, FACTS[:30]))
    assert drawn != FACTS[:30]
    orders = {tuple(map(key_up_to_variables, draw(FACTS[:30], read_equation("a=b"), 20261112, f"P{n}")))
              for n in range(5)}
    assert len(orders) == 5     # each problem gets its own order
