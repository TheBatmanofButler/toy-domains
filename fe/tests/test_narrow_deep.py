"""Tests of programs/narrow_deep.py: problems worked by hand, one where it is led astray, and its ties."""
import pytest
from conftest import record
from test_lookahead import ASTRAY

from fe_ladder.programs.common import score
from fe_ladder.programs.narrow_deep import picks, search


def test_led_astray_with_one_path_and_not_with_two():
    # See test_lookahead.py: x=1 (option 5) has the best page score after one move, so with one path kept the
    # search goes on from there only and never comes back to y=1 (option 3), the right move.
    r = record(*ASTRAY)
    pick, _ = search(r, seed=1, paths=1)
    assert pick == [0, 0, 0, 0, 0, 1.0, 0, 0, 0] and score(pick, r["right_moves"]) == 0
    # With two paths, y=1 and x=1 are both kept (scores (2, -3) and (3, -4); the next best is f(x) = f(0) at
    # (2, -3), tied with y=1, so one of the two is drawn at random). Either way the second step finds the proof
    # through y=1 then x=0.
    for seed in range(5):
        pick, _ = search(r, seed=seed, paths=2)
        assert pick == [0, 0, 0, 1.0, 0, 0, 0, 0, 0] or score(pick, r["right_moves"]) == 0
    assert any(search(r, seed=seed, paths=2)[0][3] == 1.0 for seed in range(5))
    pick, examined = search(r, seed=1, paths=3)
    assert pick == [0, 0, 0, 1.0, 0, 0, 0, 0, 0]


def test_hand_worked_cauchy_three_times_with_four_paths():
    # After one move four pages tie at (0, -4) (see test_lookahead.py); with four paths all are kept, so no
    # random choice is made at the first step. The proof is found at the third step, from a kept page reached
    # through y=x+y (option 5); the page holding both f(2x) = 2f(x) and f(2x + y) = f(x) + f(x + y) was not among
    # the four kept at the second step, so y=x (option 1), also right, gets no weight.
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    pick, _ = search(r, seed=1, paths=4)
    assert pick == [0, 0, 0, 0, 0, 1.0, 0, 0, 0] and score(pick, r["right_moves"]) == 1


def test_same_seed_same_picks_and_ties_are_drawn_from_the_seed():
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    assert picks([r], 7) == picks([r], 7)
    # Three paths out of four tied pages: which three depends on the seed, so some seeds differ.
    found = {tuple(search(r, seed=seed, paths=3, most_moves=1)[0]) for seed in range(20)}
    assert len(found) >= 2
    for pick in found:   # after one move the best kept page wins; all four tie, so it is one of the kept three
        assert sum(pick) == pytest.approx(1)


def test_without_a_proof_the_best_kept_page_is_picked():
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    pick, examined = search(r, seed=1, paths=9, most_moves=1)
    assert pick == [0.25, 0.25, 0, 0, 0.25, 0.25, 0, 0, 0] and examined == 9


def test_the_random_choices_depend_on_the_seed_and_the_problem_together():
    # Four pages tie for three places after one move. With one seed, problems that differ only in their id are
    # drawn differently; and one id is drawn differently under different seeds.
    r = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)")
    by_id = {tuple(search(dict(r, id=f"test-3-{n:04d}"), seed=1, paths=3, most_moves=1)[0]) for n in range(20)}
    by_seed = {tuple(search(r, seed=seed, paths=3, most_moves=1)[0]) for seed in range(20)}
    assert len(by_id) >= 2 and len(by_seed) >= 2
