"""Makes one set of prover calls into a folder: for each problem, the calls its caller asks for, at one limit.

Each problem's calls are made together and saved together, as soon as they are done, in two files written whole or
not at all: raw/calls/<problem>.jsonl.gz (every call's full output) and work/<problem>.json (every call's limit,
ending, counts and used facts). A set stopped half-way and started again makes only the calls still missing;
prover_calls.jsonl is written at the end, in the order of the problems given, so the files are the same whatever
the number of workers.
"""
import gzip
import json
import os
from multiprocessing import Pool
from pathlib import Path

from mizar_ladder import prover

FIELDS = ("ending", "processed", "generated", "terms", "used", "exit_code")


def facts_of(library, problem):
    """(the background and given facts as (name, statement), in the problem file's order, without the held-back
    fact; the theorem as (name, statement))."""
    held_back = problem["options"][problem["held_back"] - 1]["name"]
    _, names = library.problem_file(problem["theorem"])
    return ([(name, library.statement(name)) for name in names if name != held_back],
            (problem["theorem"], library.statement(problem["theorem"])))


def _write_whole(path, data):
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    os.replace(partial, path)


def _problem_task(task):
    problem_id, facts, theorem, options, limit, folder, program = task
    records, outputs = [], []
    for number, option in options:
        found = prover.call(facts, option, theorem, limit, program=program)
        records.append({"problem_id": problem_id, "option": number, "option_name": None if option is None else option[0],
                        "limit": limit, **{k: found[k] for k in FIELDS}})
        outputs.append({"option": number, "ending": found["ending"], "output": found["output"]})
    folder = Path(folder)
    lines = "".join(json.dumps(o) + "\n" for o in outputs).encode()
    _write_whole(folder / "raw" / "calls" / f"{problem_id}.jsonl.gz", gzip.compress(lines, mtime=0))
    _write_whole(folder / "work" / f"{problem_id}.json", (json.dumps(records) + "\n").encode())


def make_calls(library, problems, options_of, limit, folder, program, workers=1):
    """Every call `options_of(problem)` asks for (a list of option numbers, None for the call without an option),
    for every problem, into `folder`. Returns the records of prover_calls.jsonl."""
    folder = Path(folder)
    for part in ("raw/calls", "work"):
        (folder / part).mkdir(parents=True, exist_ok=True)
    tasks = []
    for problem in problems:
        if (folder / "work" / f"{problem['id']}.json").exists():
            continue
        facts, theorem = facts_of(library, problem)
        options = [(n, None if n is None else (problem["options"][n - 1]["name"], library.statement(
            problem["options"][n - 1]["name"]))) for n in options_of(problem)]
        tasks.append((problem["id"], facts, theorem, options, limit, str(folder), program))
    if workers == 1:
        for task in tasks:
            _problem_task(task)
    else:
        with Pool(workers) as pool:
            for _ in pool.imap_unordered(_problem_task, tasks, chunksize=1):
                pass
    records = [r for p in problems for r in json.loads((folder / "work" / f"{p['id']}.json").read_text())]
    _write_whole(folder / "prover_calls.jsonl", "".join(json.dumps(r) + "\n" for r in records).encode())
    return records


def read_records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
