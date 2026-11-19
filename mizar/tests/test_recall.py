"""Tests of recall.py on the hand library of made_up_programs.py: t3_aa and t5_aa are each cited twice (by t1_bb
and t2_bb, and by t1_bb and t3_bb), t7_aa once (t2_bb; t1_cc is left out), every other option never."""
from made_up_programs import OPTIONS, hand_library, problem

from mizar_ladder.programs import recall
from mizar_ladder.programs.common import pick_on


def test_recall_worked_by_hand_including_a_tie():
    counts = hand_library()
    # A problem of another theorem: t3_aa and t5_aa tie at 2.
    assert recall.picks([problem("test-1", "t2_cc", OPTIONS, 3)], counts) == [pick_on([3, 5])]
    # The problem of t1_bb leaves its own citations out: t3_aa, t5_aa and t7_aa all have 1.
    assert recall.picks([problem("train-1", "t1_bb", OPTIONS, 3)], counts) == [pick_on([3, 5, 7])]
    # Of t3_bb: t3_aa 2, t5_aa 1.
    assert recall.picks([problem("train-2", "t3_bb", OPTIONS, 5)], counts) == [pick_on([3])]
    # Options in another order: the pick follows the options' order.
    assert recall.picks([problem("test-2", "t2_cc", OPTIONS[::-1], 1)], counts) == [pick_on([28, 26])]


def test_left_out_citations_do_not_count():
    # t7_aa is cited by t2_bb and by t1_cc, which is left out: 1, below t3_aa and t5_aa.
    counts = hand_library()
    assert counts.citations("t7_aa") == 1
    options = ["t7_aa"] + [o for o in OPTIONS if o not in ("t3_aa", "t5_aa", "t7_aa")] + ["t31_aa", "t32_aa"]
    counts.statement.update({"t31_aa": "k9_z(A)=A", "t32_aa": "k9_z(A)=A"})
    assert recall.picks([problem("test-3", "t2_cc", options, 1)], counts) == [pick_on([1])]
