"""Tests of programs/common.py: picks, ranks, the guard on training, and every count a program takes from the
library. Counts leave out the test set's theorems only: on a hand-made case first, then on the made-up library
(tests/test_problems.py describes it) with the test set t3_xboole_0 and t4_xboole_0; the other five theorems of
xboole_0 and xboole_1 are counted.

Positions in the made-up library: d1_basic_0 0, d2 1, the other fact 2, t1_basic_0 3 ... t10 12, l1 13, t11 14 ...
t20 23, l2 24, t21 25 ... t34 38, d1_xboole_0 39, t1_xboole_0 40 ... t5_xboole_0 44, t1_xboole_1 45 ... t5 49,
t1_later_0 50, t2_later_0 51, t3_later_0 52. 53 facts; the 2 test theorems are left out: 51.
"""
import math

import pytest

from mizar_ladder.programs.common import Counts, check_training_problems, pick_best, pick_on, ranks


def test_picks():
    assert pick_on([3]) == [0.0] * 2 + [1.0] + [0.0] * 27
    assert pick_on([1, 30, 30]) == [0.5] + [0.0] * 28 + [0.5]
    for bad in ([], [0], [31]):
        with pytest.raises(ValueError):
            pick_on(bad)
    values = [0.0] * 30
    values[4] = values[9] = 2.0
    values[9] -= 1e-12                                     # within the tolerance: tied
    assert pick_best(values) == pick_on([5, 10])


def test_ranks():
    assert ranks([3, 1, 3, 2]) == [1, 4, 1, 3]
    assert ranks([5.0]) == [1]


def test_the_guard_on_training():
    # Training problems of the articles the test problems come from are fine; a test problem's theorem is refused under any id.
    test_theorems = {"t3_xboole_0", "t4_xboole_0"}
    fine = [{"id": "train-0001", "theorem": "t1_xboole_1", "article": "xboole_1"},
            {"id": "train-0002", "theorem": "t5_xboole_0", "article": "xboole_0"}]
    check_training_problems(fine, test_theorems)
    with pytest.raises(ValueError, match="only training problems"):
        check_training_problems([dict(fine[0], id="test-0001")], test_theorems)
    with pytest.raises(ValueError, match="train-0002: t4_xboole_0 is a test problem's theorem"):
        check_training_problems([fine[0], dict(fine[1], theorem="t4_xboole_0")], test_theorems)


def test_each_count_leaves_out_the_test_set_only():
    # t1_aa is cited, with the given fact t2_aa, by a test theorem (t1_xboole_1), by a theorem of the same article
    # that was not drawn (t2_xboole_1) and by a theorem of another article (t1_bb); k9_s is in those three
    # theorems only. Each count is 2. Six facts, one left out: 5.
    facts = [("t1_aa", "k1_s(A)"), ("t2_aa", "k2_s(A)"), ("t3_aa", "p(A)"), ("t1_xboole_1", "k9_s(A)"),
             ("t2_xboole_1", "k9_s(A)"), ("t1_bb", "k9_s(A)")]
    references = {t: ["t1_aa", "t2_aa"] for t in ("t1_xboole_1", "t2_xboole_1", "t1_bb")}
    counts = Counts(facts, references, left_out={"t1_xboole_1"})
    assert counts.citations("t1_aa") == 2
    assert counts.cited_with("t1_aa", ["t2_aa"]) == 2
    assert counts.facts_with["k9_s"] == 2 and counts.fact_total == 5
    assert counts.symbol_weight("k9_s") == pytest.approx(math.log(5 / 2))
    # A training problem's own theorem is left out of its own counts too.
    assert counts.citations("t1_aa", own="t1_bb") == 1 and counts.cited_with("t1_aa", ["t2_aa"], own="t1_bb") == 1
    assert counts.symbol_weight("k9_s", own="t1_bb") == pytest.approx(math.log(4 / 1))


@pytest.fixture(scope="module")
def counts(made_up):
    # The test set as stage 1 would give it: only the theorems' names are read.
    return Counts.for_test_set(made_up, [{"id": "test-0001", "theorem": "t3_xboole_0"},
                                         {"id": "test-0002", "theorem": "t4_xboole_0"}])


def test_the_test_set_is_an_input(made_up, counts):
    assert counts.left_out == {"t3_xboole_0", "t4_xboole_0"}
    other = Counts.for_test_set(made_up, [{"id": "test-0001", "theorem": "t2_xboole_1"}])
    # t1_xboole_1 is cited by t2_xboole_1, t2_later_0 and t3_later_0.
    assert counts.citations("t1_xboole_1") == 3 and other.citations("t1_xboole_1") == 2


def test_citation_counts_leave_out_the_test_theorems_and_the_own_theorem(counts):
    # t5_basic_0 is cited by t6_basic_0, t4_xboole_0 (a test theorem) and t1_later_0.
    assert counts.citations("t5_basic_0") == 2
    assert counts.citations("t5_basic_0", own="t1_later_0") == 1
    # t1_xboole_1 is cited by t2_xboole_1 (of one of the articles, not drawn: counted), t2_later_0 and t3_later_0.
    assert counts.citations("t1_xboole_1") == 3 and counts.citations("t1_xboole_1", own="t3_later_0") == 2
    # t10_basic_0 is cited by t11_basic_0 and t3_xboole_0 (a test theorem); a test problem's own theorem is
    # already left out, so naming it changes nothing.
    assert counts.citations("t10_basic_0") == 1 == counts.citations("t10_basic_0", own="t3_xboole_0")
    assert counts.citations("t3_later_0") == 0


def test_cited_together_with_a_given_fact(counts):
    # t3_xboole_0 is cited by t1_xboole_1 (counted) and t3_later_0; t1_xboole_1 by t2_xboole_1, t2_later_0 and
    # t3_later_0: together, t3_later_0.
    assert counts.cited_with("t3_xboole_0", ["t1_xboole_1"]) == 1
    assert counts.cited_with("t3_xboole_0", ["t1_xboole_1"], own="t3_later_0") == 0
    # t4_xboole_0 is cited by t1_xboole_1, so with both given: t1_xboole_1 and t3_later_0.
    assert counts.cited_with("t3_xboole_0", ["t4_xboole_0", "t1_xboole_1"]) == 2
    assert counts.cited_with("t3_xboole_0", []) == 0
    # t5_basic_0 with d1_xboole_0: t1_later_0 (t4_xboole_0 cites t5 but is left out; t3_xboole_0 cites
    # d1_xboole_0 but is left out).
    assert counts.cited_with("t5_basic_0", ["d1_xboole_0"]) == 1


def test_symbol_weights_over_the_facts_not_left_out(counts):
    assert counts.fact_total == 51
    # k1_basic_0 is in d1_basic_0 and t1 to t34: 35 facts.
    assert counts.symbol_weight("k1_basic_0") == pytest.approx(math.log(51 / 35))
    # k3_xboole_0: in t2_xboole_0, t3_xboole_0 (left out), t2_later_0 and t3_later_0: 3.
    assert counts.symbol_weight("k3_xboole_0") == pytest.approx(math.log(51 / 3))
    # A training problem's own theorem is left out too: 50 facts, 2 with k3_xboole_0.
    assert counts.symbol_weight("k3_xboole_0", own="t2_later_0") == pytest.approx(math.log(50 / 2))
    # k2_xboole_0: t1_xboole_0, t1_xboole_1, t3_xboole_1 and t1_later_0 (t3_xboole_0 is left out).
    assert counts.symbol_weight("k2_xboole_0") == pytest.approx(math.log(51 / 4))
    assert counts.symbol_weight("k2_xboole_0", own="t1_later_0") == pytest.approx(math.log(50 / 3))
    # r1_xboole_0 is only in t4_xboole_0, left out: weighed as if in one fact.
    assert counts.symbol_weight("r1_xboole_0") == pytest.approx(math.log(51))
    # t3_later_0 shares k3_xboole_0 with t2_later_0, and nothing with t1_later_0.
    assert counts.shared_sum("t3_later_0", ["t2_later_0"]) == pytest.approx(math.log(17))
    assert counts.shared_sum("t3_later_0", ["t1_later_0", "t2_later_0"]) == pytest.approx(math.log(17))
    assert counts.shared_sum("t3_later_0", ["t1_later_0"]) == 0 and counts.shared_sum("t3_later_0", []) == 0


def test_places_in_the_library(counts):
    assert counts.from_article_start("t1_basic_0") == 3 and counts.from_article_start("l2_basic_0") == 24
    assert counts.from_article_start("t3_xboole_0") == 3 and counts.from_article_start("t1_later_0") == 0
    assert counts.between("t1_basic_0", "t2_basic_0") == 0 and counts.between("t34_basic_0", "t3_xboole_0") == 3
