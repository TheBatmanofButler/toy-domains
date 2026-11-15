"""Tests for bins.py: one hand-made case for every rule, in the specification's order, and the two cases
the order settles."""
import pytest

from tptp_count.bins import (A_PROBLEM, BINS, DUPLICATE, NO_FACT_HELPS, NOT_FOLLOWING, NO_FACTS, NOT_USABLE, PROVED_UNAIDED,
                             STATUS, STOPPED, TOO_FEW, BinError, bin_of)
from tptp_count.prover import CLAUSE_LIMIT, MEMORY_CAP_REACHED, NOTHING_LEFT, PROVED, TERM_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE

OPTIONS = list(range(30))
LIMIT_30 = [CLAUSE_LIMIT] * 30


def with_one(ending, at=7, rest=CLAUSE_LIMIT):
    endings = [rest] * 30
    endings[at] = ending
    return endings


def test_there_are_eight_bins():
    assert len(BINS) == len(set(BINS)) == 8


@pytest.mark.parametrize("arguments, expected", [
    # 1. left out, before any call is looked at
    (dict(usable="goal is made of 2 statements", status="Unsatisfiable"), (NOT_USABLE, "goal is made of 2 statements")),
    (dict(usable="no goal", status="Satisfiable", unaided=PROVED), (NOT_USABLE, "no goal")),
    (dict(usable=True, status="Satisfiable", unaided=PROVED), (STATUS, "status Satisfiable")),
    (dict(usable=True, status="Theorem", unaided=PROVED), (STATUS, "status Theorem")),      # a word for fof files
    (dict(usable=True, status="ContradictoryAxioms", unaided=PROVED), (STATUS, "status ContradictoryAxioms")),
    (dict(usable=True, status=""), (STATUS, "status missing")),
    (dict(usable=True, status="Unsatisfiable", duplicate_of="Problems/GRP/GRP001-1.p", unaided=PROVED),
     (DUPLICATE, "same problem as Problems/GRP/GRP001-1.p")),
    # 2. proved unaided, whatever the options would say
    (dict(usable=True, status="Unsatisfiable", unaided=PROVED), (PROVED_UNAIDED, None)),
    (dict(usable=True, status="Unsatisfiable", unaided=PROVED, options=None, no_facts="deriving run 1 (S4 150 KBO6): "
          "time cap"), (PROVED_UNAIDED, None)),
    # 3. the unaided call did not decide
    (dict(usable=True, status="Unsatisfiable", unaided=TERM_CAP_REACHED), (STOPPED, "unaided call: term cap")),
    (dict(usable=True, status="Unsatisfiable", unaided=MEMORY_CAP_REACHED), (STOPPED, "unaided call: memory cap")),
    (dict(usable=True, status="Unsatisfiable", unaided=TIME_CAP_REACHED, options=None),
     (STOPPED, "unaided call: time cap")),
    (dict(usable=True, status="Unsatisfiable", unaided=UNREADABLE), (STOPPED, "unaided call: unreadable")),
    (dict(usable=True, status="Unsatisfiable", unaided=TERM_CAP_REACHED, no_facts="deriving run 0 (S3 150 KBO6): "
          "memory cap"), (STOPPED, "unaided call: term cap")),
    # 3. the axiom set has no usable list of facts (a deriving run did not finish)
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, no_facts="deriving run 2 (S1 200 KBO6): time cap"),
     (STOPPED, NO_FACTS)),
    (dict(usable=True, status="Unsatisfiable", unaided=NOTHING_LEFT, no_facts="deriving run 4 (S1 120 LPO4): unreadable"),
     (STOPPED, NO_FACTS)),
    # 4. nothing left, although TPTP says the goal follows
    (dict(usable=True, status="Unsatisfiable", unaided=NOTHING_LEFT, options=None), (STOPPED, NOT_FOLLOWING)),
    # 5. too few facts
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=None), (TOO_FEW, "fewer than 30 derived facts")),
    # 6. a problem
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS, option_endings=with_one(PROVED)),
     (A_PROBLEM, None)),
    # 7. no single fact helps: every option's call decided, none proved
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS, option_endings=LIMIT_30),
     (NO_FACT_HELPS, None)),
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS,
          option_endings=with_one(NOTHING_LEFT)), (NO_FACT_HELPS, None)),
    # 8. otherwise
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS,
          option_endings=with_one(UNREADABLE, at=3)), (STOPPED, "option call 3: unreadable")),
    # the two cases the order settles
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS,
          option_endings=[PROVED, TIME_CAP_REACHED] + LIMIT_30[2:]),
     (A_PROBLEM, None)),
    (dict(usable=True, status="Unsatisfiable", unaided=CLAUSE_LIMIT, options=OPTIONS,
          option_endings=[TIME_CAP_REACHED] + LIMIT_30[1:]), (STOPPED, "option call 0: time cap")),
])
def test_every_rule(arguments, expected):
    assert bin_of(**arguments) == expected


NOT_DECIDING = [TERM_CAP_REACHED, MEMORY_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE]


@pytest.mark.parametrize("ending", NOT_DECIDING)
@pytest.mark.parametrize("proved_at, other_at", [(0, 1), (1, 0), (29, 0), (0, 29), (12, 5)])
def test_a_proved_option_counts_wherever_it_comes(ending, proved_at, other_at):
    """Before or after a call that did not decide, a proved option makes the file "a problem"."""
    endings = with_one(PROVED, at=proved_at)
    endings[other_at] = ending
    assert bin_of(True, "Unsatisfiable", None, CLAUSE_LIMIT, OPTIONS, endings) == (A_PROBLEM, None)


@pytest.mark.parametrize("ending", NOT_DECIDING)
@pytest.mark.parametrize("rest", [CLAUSE_LIMIT, NOTHING_LEFT])
def test_no_proved_option_and_one_that_did_not_decide_stops(ending, rest):
    assert bin_of(True, "Unsatisfiable", None, CLAUSE_LIMIT, OPTIONS, with_one(ending, at=11, rest=rest)) == \
        (STOPPED, f"option call 11: {ending}")


def test_more_than_one_call_that_did_not_decide_is_counted_in_the_reason():
    endings = with_one(TERM_CAP_REACHED, at=4)
    endings[9] = MEMORY_CAP_REACHED
    assert bin_of(True, "Unsatisfiable", None, CLAUSE_LIMIT, OPTIONS, endings) == \
        (STOPPED, "option call 4: term cap and 1 more")


def test_missing_calls_stop_loudly():
    with pytest.raises(BinError):
        bin_of(True, "Unsatisfiable", None, None)
    with pytest.raises(BinError):
        bin_of(True, "Unsatisfiable", None, CLAUSE_LIMIT, OPTIONS, LIMIT_30[:29])
