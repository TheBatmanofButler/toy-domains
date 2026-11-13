"""Builds the test set and the training set of problems, each with its depth, options and right moves.

Attempts are taken in order, 0, 1, 2 and so on; each makes a candidate problem and solves it. A problem at
depth 2 to 5 fills an open place at its depth, test places first, then training places, unless it is the same
problem as one already taken in either set. Every other attempt is counted by kind and not used. Any check that
fails stops the build. Attempts may be solved in several processes; they are still taken in order, so the
result does not depend on how many.
"""
import json
import multiprocessing
import time

from fe_ladder.generator import NOT_MADE_EQUATION, NOT_MADE_GOAL, generate
from fe_ladder.identities import problem_key
from fe_ladder.identity_text import read_identity, write_identity
from fe_ladder.moves import options
from fe_ladder.shortest import DEPTH, OUT_OF_TIME, TEN_MINUTES, solve

DEPTHS = (2, 3, 4, 5)
MOST_MOVES = 5
TAKEN, SAME_AS_TAKEN, DEPTH_FULL = "taken", "same as one taken", "no open place at its depth"
MOST_OUT_OF_TIME = 0.01   # of the attempts that made a problem and reached the search
NOT_MADE = (NOT_MADE_EQUATION, NOT_MADE_GOAL)


class BuildError(Exception):
    pass


def outside_depths(depth):
    """The kind of an attempt whose depth is not one of those built (in the experiment, depth 1)."""
    return f"depth {depth}"


DEPTH_ONE = outside_depths(1)


def try_attempt(seed, attempt, depths=DEPTHS, most_moves=MOST_MOVES, time_limit=TEN_MINUTES):
    """Make and solve one candidate. Returns a dict with its `kind` and, if usable, the problem's fields."""
    made = generate(seed, attempt)
    if "not_made" in made:
        return {"attempt": attempt, "kind": made["not_made"], "family": made["family"], "seconds": 0.0}
    solution = solve(made["equation"], made["goal"], most_moves, time_limit)
    out = {"attempt": attempt, "family": made["family"], "seconds": solution.seconds}
    if solution.outcome != DEPTH:
        return out | {"kind": solution.outcome}
    if solution.depth not in depths:
        return out | {"kind": outside_depths(solution.depth)}
    return out | {"kind": DEPTH, **problem_fields(made["equation"], made["goal"], solution),
                  "planted": made["planted"], "key": problem_key(made["equation"], made["goal"])}


def problem_fields(equation, goal, solution):
    """The fields of a problem record that come from its equation, its goal and their solution."""
    return {"equation": write_identity(equation), "goal": write_identity(goal), "depth": solution.depth,
            "options": [{"result": write_identity(o.result), "moves": [list(m) for m in o.moves]}
                        for o in options([equation])],
            "right_moves": solution.right, "proofs": solution.proofs, "sequences": solution.sequences}


def _try_many(arguments):
    return try_attempt(*arguments)


def _attempts_in_order(seed, depths, most_moves, time_limit, workers, most_attempts):
    jobs = ((seed, attempt, depths, most_moves, time_limit) for attempt in range(most_attempts))
    if workers == 1:
        yield from map(_try_many, jobs)
        return
    with multiprocessing.Pool(workers) as pool:
        yield from pool.imap(_try_many, jobs, chunksize=4)   # imap keeps the order of the attempts


def build_problems(seed, test_per_depth=300, train_per_depth=1000, depths=DEPTHS, most_moves=MOST_MOVES,
                   most_attempts=1_000_000, workers=1, time_limit=TEN_MINUTES):
    """Returns (test problems, training problems, summary). Smaller `depths` and `most_moves` are for tiny
    trials; the experiment uses depths 2 to 5 and searches up to 5 moves."""
    started = time.monotonic()
    open_places = {"test": {d: test_per_depth for d in depths}, "train": {d: train_per_depth for d in depths}}
    chosen = {"test": [], "train": []}
    keys, kinds, seconds, attempts = set(), {}, {}, 0
    stream = _attempts_in_order(seed, depths, most_moves, time_limit, workers, most_attempts)
    try:
        for record in stream:
            attempts += 1
            kind = record["kind"]
            if kind == DEPTH:
                kind = _place(record, open_places, chosen, keys)
            kinds[kind] = kinds.get(kind, 0) + 1
            seconds[kind] = seconds.get(kind, 0.0) + record["seconds"]
            if not any(n for places in open_places.values() for n in places.values()):
                break
    finally:
        stream.close()   # stops the worker processes still solving later attempts
    test, train = (_numbered(chosen[name], name, seed) for name in ("test", "train"))
    summary = {"seed": seed, "attempts": attempts, "count_by_kind": kinds,
               "test_count_by_depth": _count_by_depth(test, depths),
               "training_count_by_depth": _count_by_depth(train, depths),
               "training_depths_left_short": [d for d in depths if _count_by_depth(train, depths)[d] < train_per_depth],
               "solve_seconds_by_kind": seconds}
    check_sets(test, train, summary, test_per_depth, train_per_depth)
    check_solved_again(test + train, most_moves, workers)
    summary["build_seconds"] = time.monotonic() - started
    return test, train, summary


def _place(record, open_places, chosen, keys):
    key = repr(record.pop("key"))
    if key in keys:
        return SAME_AS_TAKEN
    for name in ("test", "train"):
        if open_places[name][record["depth"]] > 0:
            open_places[name][record["depth"]] -= 1
            chosen[name].append(record)
            keys.add(key)
            return TAKEN
    return DEPTH_FULL


def _numbered(records, set_name, seed):
    numbers, out = {}, []
    for r in records:
        number = numbers[r["depth"]] = numbers.get(r["depth"], 0) + 1
        out.append({"id": f"{set_name}-{r['depth']}-{number:04d}", "equation": r["equation"], "goal": r["goal"],
                    "depth": r["depth"], "options": r["options"], "right_moves": r["right_moves"],
                    "proofs": r["proofs"], "sequences": r["sequences"], "family": r["family"],
                    "planted": r["planted"], "attempt": r["attempt"], "seed": seed})
    return out


def _count_by_depth(problems, depths):
    return {d: sum(p["depth"] == d for p in problems) for d in depths}


def check_sets(test, train, summary, test_per_depth, train_per_depth):
    for depth, count in summary["test_count_by_depth"].items():
        if count != test_per_depth:
            raise BuildError(f"the test set has {count} problems at depth {depth}, not {test_per_depth}")
    for depth, count in summary["training_count_by_depth"].items():
        if count > train_per_depth:
            raise BuildError(f"the training set has {count} problems at depth {depth}, more than {train_per_depth}")
    out_of_time = summary["count_by_kind"].get(OUT_OF_TIME, 0)
    searched = summary["attempts"] - sum(summary["count_by_kind"].get(k, 0) for k in NOT_MADE)
    if out_of_time > MOST_OUT_OF_TIME * searched:
        raise BuildError(f"{out_of_time} of {searched} problems searched ran out of time, more than 1%")
    seen = {}
    for problem in test + train:
        if not problem["right_moves"]:
            raise BuildError(f"{problem['id']}: no right move")
        key = repr(problem_key(read_identity(problem["equation"]), read_identity(problem["goal"])))
        if key in seen:
            raise BuildError(f"{problem['id']} is the same problem as {seen[key]}")
        seen[key] = problem["id"]


def _solve_again(problem, most_moves):
    solution = solve(read_identity(problem["equation"]), read_identity(problem["goal"]), most_moves, TEN_MINUTES)
    return problem["id"], solution.outcome, solution.depth, solution.right


def check_solved_again(problems, most_moves=MOST_MOVES, workers=1):
    """Solve every problem again from its text; its depth and right moves must be the ones recorded."""
    recorded = {p["id"]: p for p in problems}
    jobs = [(p, most_moves) for p in problems]
    if workers == 1:
        found = [_solve_again(*job) for job in jobs]
    else:
        with multiprocessing.Pool(workers) as pool:
            found = pool.starmap(_solve_again, jobs, chunksize=4)
    for problem_id, outcome, depth, right in found:
        p = recorded[problem_id]
        if outcome != DEPTH or depth != p["depth"] or right != p["right_moves"]:
            raise BuildError(f"{problem_id}: solved again gives {outcome} {depth} {right}, "
                             f"recorded depth {p['depth']} right moves {p['right_moves']}")


def write_jsonl(path, records):
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]

