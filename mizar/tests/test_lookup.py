"""Tests of lookup.py, worked by hand. Training problems (the held-back fact of each): train-1 t3_aa, train-2
t3_aa, train-3 t5_aa, train-4 t5_aa, train-5 t7_aa, train-6 t40_zz (not an option of any test problem below).
So t3_aa and t5_aa were each held back twice, t7_aa once, every other option never. Every training problem also
has given facts, t9_aa and t11_aa among them (options of the test problems below): given facts are not held back
and are not counted."""
import pytest
from made_up_programs import OPTIONS, hand_library, problem

from mizar_ladder.programs import lookup
from mizar_ladder.programs.common import pick_on

OTHERS = [f"t{n}_zz" for n in range(31, 61)]


@pytest.fixture
def trained():
    held = ["t3_aa", "t3_aa", "t5_aa", "t5_aa", "t7_aa"]
    given = ["t9_aa", "t11_aa", "d1_bb"]
    train = [problem(f"train-{n}", f"t{n}_bb", OPTIONS, OPTIONS.index(name) + 1, given=given)
             for n, name in enumerate(held, 1)]
    train.append(problem("train-6", "t6_bb", OTHERS[9:] + OTHERS[:9], 1, given=given))       # held back: t40_zz
    return lookup.train(train, hand_library())


def test_the_counts_it_is_given(trained):
    assert trained == {"t3_aa": 2, "t5_aa": 2, "t7_aa": 1, "t40_zz": 1}


def test_lookup_worked_by_hand_including_a_tie(trained):
    # t3_aa and t5_aa tie at 2 and share the weight (t9_aa and t11_aa, given six times each, count for nothing).
    assert lookup.picks([problem("test-1", "t2_cc", OPTIONS, 9)], trained) == [pick_on([3, 5])]
    # Without t3_aa and t5_aa among the options, t7_aa (once) is the pick; the order shown is followed.
    options = ["t31_zz", "t32_zz"] + [o for o in OPTIONS if o not in ("t3_aa", "t5_aa")]
    assert lookup.picks([problem("test-2", "t2_cc", options, 1)], trained) == [pick_on([7])]
    # t40_zz, held back once, beats options never held back.
    assert lookup.picks([problem("test-3", "t2_cc", OTHERS, 1)], trained) == [pick_on([10])]


def test_no_information_gives_equal_weight(trained):
    never = [f"t{n}_yy" for n in range(1, 31)]
    assert lookup.picks([problem("test-4", "t2_cc", never, 4)], trained) == [[1 / 30] * 30]
    # Options that were only ever given facts in training: still no information.
    given_only = ["t9_aa", "t11_aa"] + never[:28]
    assert lookup.picks([problem("test-5", "t2_cc", given_only, 4)], trained) == [[1 / 30] * 30]


def test_it_refuses_a_test_theorem_in_training():
    counts = hand_library()                     # t1_cc is the left-out (test) theorem
    with pytest.raises(ValueError, match="t1_cc is a test problem's theorem"):
        lookup.train([problem("train-1", "t1_cc", OPTIONS, 1)], counts)
