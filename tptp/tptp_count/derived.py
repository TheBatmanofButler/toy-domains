"""The derived facts of an axiom set: equations the prover derives from the axioms alone, without the goal,
that are of moderate size and say something the axioms do not already say word for word.

The prover is run six times, with the earlier pilot's six settings, each asked to print the clauses it holds
when it stops. The facts are kept in a fixed order: by deriving run, then in the order the prover printed them.
If any of the six runs does not finish, the axiom set has no usable list of facts.
"""
from tptp_count import prover
from tptp_count.equations import is_instance, key_up_to_variables, size, variables

# The earlier pilot's six deriving runs: (way of choosing the next clause, processed-clause limit, ordering).
SETTINGS = (
    ("S3", 150, "KBO6"),
    ("S4", 150, "KBO6"),
    ("S1", 200, "KBO6"),
    ("S3", 150, "LPO4"),
    ("S1", 120, "LPO4"),
    ("S2", 200, "KBO6"),
)
# How the earlier pilot read a run's printout, kept so that the facts are the pilot's: clause lines longer than
# 220 characters are passed over, and only the first 1,500 remaining clause lines are read. So the derived facts
# are, by definition, those found in that part of the printout, not every clause the prover holds when it stops:
# a run can print hundreds of thousands of clauses, and a longer or shorter cut would give other facts.
MAX_LINE_LENGTH = 220
MAX_LINES = 1500

MIN_SIZE, MAX_SIZE, MAX_VARIABLES = 5, 16, 4

# A run that stopped on one of these did not finish: on the time cap or the memory cap, what it printed would
# depend on the machine's speed or memory, and an unreadable output cannot be trusted. Then the axiom set has no
# usable list of facts at all, rather than a list short of that run's facts.
NOT_FINISHED = (prover.TIME_CAP_REACHED, prover.MEMORY_CAP_REACHED, prover.UNREADABLE)


def passes(equation, axioms, axiom_keys):
    """The rules for a derived fact, apart from 'counts once'."""
    return (MIN_SIZE <= size(equation) <= MAX_SIZE and len(variables(equation)) <= MAX_VARIABLES
            and equation[0] != equation[1] and key_up_to_variables(equation) not in axiom_keys
            and not any(is_instance(equation, axiom) for axiom in axioms))


def keep_facts(axioms, printed_by_run):
    """From each run's printed equations (runs in SETTINGS order), the facts that pass, each renaming of one
    counted once (the first met is kept)."""
    axiom_keys = {key_up_to_variables(axiom) for axiom in axioms}
    facts, seen = [], set()
    for printed in printed_by_run:
        for equation in printed:
            found = key_up_to_variables(equation)
            if found not in seen and passes(equation, axioms, axiom_keys):
                seen.add(found)
                facts.append(equation)
    return facts


def derive_facts(axioms, *, program):
    """-> {"facts": [...], or None if the axiom set has no usable list of facts, "not_finished": None, or why
    there is no usable list, "printed": clause lines printed by the runs that finished, "runs": [{setting,
    ending, printed}], "outputs": each run's printout without its clause lines}. For a run that did not finish
    only its setting and ending are given (its output is None): what it had printed when it was cut off depends
    on timing, and two runs of the count must write the same files."""
    printed_by_run, runs, outputs, printed_count, not_finished = [], [], [], 0, []
    for number, (heuristic, limit, ordering) in enumerate(SETTINGS):
        run = prover.derive(axioms, heuristic, limit, ordering, MAX_LINE_LENGTH, MAX_LINES, program=program)
        setting = [heuristic, limit, ordering]
        if run["ending"] in NOT_FINISHED:
            not_finished.append(f"deriving run {number} ({heuristic} {limit} {ordering}): {run['ending']}")
            runs.append({"setting": setting, "ending": run["ending"]})
            outputs.append(None)
            continue
        printed_by_run.append(prover.printed_equations(run["clauses"]))
        printed_count += run["printed"]
        runs.append({"setting": setting, "ending": run["ending"], "printed": run["printed"]})
        outputs.append(run["output"])
    if not_finished:
        reason = not_finished[0] + (f" and {len(not_finished) - 1} more" if len(not_finished) > 1 else "")
        return {"facts": None, "not_finished": reason, "printed": printed_count, "runs": runs, "outputs": outputs}
    return {"facts": keep_facts(axioms, printed_by_run), "not_finished": None, "printed": printed_count,
            "runs": runs, "outputs": outputs}
