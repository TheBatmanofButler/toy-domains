"""The one place that knows the prover, E 2.6: its command line, the text it is given, how to run it, and how
to read from its output how a call ended, what it counted and which library facts its proof uses.

Built from the TPTP code's prover.py. Kept as they are: the fixed environment, the version check and the
program's checksum, the caps, the seven endings of which three decide, taking the lines on time and memory used
out of every output, and giving the prover its input as a file. Where the prover is installed is not written
here: every function that runs it is given `program`, the path of a command that starts it.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

VERSION = "E 2.6 Floral Guranse (8e8bfa2a3f682a4a7d96975eaa7b1133c4267b13)"

TERM_CAP = 1_000_000     # term bank insertions, a cap that does not depend on the machine
MEMORY_CAP_MB = 2000
TIME_CAP_SECONDS = 60    # computing time; the only time limit anywhere, and a call that reaches it says so

# The search setting: the prover's automatic mode, printing its proof. `--free-numbers` makes the numerals of the
# library's statements (`1` in `~ (v1_xboole_0(1))`, a background fact of many problems) plain symbols: without
# it E 2.6 reads them as integers and stops every such problem with "Type mismatch ... expected $i but got $int".
SEARCH = ["--auto", "--proof-object", "--free-numbers"]

# The processed-clause limit of every call in the experiment. A number of steps, not a time, so that it does not
# depend on the machine. Chosen after the prover's key had been made at 1,000 and at 4,000 on the test problems,
# with no model involved: at 4,000 the search program is stronger and the prover has right options for more
# problems (88 against 74), at the price of more problems on which a cap stops the prover before the limit does
# (41 against 4). Above 4,000 that cap stops most calls.
LIMIT = 4000


def command(limit):
    """The pinned command line, with `limit` as the processed-clause limit. The input file's name is put after it."""
    return ["--print-statistics", "--silent", f"--cpu-limit={TIME_CAP_SECONDS}", f"--processed-clauses-limit={limit}",
            f"--tb-insert-limit={TERM_CAP}", f"--memory-limit={MEMORY_CAP_MB}", *SEARCH]


# The one environment every prover process is started with; nothing from the caller's environment reaches it.
# E 2.6's search depends on the C library's memory settings: with MALLOC_MMAP_THRESHOLD_, MALLOC_TOP_PAD_ or
# GLIBC_TUNABLES set, the same input gives other clause counts, other derived facts and, on a few borderline
# calls, another ending (found by the TPTP code). PATH is fixed (not the caller's) because a start script needs
# it to find its own tools; LC_ALL fixes the locale.
ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}

# The prover's search is not the same from one run to the next: in automatic mode it depends on where its memory
# lies, which the system randomises. Nothing here forces it to repeat itself (turning the randomisation off is
# refused by many rented machines); every call is made twice instead and settled (settle.py): each run measures
# how steady it is and writes it to settled.json.

PROVED, CLAUSE_LIMIT, NOTHING_LEFT = "proved", "clause limit", "nothing left"
TERM_CAP_REACHED, MEMORY_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE = "term cap", "memory cap", "time cap", "unreadable"
ENDINGS = (PROVED, CLAUSE_LIMIT, NOTHING_LEFT, TERM_CAP_REACHED, MEMORY_CAP_REACHED, TIME_CAP_REACHED, UNREADABLE)
DECIDING = (PROVED, CLAUSE_LIMIT, NOTHING_LEFT)

# How a call ended, read from the output. Each ending rests on these exact lines of E 2.6's output on these
# problems (real outputs kept in tests/fixtures/endings.json.gz):
#   proved:        "# Proof found!" and "# SZS status Theorem"
#   clause limit:  "# Failure: User resource limit exceeded!" and "# SZS status ResourceOut", with
#                  "# Processed clauses : N" where N is at least the limit, and "# Termbank termtop insertions : M"
#                  under the cap. Why "at least": in automatic mode E first simplifies the clauses it starts with
#                  against each other ("# Presaturation interreduction done" in the output). The clauses it
#                  processes in doing so are counted in the "Processed clauses" it prints, but the limit only
#                  starts to count once the search proper begins. Example: the whole problem file of t47_knaster
#                  starts the search with 386 clauses, and its presaturation processes 422; at a limit of 250 it
#                  prints 672 (422 + 250), at 1,000 it prints 1,422, and so on for every limit tried from 1 to
#                  4,000. So N is the limit plus that problem's presaturation count, never less than the limit.
#                  E has only two user limits here (processed clauses and term bank insertions), so the term
#                  count tells them apart; a call past both is read as the term cap, never as "does not prove".
#   nothing left:  "# No proof found!" and "# SZS status CounterSatisfiable"
#   term cap:      "# Failure: User resource limit exceeded!" and "# SZS status ResourceOut", with
#                  "# Termbank termtop insertions : M" where M is at least the cap
#   memory cap:    "# Failure: Resource limit exceeded (memory)"
#   time cap:      "# Failure: Resource limit exceeded (time)"
#   unreadable:    none of the above, or more than one
# The automatic mode may prune axioms before searching (it is --sine=Auto among other things). It did not on any
# of these problems: every output said "# No SInE strategy applied" and "# Removed by relevancy pruning/SinE : 0".
# A fact the prover never read cannot count as not needed, so an ending that decides is read only when the
# output says both; otherwise the call is unreadable.
_COUNTS = {
    "processed": re.compile(r"^# Processed clauses\s*:\s*(\d+)\s*$", re.M),
    "generated": re.compile(r"^# Generated clauses\s*:\s*(\d+)\s*$", re.M),
    "terms": re.compile(r"^# Termbank termtop insertions\s*:\s*(\d+)\s*$", re.M),
}
_REMOVED = re.compile(r"^# Removed by relevancy pruning/SinE\s*:\s*(\d+)\s*$", re.M)
NO_PRUNING = "# No SInE strategy applied"

# Lines in which E reports the time or memory it used ("# User time : 0.005 s", "# Maximum resident set size:
# 123916 pages", "#    Propositional solver time : 0.000"). They differ from one run to the next, so they are
# taken out of every output before it is read or kept; no ending or count rests on them.
_USAGE = re.compile(r"^#[^:\n]*(?:\btime|resident set size)\s*:[^\n]*\n?", re.M)

# The input file's name as the prover prints it in each line of a proof: "file('/tmp/tmpab12.p', d3_tarski)".
INPUT_NAME = "problem.p"
# A library fact in the printed proof: "fof(<name>, axiom, <formula>, file('<input>', <name>))."
_USED = re.compile(r"^fof\(([^,\s]+), axiom, .*, file\('[^']*', \1\)\)\.$", re.M)


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


def every_axiom_read(output):
    """True when the output says no axiom was pruned before the search (see above)."""
    removed = _REMOVED.findall(output)
    return NO_PRUNING in output.splitlines() and removed == ["0"]


def how_it_ended(output, limit, term_cap=TERM_CAP):
    """One of ENDINGS. `limit` is the processed-clause limit the call was given."""
    lines = {line.strip() for line in output.splitlines()}
    numbers = counts(output)
    endings = []
    if "# Proof found!" in lines and "# SZS status Theorem" in lines:
        endings.append(PROVED)
    if "# No proof found!" in lines and "# SZS status CounterSatisfiable" in lines:
        endings.append(NOTHING_LEFT)
    if "# Failure: Resource limit exceeded (memory)" in lines:
        endings.append(MEMORY_CAP_REACHED)
    if "# Failure: Resource limit exceeded (time)" in lines:
        endings.append(TIME_CAP_REACHED)
    if "# Failure: User resource limit exceeded!" in lines and "# SZS status ResourceOut" in lines:
        terms, processed = numbers["terms"], numbers["processed"]
        if terms is not None and terms >= term_cap:
            endings.append(TERM_CAP_REACHED)   # even if the clause limit was reached too: never "does not prove"
        elif terms is not None and processed is not None and processed >= limit:
            endings.append(CLAUSE_LIMIT)
    if len(endings) != 1:
        return UNREADABLE
    if endings[0] in DECIDING and not every_axiom_read(output):
        return UNREADABLE
    return endings[0]


def used_facts(output):
    """The library names of the axioms in the printed proof (between the SZS output lines), in the order printed,
    each once. Empty when no proof is printed."""
    start, end = "# SZS output start CNFRefutation", "# SZS output end CNFRefutation"
    if start not in output or end not in output:
        return []
    proof = output.split(start, 1)[1].split(end, 1)[0]
    return list(dict.fromkeys(_USED.findall(proof)))


def input_text(facts, option, theorem):
    """`facts` (the background and given facts, (name, statement) in the problem file's order), then the option
    if there is one, under its library name, then the theorem as the conjecture. Nothing else."""
    lines = [f"fof({name}, axiom, {statement})." for name, statement in facts]
    if option is not None:
        lines.append(f"fof({option[0]}, axiom, {option[1]}).")
    lines.append(f"fof({theorem[0]}, conjecture, {theorem[1]}).")
    return "\n".join(lines) + "\n"


@contextmanager
def _input_file(text):
    """The input, in a file of its own: the prover is given a file, as in the TPTP code."""
    handle, path = tempfile.mkstemp(suffix=".p")
    try:
        with os.fdopen(handle, "w") as f:
            f.write(text)
        yield path
    finally:
        os.unlink(path)


def cleaned(output, path):
    """The output without the lines on time and memory used, and with the input file's name, which differs from
    run to run, written as INPUT_NAME."""
    return without_usage(output).replace(f"file('{path}',", f"file('{INPUT_NAME}',")


def _run(program, arguments, text=None):
    """Runs the prover in ENVIRONMENT; the output is both of its streams, standard output first (E prints some
    of its stops, such as running out of memory, on the error stream), cleaned."""
    if text is None:
        done = subprocess.run([program, *arguments], capture_output=True, text=True, env=ENVIRONMENT)
        return without_usage(done.stdout + done.stderr), done.returncode
    with _input_file(text) as path:
        done = subprocess.run([program, *arguments, path], capture_output=True, text=True, env=ENVIRONMENT)
    return cleaned(done.stdout + done.stderr, path), done.returncode


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


def call(facts, option, theorem, limit, *, program):
    """One call: how it ended, its counts, the facts its proof uses, the exit code and the full output."""
    output, exit_code = _run(program, command(limit), input_text(facts, option, theorem))
    ending = how_it_ended(output, limit)
    return {"ending": ending, **counts(output), "used": used_facts(output) if ending == PROVED else [],
            "exit_code": exit_code, "output": output}
