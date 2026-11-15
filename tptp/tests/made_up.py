"""The made-up library of twelve files (tests/fixtures/made_up_library/), the stand-in prover's answers for it,
and the bins and figures worked out by hand. Used by test_count.py, test_report.py and test_end_to_end.py.

The answers use the real outputs saved in fixtures/endings.json. The axiom set of ALG004 (also BLG001-1, under
other names) derives 31 facts: F0..F29 below and G, the law m(X,Y)=m(Y,X). So:
- ALG004-1: its goal is G; once G is removed, all 30 facts F0..F29 are the options. F3 and F11 prove it.
- ALG004-3: 30 of the 31 facts are drawn; every option's call reaches the time cap.
- ALG004-4: its goal is F29; the options are F0..F28 and G. F5 proves it; F6's call reaches the time cap.
- BLG001-1: the same facts in its own symbols (n, u, j); no option's call proves its goal.
"""
import json

from conftest import FIXTURES

LIBRARY = FIXTURES / "made_up_library"

TERMS = ["e", "i(e)", "i(i(e))", "i(i(i(e)))", "i(i(i(i(e))))", "i(m(e,e))", "m(e,i(e))", "m(i(e),e)",
         "m(i(e),i(e))", "i(i(m(e,e)))", "m(e,i(i(e)))", "m(i(i(e)),e)", "i(m(e,i(e)))", "i(m(i(e),e))",
         "m(e,m(e,e))", "m(m(e,e),e)", "m(e,m(e,i(e)))", "m(m(e,i(e)),e)", "m(i(e),m(e,e))", "m(m(e,e),i(e))",
         "m(e,m(i(e),e))", "m(m(i(e),e),e)", "i(m(e,m(e,e)))", "i(m(m(e,e),e))", "m(i(i(e)),i(e))",
         "m(i(e),i(i(e)))", "i(i(i(m(e,e))))", "m(i(m(e,e)),e)", "m(e,i(m(e,e)))", "m(e,e)"]
FACTS = [f"m(X1,{t})=m({t},X1)" for t in TERMS]
G = "m(X1,X2)=m(X2,X1)"
K_FACTS = [f"{'k(' * n}X1{')' * n}=k(X1)" for n in range(3, 8)]

GOAL = {name: f"cnf(g,negated_conjecture,({text}))." for name, text in (
    ("ALG003-1", "p(a,p(q,b))!=p(a,b)"), ("ALG004-1", "m(a,b)!=m(b,a)"), ("ALG004-3", "m(a,m(b,a))!=m(a,b)"),
    ("ALG004-4", "m(a,m(e,e))!=m(m(e,e),a)"), ("ALG005-1", "s(s(s(s(a))))!=a"), ("ALG006-1", "t(a,b)!=b"),
    ("ALG007-1", "k(a)!=k(k(k(a)))"), ("BLG001-1", "n(a,j(a))!=u"))}


def _goal(name):
    return GOAL[name].replace("cnf(g,", "cnf(goal,")


def _option(fact):
    return f"cnf(option,axiom,({fact}))."   # the facts keep the variable names the prover printed


def _printed(facts):
    return "".join(f"cnf(c_0_{n}, plain, ({fact})).\n" for n, fact in enumerate(facts))


def table():
    """(texts that must all appear, output) pairs for the stand-in prover. The stand-in answers with the first
    row whose texts all appear, so the order of the rows matters: a row for one option's call comes before the
    row for the same goal with any option, and both before the row for the goal alone, which every call on that
    goal also matches."""
    real = {e["ending"]: e["output"] for e in json.loads((FIXTURES / "endings.json").read_text())}
    saturated = real["nothing left"]
    return [
        (["--print-saturated=eE", "(m(X,m(Y,Z))=m(m(X,Y),Z))"], _printed([G] + FACTS) + saturated),
        (["--print-saturated=eE", "(k(k(X))=k(X))"], _printed(K_FACTS) + saturated),
        (["--print-saturated=eE"], saturated),
        ([_goal("ALG004-1"), _option(FACTS[3])], real["proved"]),
        ([_goal("ALG004-1"), _option(FACTS[11])], real["proved"]),
        ([_goal("ALG004-4"), _option(FACTS[5])], real["proved"]),
        ([_goal("ALG004-4"), _option(FACTS[6])], real["time cap"]),
        ([_goal("ALG004-3"), "cnf(option,"], real["time cap"]),
        ([_goal("ALG003-1")], real["proved"]),
        ([_goal("ALG005-1")], real["term cap"]),
        ([_goal("ALG006-1")], real["nothing left"]),
        ([_goal("ALG004-1")], real["clause limit"]),
        ([_goal("ALG004-3")], real["clause limit"]),
        ([_goal("ALG004-4")], real["clause limit"]),
        ([_goal("ALG007-1")], real["clause limit"]),
        ([_goal("BLG001-1")], real["clause limit"]),
    ]


def proved_clauses():
    """The clauses processed in the saved proved output, which ALG003-1's unaided call is given."""
    from tptp_count.prover import counts
    real = {e["ending"]: e["output"] for e in json.loads((FIXTURES / "endings.json").read_text())}
    return counts(real["proved"])["processed"]


# The bins worked out by hand, in the library's order of names.
BINS = [
    ("Problems/ALG/ALG001-1.p", "left out: not usable", "statement a is not a single equation"),
    ("Problems/ALG/ALG002-1.p", "left out: status", "status Satisfiable"),
    ("Problems/ALG/ALG003-1.p", "proved unaided", None),
    ("Problems/ALG/ALG003-2.p", "left out: duplicate", "same problem as Problems/ALG/ALG003-1.p"),
    ("Problems/ALG/ALG004-1.p", "a problem", None),
    ("Problems/ALG/ALG004-3.p", "stopped for another reason", "option call 0: time cap and 29 more"),
    ("Problems/ALG/ALG004-4.p", "a problem", None),
    ("Problems/ALG/ALG005-1.p", "stopped for another reason", "unaided call: term cap"),
    ("Problems/ALG/ALG006-1.p", "stopped for another reason",
     "the prover says the goal does not follow, TPTP says it does"),
    ("Problems/ALG/ALG007-1.p", "left out: too few facts", "fewer than 30 derived facts"),
    ("Problems/ALG/ALG008-1.p", "left out: not usable", "goal is made of 2 statements"),
    ("Problems/BLG/BLG001-1.p", "no single fact helps", None),
]
COUNTS = {"left out: not usable": 2, "left out: status": 1, "left out: duplicate": 1, "left out: too few facts": 1,
          "proved unaided": 1, "no single fact helps": 1, "a problem": 2, "stopped for another reason": 3}
SHARES = {"proved unaided": 0.25, "no single fact helps": 0.25, "a problem": 0.5}
RIGHT_FACTS = {"ALG004-1": 2, "ALG004-4": 1}
UNDECIDED = 1   # problems with an option whose call did not decide: ALG004-4 (F6, time cap)
BY_AREA = {"ALG": {"proved unaided": 1, "no single fact helps": 0, "a problem": 2},
           "BLG": {"proved unaided": 0, "no single fact helps": 1, "a problem": 0}}


# A pair of counts in which ALG004's axiom set (also BLG001-1's) is unsettled: its fourth deriving run (S3 150
# LPO4) finishes in the first count and reaches the time cap in the second, so the first count has a usable list
# for it and the second none. So that every kind of file is on the set, ALG004-3's unaided call proves its goal and
# ALG004-4's ends on the term cap; ALG004-1 is "a problem" and BLG001-1 "no single fact helps" in the first count.
SET_1 = "Problems/ALG/ALG004-1.p"


def unsettled_table():
    real = {e["ending"]: e["output"] for e in json.loads((FIXTURES / "endings.json").read_text())}
    run_3 = ["--print-saturated=eE", "--processed-clauses-limit=150 ", "-tLPO4", "(m(X,m(Y,Z))=m(m(X,Y),Z))"]
    return [(run_3, {"first time": _printed([G] + FACTS) + real["nothing left"],
                     "after": _printed(FACTS[:5]) + real["time cap"]}),
            ([_goal("ALG004-3")], real["proved"]),
            ([_goal("ALG004-4")], real["term cap"])] + table()


UNSETTLED = "its axioms' facts were not the same in two counts"
UNSETTLED_BINS = [
    ("Problems/ALG/ALG001-1.p", "left out: not usable", "statement a is not a single equation"),
    ("Problems/ALG/ALG002-1.p", "left out: status", "status Satisfiable"),
    ("Problems/ALG/ALG003-1.p", "proved unaided", None),
    ("Problems/ALG/ALG003-2.p", "left out: duplicate", "same problem as Problems/ALG/ALG003-1.p"),
    ("Problems/ALG/ALG004-1.p", "stopped for another reason", UNSETTLED),
    ("Problems/ALG/ALG004-3.p", "proved unaided", None),
    ("Problems/ALG/ALG004-4.p", "stopped for another reason", "unaided call: term cap"),
    ("Problems/ALG/ALG005-1.p", "stopped for another reason", "unaided call: term cap"),
    ("Problems/ALG/ALG006-1.p", "stopped for another reason",
     "the prover says the goal does not follow, TPTP says it does"),
    ("Problems/ALG/ALG007-1.p", "left out: too few facts", "fewer than 30 derived facts"),
    ("Problems/ALG/ALG008-1.p", "left out: not usable", "goal is made of 2 statements"),
    ("Problems/BLG/BLG001-1.p", "stopped for another reason", UNSETTLED),
]
UNSETTLED_FILES = ["Problems/ALG/ALG004-1.p", "Problems/ALG/ALG004-3.p", "Problems/ALG/ALG004-4.p",
                   "Problems/BLG/BLG001-1.p"]
