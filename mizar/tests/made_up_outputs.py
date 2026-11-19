"""Made-up prover outputs in the shape of E 2.6's real ones on these problems (tests/fixtures/endings.json.gz
holds the real ones), for the stand-in prover: each carries the lines its ending rests on and the counts."""
from mizar_ladder.prover import CLAUSE_LIMIT, NOTHING_LEFT, PROVED, TERM_CAP_REACHED, TIME_CAP_REACHED

HEAD = "# No SInE strategy applied\n# Auto-Mode selected heuristic G_E___208_C18_F1_SE_CS_SP_PS_S5PRR_S2mI\n"


def statistics(processed, generated, terms):
    return (f"# Removed by relevancy pruning/SinE    : 0\n# Processed clauses                    : {processed}\n"
            f"# Generated clauses                    : {generated}\n"
            f"# Termbank termtop insertions          : {terms}\n")


def output(ending, used=(), processed=None, generated=50, terms=1000):
    """An output that ends as `ending`; for a proof, `used` are the library facts in it. Processed clauses are
    100 unless given, or, at the clause limit, 70,000: past every limit tried."""
    processed = processed if processed is not None else 70000 if ending == CLAUSE_LIMIT else 100
    if ending == PROVED:
        proof = "".join(f"fof({name}, axiom, p({name}), file('/tmp/tmpabc.p', {name})).\n" for name in used)
        return (HEAD + "# Proof found!\n# SZS status Theorem\n# SZS output start CNFRefutation\n" + proof
                + "fof(c_0_1, negated_conjecture, ~q, inference(assume_negation,[status(cth)],[t])).\n"
                + "# SZS output end CNFRefutation\n" + statistics(processed, generated, terms))
    if ending == NOTHING_LEFT:
        return HEAD + "# No proof found!\n# SZS status CounterSatisfiable\n" + statistics(processed, generated, terms)
    if ending in (CLAUSE_LIMIT, TERM_CAP_REACHED):
        return (HEAD + "# Failure: User resource limit exceeded!\n# SZS status ResourceOut\n"
                + statistics(processed, generated, 1_000_000 if ending == TERM_CAP_REACHED else terms))
    if ending == TIME_CAP_REACHED:
        return "# Failure: Resource limit exceeded (time)\n# SZS status ResourceOut\n" + HEAD
    return "eprover: Type error\n"
