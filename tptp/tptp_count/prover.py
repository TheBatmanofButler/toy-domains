"""The one place that knows the prover, E 2.6: its command line, the text it is given, how to run it, and how
to read from its output how a call ended and what it counted.

Where the prover is installed is not written here: every function that runs it is given `program`, the path
of a command that starts it.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from tptp_count.equations import EquationError, read_equation, write_term

VERSION = "E 2.6 Floral Guranse (8e8bfa2a3f682a4a7d96975eaa7b1133c4267b13)"

LIMIT = 160              # processed clauses
TERM_CAP = 1_000_000     # term bank insertions, a cap that does not depend on the machine
MEMORY_CAP_MB = 2000
TIME_CAP_SECONDS = 60    # computing time; the only time limit anywhere, and a call that reaches it says so

# The fixed search setting of the earlier pilot: ordering KBO, no literal selection, clauses taken in turn by
# age (first in, first out) and by size.
SEARCH = ["-tKBO6", "-WNoSelection", "-H(1*FIFOWeight(ConstPrio),1*Clauseweight(ConstPrio,1,1,1))"]

# The other ways of choosing the next clause that the deriving runs use (derived.py), by the earlier pilot's names.
HEURISTICS = {
    "S1": SEARCH[2],
    "S2": "-H(1*Clauseweight(ConstPrio,1,1,1))",
    "S3": "-H(1*FIFOWeight(ConstPrio))",
    "S4": "-H(1*FIFOWeight(ConstPrio),4*ConjectureRelativeSymbolWeight(ConstPrio,0.1,100,100,100,100,1.5,1.5,1.5))",
}


def command(limit=LIMIT):
    """The pinned command line, with `limit` as the processed-clause limit. The input file's name is put after it."""
    return ["--print-statistics", "--silent", f"--cpu-limit={TIME_CAP_SECONDS}", f"--processed-clauses-limit={limit}",
            f"--tb-insert-limit={TERM_CAP}", f"--memory-limit={MEMORY_CAP_MB}", *SEARCH]


COMMAND = command(LIMIT)

# The one environment every prover process is started with; nothing from the caller's environment reaches it.
# E 2.6's search depends on the C library's memory settings: with MALLOC_MMAP_THRESHOLD_, MALLOC_TOP_PAD_ or
# GLIBC_TUNABLES set, the same input gives other clause counts, other derived facts and, on a few borderline
# calls, another ending. With this environment the prover gives the earlier pilot's outcomes and counts exactly.
# PATH is fixed (not the caller's) because a start script needs it to find its own tools; LC_ALL fixes the locale.
ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}

PROVED, CLAUSE_LIMIT, NOTHING_LEFT = "proved", "clause limit", "nothing left"
TERM_CAP_REACHED, MEMORY_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE = "term cap", "memory cap", "time cap", "unreadable"
ENDINGS = (PROVED, CLAUSE_LIMIT, NOTHING_LEFT, TERM_CAP_REACHED, MEMORY_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE)
DECIDING = (PROVED, CLAUSE_LIMIT, NOTHING_LEFT)

# How a call ended, read from the output. Each ending rests on these exact lines of E 2.6's output (seen in
# real outputs, kept in tests/fixtures/endings.json):
#   proved:        "# Proof found!" and "# SZS status Unsatisfiable"
#   clause limit:  "# Failure: User resource limit exceeded!" and "# SZS status ResourceOut", with
#                  "# Processed clauses : N" where N is the limit and "# Termbank termtop insertions : M" under the cap
#   nothing left:  "# No proof found!" and "# SZS status Satisfiable"
#   term cap:      "# Failure: User resource limit exceeded!" and "# SZS status ResourceOut", with
#                  "# Termbank termtop insertions : M" where M is at least the cap (E prints the same failure line
#                  for both of its user limits, so the counts tell them apart)
#   memory cap:    "# Failure: Resource limit exceeded (memory)"
#   time cap:      "# Failure: Resource limit exceeded (time)"
#   unreadable:    none of the above, or more than one
_COUNTS = {
    "processed": re.compile(r"^# Processed clauses\s*:\s*(\d+)\s*$", re.M),
    "generated": re.compile(r"^# Generated clauses\s*:\s*(\d+)\s*$", re.M),
    "terms": re.compile(r"^# Termbank termtop insertions\s*:\s*(\d+)\s*$", re.M),
}
_UNPROCESSED = re.compile(r"^# Current number of unprocessed clauses\s*:\s*(\d+)\s*$", re.M)

# Lines in which E reports the time or memory it used ("# User time : 0.005 s", "# Maximum resident set size:
# 123916 pages", "#    Propositional solver time : 0.000"). They differ from one run to the next, so they are
# taken out of every output before it is read or kept; no ending or count rests on them.
_USAGE = re.compile(r"^#[^:\n]*(?:\btime|resident set size)\s*:[^\n]*\n?", re.M)


def without_usage(output):
    return _USAGE.sub("", output)


class ProverError(RuntimeError):
    pass


def counts(output):
    """Clauses processed, clauses generated and terms built (term bank insertions); None where not printed."""
    found = {}
    for name, pattern in _COUNTS.items():
        values = pattern.findall(output)
        found[name] = int(values[0]) if len(values) == 1 else None
    return found


def unprocessed(output):
    """The clauses left unprocessed when the prover stopped; None where not printed exactly once."""
    values = _UNPROCESSED.findall(output)
    return int(values[0]) if len(values) == 1 else None


def how_it_ended(output, limit=LIMIT, term_cap=TERM_CAP):
    """One of ENDINGS. `limit` is the processed-clause limit the call was given; `term_cap` None for a run
    given no term cap (the deriving runs)."""
    lines = {line.strip() for line in output.splitlines()}
    numbers = counts(output)
    endings = []
    if "# Proof found!" in lines and "# SZS status Unsatisfiable" in lines:
        endings.append(PROVED)
    if "# No proof found!" in lines and "# SZS status Satisfiable" in lines:
        endings.append(NOTHING_LEFT)
    if "# Failure: Resource limit exceeded (memory)" in lines:
        endings.append(MEMORY_CAP_REACHED)
    if "# Failure: Resource limit exceeded (time)" in lines:
        endings.append(TIME_CAP_REACHED)
    if "# Failure: User resource limit exceeded!" in lines and "# SZS status ResourceOut" in lines:
        terms, processed = numbers["terms"], numbers["processed"]
        if terms is not None and term_cap is not None and terms >= term_cap:
            endings.append(TERM_CAP_REACHED)   # even if the clause limit was reached too: never "does not prove"
        elif terms is not None and processed == limit:
            endings.append(CLAUSE_LIMIT)
    return endings[0] if len(endings) == 1 else UNREADABLE


def input_text(axioms, option, goal):
    """The axioms in the file's order, then the option if there is one, then the goal, denied. Nothing else.
    With goal None (the deriving runs), the axioms alone."""
    def clause(name, role, equation, sign="="):
        return f"cnf({name},{role},({write_term(equation[0])}{sign}{write_term(equation[1])}))."
    lines = [clause(f"ax{i}", "axiom", axiom) for i, axiom in enumerate(axioms)]
    if option is not None:
        lines.append(clause("option", "axiom", option))
    if goal is not None:
        lines.append(clause("goal", "negated_conjecture", goal, "!="))
    return "\n".join(lines) + "\n"


@contextmanager
def _input_file(text):
    """The input, in a file of its own. As in the earlier pilot the prover reads a file: given the same text
    on standard input, E 2.6 prints its clauses in another order (the search itself was seen to be the same)."""
    handle, path = tempfile.mkstemp(suffix=".p")
    try:
        with os.fdopen(handle, "w") as f:
            f.write(text)
        yield path
    finally:
        os.unlink(path)


def _run(program, arguments, text=None):
    """Runs the prover in ENVIRONMENT; the output is both of its streams, standard output first (E prints some
    of its stops, such as running out of memory, on the error stream), without the lines on time and memory
    used."""
    if text is None:
        done = subprocess.run([program, *arguments], capture_output=True, text=True, env=ENVIRONMENT)
        return without_usage(done.stdout + done.stderr), done.returncode
    with _input_file(text) as path:
        done = subprocess.run([program, *arguments, path], capture_output=True, text=True, env=ENVIRONMENT)
    return without_usage(done.stdout + done.stderr), done.returncode


def program_checksum(program):
    """sha256 of the file that starts the prover, found as the prover's own start would find it. When that file
    is a start script, the prover program behind it is given separately and checked with this too."""
    found = shutil.which(program, path=ENVIRONMENT["PATH"])
    if found is None:
        raise ProverError(f"the prover's command {program!r} is not a program that can be started")
    return hashlib.sha256(Path(found).read_bytes()).hexdigest()


def check_version(program):
    output, _ = _run(program, ["--version"])
    if output.strip() != VERSION:
        raise ProverError(f"the prover reports {output.strip()!r}, not the pinned {VERSION!r}")


def call(axioms, option, goal, limit=LIMIT, *, program):
    """One call: how it ended, its counts, the exit code and the full output."""
    output, exit_code = _run(program, command(limit), input_text(axioms, option, goal))
    return {"ending": how_it_ended(output, limit), **counts(output), "exit_code": exit_code, "output": output}


def deriving_command(heuristic, limit, ordering):
    """A deriving run: the axioms alone, one of the HEURISTICS and orderings, printing the clauses it holds
    when it stops. As in the earlier pilot it has no term cap: with one, some runs stop early and print other
    facts than the pilot's. The time and memory caps are those of a call."""
    return ["--print-statistics", "--silent", f"-t{ordering}", "-WNoSelection", f"--processed-clauses-limit={limit}",
            "--print-saturated=eE", f"--cpu-limit={TIME_CAP_SECONDS}", f"--memory-limit={MEMORY_CAP_MB}",
            HEURISTICS[heuristic]]


def derive(axioms, heuristic, limit, ordering, max_line_length, max_lines, *, program):
    """One deriving run: how it ended, how many clause lines it printed, and the clause lines to read: those no
    longer than `max_line_length`, the first `max_lines` of them. The printout is read as it comes and the other
    clause lines are not kept: without a term cap a run can print gigabytes. "output" is the rest of the
    printout (the lines that are not clauses, without those on time and memory used), which is what the ending
    is read from."""
    printed, clauses, other = 0, [], []
    with _input_file(input_text(axioms, None, None)) as path:
        process = subprocess.Popen([program, *deriving_command(heuristic, limit, ordering), path],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=ENVIRONMENT)
        for line in process.stdout:
            if line.startswith("cnf("):
                printed += 1
                if len(line.rstrip("\n")) <= max_line_length and len(clauses) < max_lines:
                    clauses.append(line.rstrip("\n"))
            else:
                other.append(line)
        exit_code = process.wait()
    output = without_usage("".join(other))
    return {"ending": how_it_ended(output, limit, term_cap=None), "exit_code": exit_code, "printed": printed,
            "clauses": clauses, "output": output}


_PRINTED = re.compile(r"^cnf\([^,]+,\s*[^,]+,\s*\((.*)\)\)\.$")


def printed_equations(lines):
    """The positive single equations among printed clause lines, in order. Clauses that are not one positive
    equation (an inequality, a disjunction, $false) are passed over: they cannot be facts to choose."""
    found = []
    for line in lines:
        printed = _PRINTED.match(line.strip())
        if not printed:
            raise ProverError(f"a printed clause is not in the expected form: {line!r}")
        if any(mark in printed.group(1) for mark in ("|", "!=", "$")):
            continue
        try:
            found.append(read_equation(printed.group(1)))
        except EquationError:
            raise ProverError(f"cannot read the clause the prover printed: {line!r}") from None
    return found
