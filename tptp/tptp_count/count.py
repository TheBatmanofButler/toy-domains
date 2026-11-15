"""Does stage 1's work: reads every problem file of the library, finds the same problems and the same axiom sets,
derives the facts once per axiom set, draws the options, makes the calls, and writes files.jsonl,
problems.jsonl, derived_facts.jsonl and calls/ to the data folder.

Each axiom set's deriving and each problem's calls are one task. A task's result is saved under work/ as soon as
it is done, so a run that is stopped carries on from what is saved when started again. The files written at the
end are put together from the saved results in a fixed order, so they do not depend on the number of workers.
"""
import gzip
import json
import os
import re
import resource
from multiprocessing import Pool
from pathlib import Path

from tptp_count import derived, options, prover
from tptp_count.bins import bin_of, MAIN, STOPPED
from tptp_count.equations import key, read_equation, rename_symbols, symbol_renaming, universal_form, write_equation
from tptp_count.tptp_file import axioms_and_goal, is_theorem, read_file, usable


class CountError(RuntimeError):
    pass


def library_files(library):
    """Every problem file, as its path inside the library, in the library's own order of names. Only files named
    `.p` are problems: TPTP keeps the problems it has withdrawn beside them, named `.rm`, and those are not read
    and get no line, because TPTP no longer stands behind them."""
    root = Path(library)
    return sorted(path.relative_to(root).as_posix() for path in (root / "Problems").rglob("*.p"))


_VERSION = re.compile(r"^%\s*File\s*:.*\bTPTP v(\d+(?:\.\d+)*)", re.M)


def library_version(library, paths):
    """The TPTP version, from the header of the library's first problem file ("% File : ... : TPTP v9.3.1.")."""
    found = _VERSION.search((Path(library) / paths[0]).read_text(errors="replace")) if paths else None
    if not found:
        raise CountError("no TPTP version in the header of the library's first problem file")
    return found.group(1)


def read_one(task):
    path, library = task
    file = read_file(path, library)
    found = {"path": path, "area": file.area, "status": file.status, "usable": usable(file)}
    if found["usable"] is True:
        axioms, goal = axioms_and_goal(file)
        found.update(axioms=[write_equation(a) for a in axioms], goal=write_equation(goal))
    return found


def find_problems(files):
    """Of the usable theorem files, in order: the problems (the first file of each), the duplicates, and the
    axiom sets (each with the axioms of its first problem, which are the ones the prover derives from)."""
    problems, duplicates, first_of_problem, axiom_sets, set_of_key = [], {}, {}, [], {}
    for file in files:
        if file["usable"] is not True or not is_theorem(file["status"]):
            continue
        axioms, goal = [read_equation(a) for a in file["axioms"]], read_equation(file["goal"])
        problem_key = key(axioms, goal)
        if problem_key in first_of_problem:
            duplicates[file["path"]] = first_of_problem[problem_key]
            continue
        first_of_problem[problem_key] = file["path"]
        set_key = key(axioms)
        if set_key not in set_of_key:
            set_of_key[set_key] = len(axiom_sets)
            axiom_sets.append({"index": len(axiom_sets), "first_file": file["path"], "axioms": file["axioms"]})
        problems.append({"id": Path(file["path"]).stem, "path": file["path"], "area": file["area"],
                         "axioms": file["axioms"], "goal": file["goal"], "axiom_set": set_of_key[set_key]})
    if len({p["id"] for p in problems}) != len(problems):
        raise CountError("two problem files have the same name")
    return problems, duplicates, axiom_sets


def _write_atomically(path, data):
    """A result file is either all there or not there, whenever the run stops."""
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    os.replace(partial, path)


def _json_bytes(value):
    return (json.dumps(value) + "\n").encode()


def derive_task(task):
    """The facts of one axiom set. The part of each deriving run's output that is not a list of clauses goes to
    calls/axiom_set_N.jsonl.gz, so that how each run ended can be read again; of a run that did not finish, only
    how it ended is written (see derived.derive_facts)."""
    axiom_set, data, program = task
    found = derived.derive_facts([read_equation(a) for a in axiom_set["axioms"]], program=program)
    facts = None if found["facts"] is None else [write_equation(f) for f in found["facts"]]
    result = {"axiom_set": axiom_set["index"], "first_file": axiom_set["first_file"], "axioms": axiom_set["axioms"],
              "facts": facts, "not_finished": found["not_finished"], "printed": found["printed"],
              "runs": found["runs"]}
    lines = b"".join(_json_bytes({"run": n, **run} if output is None else {"run": n, **run, "output": output})
                     for n, (run, output) in enumerate(zip(found["runs"], found["outputs"])))
    _write_atomically(Path(data) / "calls" / f"axiom_set_{axiom_set['index']}.jsonl.gz", gzip.compress(lines, mtime=0))
    _write_atomically(Path(data) / "work" / "derived" / f"{axiom_set['index']}.json", _json_bytes(result))


# Kept in a problem's saved result under work/ but not written to problems.jsonl: whether there were too few facts,
# why there was no usable list, and the number of the problem's axiom set (which settle.py reads).
WORK_ONLY = ("too_few", "no_facts", "axiom_set")


def _counts(result):
    return {name: result[name] for name in ("ending", "processed", "generated", "terms")}


def problem_task(task):
    """The unaided call; if it reached the clause limit and the axiom set has a usable list of facts, the
    options and a call with each. `facts` is None when there is no usable list, and `no_facts` says why."""
    problem, facts, no_facts, seed, data, program = task
    axioms, goal = [read_equation(a) for a in problem["axioms"]], read_equation(problem["goal"])
    unaided = prover.call(axioms, None, goal, program=program)
    result = {"id": problem["id"], "path": problem["path"], "area": problem["area"], "axioms": problem["axioms"],
              "goal": problem["goal"], "unaided": _counts(unaided), "seed": seed, "axiom_set": problem["axiom_set"]}
    if facts is None:
        result["no_facts"] = no_facts
    outputs = [{"call": "unaided", "ending": unaided["ending"], "output": unaided["output"]}]
    if unaided["ending"] == prover.CLAUSE_LIMIT and facts is not None:
        drawn = options.draw([read_equation(f) for f in facts], universal_form(goal, axioms), seed, problem["id"])
        result["too_few"] = drawn is None
        if drawn is not None:
            calls = [prover.call(axioms, option, goal, program=program) for option in drawn]
            result.update(options=[write_equation(o) for o in drawn], calls=[_counts(c) for c in calls],
                          right=[n for n, c in enumerate(calls) if c["ending"] == prover.PROVED],
                          undecided_options=[n for n, c in enumerate(calls) if c["ending"] not in prover.DECIDING])
            outputs += [{"call": n, "ending": c["ending"], "output": c["output"]} for n, c in enumerate(calls)]
    lines = b"".join(_json_bytes(o) for o in outputs)
    _write_atomically(Path(data) / "calls" / f"{problem['id']}.jsonl.gz", gzip.compress(lines, mtime=0))
    _write_atomically(Path(data) / "work" / "problems" / f"{problem['id']}.json", _json_bytes(result))


def _run(function, tasks, workers):
    if workers == 1:
        for task in tasks:
            function(task)
        return
    with Pool(workers) as pool:
        for _ in pool.imap_unordered(function, tasks, chunksize=1):
            pass


def _facts_for(problem, axiom_sets, saved):
    """The axiom set's facts in this problem's symbols: they were derived from the set's first file, which may
    name its symbols differently. None if the axiom set has no usable list of facts."""
    if saved["facts"] is None:
        return None
    first = [read_equation(a) for a in axiom_sets[problem["axiom_set"]]["axioms"]]
    names = symbol_renaming(first, [read_equation(a) for a in problem["axioms"]])
    if names is None:
        raise CountError(f"{problem['path']}: its axioms are not a renaming of its axiom set's")
    return [write_equation(rename_symbols(read_equation(f), names)) for f in saved["facts"]]


# The shell's limits that reach the prover through the process that starts it: one on computing time, and two on
# memory (address space, and data). Any of them can stop a prover run that would otherwise have finished, and how
# it stops (killed, out of memory) would then depend on the machine it ran on, not on the problem.
SHELL_LIMITS = {"computing time": resource.RLIMIT_CPU, "address space": resource.RLIMIT_AS,
                "data": resource.RLIMIT_DATA}


def shell_limits():
    """{name: "unlimited" or the limit} for this process's own limits in SHELL_LIMITS."""
    found = {}
    for name, which in SHELL_LIMITS.items():
        soft, _ = resource.getrlimit(which)
        found[name] = "unlimited" if soft == resource.RLIM_INFINITY else soft
    return found


def settings(library, paths, program, seed, prover_program=None):
    """What a run's results depend on besides the library's files. Saved in work/settings.json; a run started
    again carries on only if every one of these is the same. `prover_program` is the prover program behind
    `program` when `program` is a start script, so that a change of program behind the same script is seen."""
    return {"seed": seed, "limit": prover.LIMIT, "prover_version": prover.VERSION,
            "prover_checksum": prover.program_checksum(program),
            "prover_program_checksum": None if prover_program is None else prover.program_checksum(prover_program),
            "prover_environment": prover.ENVIRONMENT, "shell_limits": shell_limits(),
            "c_library": os.confstr("CS_GNU_LIBC_VERSION"), "tptp_version": library_version(library, paths)}


def _check_settings(work, found):
    path = work / "settings.json"
    if path.exists() and json.loads(path.read_text()) != found:
        saved = json.loads(path.read_text())
        differing = sorted(name for name in set(saved) | set(found) if saved.get(name) != found.get(name))
        raise CountError(f"{work} holds results made with other settings ({', '.join(differing)}): {path.read_text()}")
    path.write_text(json.dumps(found))


def count(library, data, program, seed, workers=1, prover_program=None):
    data = Path(data)
    work = data / "work"
    for folder in (work / "derived", work / "problems", data / "calls"):
        folder.mkdir(parents=True, exist_ok=True)
    paths = library_files(library)
    _check_settings(work, settings(library, paths, program, seed, prover_program))
    if workers == 1:
        files = [read_one((path, library)) for path in paths]
    else:
        with Pool(workers) as pool:
            files = pool.map(read_one, [(path, library) for path in paths], chunksize=50)
    problems, duplicates, axiom_sets = find_problems(files)
    print(f"{len(files)} files read; {len(problems)} problems in {len(axiom_sets)} axiom sets", flush=True)

    _run(derive_task, [(s, str(data), program) for s in axiom_sets
                       if not (work / "derived" / f"{s['index']}.json").exists()], workers)
    saved_sets = [json.loads((work / "derived" / f"{s['index']}.json").read_text()) for s in axiom_sets]
    _run(problem_task, [(p, _facts_for(p, axiom_sets, saved_sets[p["axiom_set"]]),
                         saved_sets[p["axiom_set"]]["not_finished"], seed, str(data), program)
                        for p in problems if not (work / "problems" / f"{p['id']}.json").exists()], workers)
    results = {p["id"]: json.loads((work / "problems" / f"{p['id']}.json").read_text()) for p in problems}
    write_files(data, files, duplicates, results, saved_sets)


def write_files(data, files, duplicates, results, saved_sets):
    """files.jsonl, problems.jsonl and derived_facts.jsonl, in the library's order and the axiom sets' order."""
    file_lines, problem_lines = [], []
    by_path = {result["path"]: result for result in results.values()}
    for file in files:
        result = by_path.get(file["path"])
        unaided = result["unaided"]["ending"] if result else None
        drawn = result.get("options") if result else None
        endings = [c["ending"] for c in result.get("calls", [])] if result else []
        bin_name, why = bin_of(file["usable"], file["status"], duplicates.get(file["path"]), unaided, drawn, endings,
                               result.get("no_facts") if result else None)
        has_problem_line = bin_name in MAIN or bin_name == STOPPED   # the plan's last four bins
        file_lines.append({"path": file["path"], "area": file["area"], "status": file["status"], "bin": bin_name,
                           "why": why, "problem_id": result["id"] if has_problem_line else None})
        if has_problem_line:
            problem_lines.append({k: v for k, v in result.items() if k not in WORK_ONLY})
    for name, lines in (("files.jsonl", file_lines), ("problems.jsonl", problem_lines),
                        ("derived_facts.jsonl", saved_sets)):
        _write_atomically(Path(data) / name, b"".join(_json_bytes(line) for line in lines))
    print(f"wrote {len(file_lines)} files, {len(problem_lines)} problems, {len(saved_sets)} axiom sets", flush=True)
