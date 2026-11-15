"""Tests for derived.py: the rules on hand-made equations, the order of the result with the stand-in prover,
and (slow) the facts of 20 of the earlier pilot's axiom sets before any topping-up."""
import pytest

from conftest import read_json
from tptp_count import derived
from tptp_count.equations import key_up_to_variables, read_equation, write_equation

E = read_equation
AXIOMS = [E("f(X,f(Y,Z))=f(f(X,Y),Z)"), E("f(e,X)=X")]
KEYS = {key_up_to_variables(a) for a in AXIOMS}


@pytest.mark.parametrize("text, kept", [
    ("f(X,f(Y,X))=f(Y,X)", True),
    ("f(X,Y)=f(Y,X)", True),                       # 5 symbols
    ("f(X,X)=X", False),                           # 4 symbols: too small
    ("f(f(f(f(X,Y),Z),U),f(f(X,Y),Z))=f(X,f(Y,Z))", False),   # 17 symbols: too big
    ("f(f(f(f(X,Y),Z),U),f(X,Y))=f(X,f(Y,Z))", True),          # 16 symbols
    ("f(X,f(Y,f(Z,U)))=f(V,X)", False),            # 5 variables
    ("f(X,f(Y,f(Z,U)))=f(U,X)", True),             # 4 variables
    ("f(f(A,B),C)=f(A,f(B,C))", False),            # an axiom, renamed and the other way round
    ("f(e,f(X,Y))=f(X,Y)", False),                 # an instance of an axiom
    ("f(X,f(e,Y))=f(X,Y)", True),                  # true, but not an instance of an axiom
    ("f(X,f(Y,Z))=f(X,f(Y,Z))", False),            # both sides the same
])
def test_the_rules_on_hand_made_equations(text, kept):
    assert derived.passes(E(text), AXIOMS, KEYS) is kept


def test_renamings_count_once_and_the_first_is_kept():
    first = [E("f(X,f(Y,X))=f(Y,X)"), E("f(A,B)=f(B,A)")]
    second = [E("f(B,A)=f(A,B)"), E("f(Y,X)=f(X,f(Y,X))"), E("f(X,f(e,Y))=f(X,Y)")]
    facts = derived.keep_facts(AXIOMS, [first, second])
    assert [write_equation(f) for f in facts] == ["f(X,f(Y,X))=f(Y,X)", "f(A,B)=f(B,A)", "f(X,f(e,Y))=f(X,Y)"]


def _run_output(lines, ending_lines):
    return "\n".join(lines) + "\n" + ending_lines


CLAUSE_LIMIT_AT = ("# Failure: User resource limit exceeded!\n# SZS status ResourceOut\n"
                   "# Processed clauses : {limit}\n# Termbank termtop insertions : 99\n")


def test_order_with_a_stand_in_prover(stand_in):
    """Each of the six runs prints its own list; the result is by run, then by printed order, as worked out by
    hand. The second run prints only an equation that is too small; the fourth saturates."""
    printed = {
        0: ["cnf(c1, plain, (f(X1,f(X2,X1))=f(X2,X1))).", "cnf(c2, plain, (f(X1,X1)=X1))."],
        1: ["cnf(c3, plain, (f(X1,e)=X1))."],
        2: ["cnf(c4, plain, (f(X1,f(e,X2))=f(X1,X2))).", "cnf(c5, plain, (f(X2,f(X1,X2))=f(X1,X2)))."],
        3: ["cnf(c6, plain, (f(X1,f(X2,X3))=f(X2,f(X1,X3))))."],
        4: [],
        5: ["cnf(c7, plain, (f(e,f(X1,X2))=f(X1,X2))).", "cnf(c8, plain, (f(X1,X2)=f(X2,X1)))."],
    }
    table = []
    for number, (heuristic, limit, ordering) in enumerate(derived.SETTINGS):
        if number == 3:
            ending = "# No proof found!\n# SZS status Satisfiable\n"
        else:
            ending = CLAUSE_LIMIT_AT.format(limit=limit)
        when = [f"--processed-clauses-limit={limit} ", f"-t{ordering}", derived.prover.HEURISTICS[heuristic] + "\n"]
        table.append((when, _run_output(printed[number], ending)))
    result = derived.derive_facts(AXIOMS, program=stand_in(table))
    assert [write_equation(f) for f in result["facts"]] == [
        "f(X1,f(X2,X1))=f(X2,X1)",          # run 1 (f(X1,X1)=X1 is too small, and so is run 2's)
        "f(X1,f(e,X2))=f(X1,X2)",           # run 3 (its second line is a renaming of run 1's first)
        "f(X1,f(X2,X3))=f(X2,f(X1,X3))",    # run 4
        "f(X1,X2)=f(X2,X1)"]                # run 6 (its first line is an instance of an axiom)
    assert result["printed"] == 8
    assert [r["ending"] for r in result["runs"]] == ["clause limit", "clause limit", "clause limit", "nothing left",
                                                     "clause limit", "clause limit"]
    assert [r["printed"] for r in result["runs"]] == [2, 1, 2, 1, 0, 2]
    assert len(result["outputs"]) == 6 and result["not_finished"] is None


@pytest.mark.parametrize("ending, stop", [
    ("time cap", "# Failure: Resource limit exceeded (time)\n# SZS status ResourceOut\n"),
    ("memory cap", "# Failure: Resource limit exceeded (memory)\n"),
    ("unreadable", "eprover: a stop the code has no words for\n"),
])
@pytest.mark.parametrize("at", [0, 1, 5])
def test_a_run_that_does_not_finish_leaves_no_usable_list(stand_in, ending, stop, at):
    """Every run prints a fact that passes; one of them does not finish. There is then no list at all, not a
    list without that run's facts."""
    table = []
    for number, (heuristic, limit, ordering) in enumerate(derived.SETTINGS):
        when = [f"--processed-clauses-limit={limit} ", f"-t{ordering}", derived.prover.HEURISTICS[heuristic] + "\n"]
        fact = f"cnf(c{number}, plain, (f(X1,f(X2,g{number}))=f(X2,X1)))."
        table.append((when, _run_output([fact], stop if number == at else CLAUSE_LIMIT_AT.format(limit=limit))))
    result = derived.derive_facts(AXIOMS, program=stand_in(table))
    heuristic, limit, ordering = derived.SETTINGS[at]
    assert result["facts"] is None
    assert result["not_finished"] == f"deriving run {at} ({heuristic} {limit} {ordering}): {ending}"
    assert [r["ending"] for r in result["runs"]][at] == ending and len(result["outputs"]) == 6


def test_more_than_one_run_that_does_not_finish_is_counted_in_the_reason(stand_in):
    result = derived.derive_facts(AXIOMS, program=stand_in([]))     # every output unreadable
    assert result["facts"] is None and result["not_finished"] == "deriving run 0 (S3 150 KBO6): unreadable and 5 more"


# Of the 20 pilot axiom sets, one (LDA) has a deriving run that reaches the 60-second cap on computing time: the
# fourth, S3 150 LPO4. So it has no usable list of facts; the pilot, which passed over such runs, kept the 2
# facts of the other runs. Its first run, S3 150 KBO6, needs about 58 seconds of computing time on the machine
# where this was measured, so whether it too is cut off depends on the machine's speed and load; the other four
# runs finish in seconds. A run that sits at the time cap like this finishes on some runs and not on others; the
# axiom set has no usable list of facts either way.
NOT_FINISHING = {"48058c83185bb7f27549": {"cut off": [3], "at the cap": [0]}}


@pytest.mark.slow
def test_facts_of_20_pilot_axiom_sets_equal_the_pilots(real_prover):
    rows = read_json("pilot_derived.json")
    assert len(rows) == 20
    differences = []
    for row in rows:
        found = derived.derive_facts([E(a) for a in row["axioms"]], program=real_prover)
        if row["theory"] in NOT_FINISHING:
            expected = NOT_FINISHING[row["theory"]]
            endings = [run["ending"] for run in found["runs"]]
            cut_off = [n for n, ending in enumerate(endings) if ending in derived.NOT_FINISHED]
            if (found["facts"] is not None or any(endings[n] != "time cap" for n in cut_off)
                    or not set(expected["cut off"]) <= set(cut_off) <= set(expected["cut off"] + expected["at the cap"])):
                differences.append(f"{row['theory']}: runs ended {endings}, expected {expected}")
            continue
        ours = [key_up_to_variables(f) for f in found["facts"] or []]
        pilots = [key_up_to_variables(E(f)) for f in row["pilot_facts"]]
        if found["facts"] is None or ours != pilots:
            differences.append(f"{row['theory']}: {found['not_finished'] or len(ours)} facts, the pilot's {len(pilots)}")
    assert not differences, "\n".join(differences)
