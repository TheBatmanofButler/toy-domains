"""Tests of surface_symbols.py on the hand library of made_up_programs.py. The theorem t1_bb has r1_x, k1_y and
k9_z. Of the 33 counted facts (34 less t1_cc), r1_x is in t2_aa, t6_aa, t8_aa and t1_bb (4), k1_y in t4_aa, t6_aa,
t8_aa and t1_bb (4), k9_z in the other 26 options and t1_bb, t2_bb, t3_bb (29). So t6_aa and t8_aa (both rare
symbols) tie at 2 log(33/4); t2_aa and t4_aa have log(33/4); the rest log(33/29)."""
import math

import pytest
from made_up_programs import OPTIONS, hand_library, problem

from mizar_ladder.programs import surface_symbols
from mizar_ladder.programs.common import pick_on


def test_surface_symbols_worked_by_hand_including_a_tie():
    counts = hand_library()
    assert counts.shared_sum("t6_aa", ["t1_bb"]) == pytest.approx(2 * math.log(33 / 4))
    assert counts.shared_sum("t2_aa", ["t1_bb"]) == pytest.approx(math.log(33 / 4))
    assert counts.shared_sum("t9_aa", ["t1_bb"]) == pytest.approx(math.log(33 / 29))
    # A test problem of t1_bb (left out, say): the tie between t6_aa and t8_aa.
    counts.left_out.add("t1_bb")
    assert surface_symbols.picks([problem("test-1", "t1_bb", OPTIONS, 6)], counts) == [pick_on([6, 8])]
    # Without t6_aa and t8_aa among the options, t2_aa and t4_aa tie.
    options = [o for o in OPTIONS if o not in ("t6_aa", "t8_aa")] + ["t31_aa", "t32_aa"]
    counts.symbols.update({"t31_aa": {"k9_z"}, "t32_aa": {"k9_z"}})
    assert surface_symbols.picks([problem("test-2", "t1_bb", options, 2)], counts) == [pick_on([2, 4])]
