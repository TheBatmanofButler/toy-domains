"""Stand-in prover tables for the made-up library's problems (tests/test_problems.py describes the library).

`table(scenario)` turns {theorem: {limit: (ending without an option, {option fact: (ending, uses the option)})}}
into the stand-in prover's rows: a call is recognised by its theorem's conjecture line, its limit, and the line
of the option fact it adds, if any. An ending may be ("first time", first, after): the first run of a set of
calls gets the first ending, every later one the other, as a call at the time cap can differ between runs. A call
no row fits is answered with nothing, which reads as unreadable.
"""
from made_up_outputs import output


def _with(theorem, limit):
    return [f"fof({theorem}, conjecture,", f"--processed-clauses-limit={limit} "]


def _answer(ending, used):
    if isinstance(ending, tuple):
        return {"first time": output(ending[1], used), "after": output(ending[2], used)}
    return output(ending, used)


def table(scenario):
    rows = []
    for theorem, limits in scenario.items():
        for limit, (without, options) in limits.items():
            for fact, (ending, uses) in options.items():
                used = [fact, "d1_basic_0"] if uses else ["d1_basic_0"]
                rows.append((_with(theorem, limit) + [f"fof({fact}, axiom,"], _answer(ending, used)))
            rows.append((_with(theorem, limit), _answer(without, ["d1_basic_0"])))
    return rows
