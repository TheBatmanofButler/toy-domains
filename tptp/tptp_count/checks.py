"""Stage 1's checks from the plan: the prover gives the earlier pilot's outcome and counts on its 200 saved
calls; a repeat of one call in twenty gives the same result; every file read is in exactly one bin; and no call
that did not decide is counted as "does not prove". Each check returns a list of failures, empty if it holds.
"""
import gzip
import json
from pathlib import Path

from tptp_count import prover
from tptp_count.bins import A_PROBLEM, BINS, NO_FACT_HELPS, PROVED_UNAIDED
from tptp_count.count import library_files
from tptp_count.equations import read_equation, read_relation

PILOT_ENDING = {"proof": prover.PROVED, "limit": prover.CLAUSE_LIMIT}
REPEAT_EVERY = 20


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _same(found, saved):
    return all(found[name] == saved[name] for name in ("ending", "processed", "generated", "terms"))


PILOT_COUNTS = ("ending", "processed", "generated", "terms", "unprocessed")


def pilot_calls(path, program):
    """The saved calls of the earlier pilot (tests/fixtures/pilot_calls.jsonl.gz), each rebuilt and run."""
    with gzip.open(path, "rt") as f:
        saved_calls = [json.loads(line) for line in f]
    failures = []
    for saved in saved_calls:
        axioms = [read_equation(a) for a in saved["axioms"]]
        option = None if saved["option"] is None else read_equation(saved["option"])
        found = prover.call(axioms, option, read_relation(saved["goal_denied"])[1], program=program)
        found["unprocessed"] = prover.unprocessed(found["output"])
        pilot = saved["pilot_result"]
        theirs = {"ending": PILOT_ENDING[pilot["status"]], "processed": pilot["processed"],
                  "generated": pilot["generated"], "terms": pilot["tb"], "unprocessed": pilot["unprocessed"]}
        if any(found[name] != theirs[name] for name in PILOT_COUNTS):
            failures.append(f"pilot call {saved['theory']} {saved['gi']} {saved['call']}: "
                            f"now {[found[k] for k in PILOT_COUNTS]}, the pilot's {[theirs[k] for k in PILOT_COUNTS]}")
    return failures


def repeat(data, program):
    """Every twentieth call, counting the calls of all problems in order (unaided first, then the options)."""
    failures, number = [], 0
    for problem in _jsonl(Path(data) / "problems.jsonl"):
        axioms, goal = [read_equation(a) for a in problem["axioms"]], read_equation(problem["goal"])
        calls = [(None, problem["unaided"])] + list(zip(problem.get("options", []), problem.get("calls", [])))
        for option, saved in calls:
            if number % REPEAT_EVERY == 0:
                found = prover.call(axioms, None if option is None else read_equation(option), goal, program=program)
                if not _same(found, saved):
                    failures.append(f"{problem['id']} call {number}: again {found['ending']} {found['processed']}, "
                                    f"saved {saved['ending']} {saved['processed']}")
            number += 1
    return failures


def one_bin_each(library, data):
    files = _jsonl(Path(data) / "files.jsonl")
    failures = [f"{f['path']}: bin {f['bin']!r}" for f in files if f["bin"] not in BINS]
    if [f["path"] for f in files] != library_files(library):
        failures.append(f"files.jsonl holds {len(files)} lines, not one per library file in order")
    return failures


def no_silent_does_not_prove(data):
    """A file is in "no single fact helps" only if every call ended on the clause limit or with nothing left,
    and the right facts are exactly the options whose call proved."""
    problems = {p["id"]: p for p in _jsonl(Path(data) / "problems.jsonl")}
    failures = []
    for file in _jsonl(Path(data) / "files.jsonl"):
        problem = problems.get(file["problem_id"])
        if problem is None:
            continue
        unaided = problem["unaided"]["ending"]
        endings = [c["ending"] for c in problem.get("calls", [])]
        if file["bin"] == PROVED_UNAIDED and unaided != prover.PROVED:
            failures.append(f"{file['path']}: proved unaided, but the unaided call ended {unaided}")
        if file["bin"] in (NO_FACT_HELPS, A_PROBLEM) and (unaided != prover.CLAUSE_LIMIT or len(endings) != 30):
            failures.append(f"{file['path']}: {file['bin']}, with unaided {unaided} and {len(endings)} option calls")
        if file["bin"] == NO_FACT_HELPS and any(e not in (prover.CLAUSE_LIMIT, prover.NOTHING_LEFT) for e in endings):
            failures.append(f"{file['path']}: no single fact helps, but its calls ended {sorted(set(endings))}")
        if problem.get("right", []) != [n for n, e in enumerate(endings) if e == prover.PROVED]:
            failures.append(f"{file['path']}: right facts {problem.get('right')} do not match the calls")
        if (file["bin"] == A_PROBLEM) != bool(problem.get("right")):
            failures.append(f"{file['path']}: {file['bin']} with right facts {problem.get('right')}")
    return failures
