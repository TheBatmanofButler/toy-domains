"""Stage 1b: the test problems with every symbol replaced by a meaningless code (mizar_ladder/renaming.py).

Reads test_problems.jsonl from --data and the library's statements from --library (checked as in stage 1). The
symbols coded are those of the theorems, the given facts and the options of the test problems; the seed is the
problems' own. Writes rename_map.json (symbol to code, with the seed) and test_problems_renamed.jsonl: the same
records in the same order, every `statement` replaced by its renamed form and one field added, "renamed": true.
Run twice it writes the same bytes. Each check stops the stage, its message printed first: every statement read
back gives the library's statement (compared by statements.canonical); within each problem no two of the theorem,
the given facts and the options have the same renamed text; every word of every renamed question is a word of the
fixed sentences and headings, a variable, a code or a numeral. Prints the number of symbols coded and the first
problem's theorem and first three options, named and renamed.

It also writes named_run.json from raw/model_answers.jsonl, which must be complete (every test problem, the same
tries each, one settings record, one model version, no failed answer) or the stage stops: the settings record,
the model version, the number of tries, the run's seed and the request seed of each problem and try. The run's
seed is --run-seed, by default the problems' own; every named request seed must be the one it gives. Stage 3 with
--renamed checks itself against this file before its first request.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mizar_ladder import renaming, statements  # noqa: E402
from mizar_ladder.library import Library, LibraryError  # noqa: E402
from mizar_ladder.problems import read_jsonl, write_jsonl  # noqa: E402
from mizar_ladder.question import build_question  # noqa: E402


def facts(problem):
    """Every fact a problem shows, as (where it sits, name): the theorem, the given facts, the options."""
    return ([("theorem", problem["theorem"])] + [(("given", n), g["name"]) for n, g in enumerate(problem["given"])]
            + [(("options", n), o["name"]) for n, o in enumerate(problem["options"])])


def renamed_problem(problem, text_of):
    """The problem's record with every statement replaced by `text_of[name]`, and "renamed": true added."""
    record = dict(problem, statement=text_of[problem["theorem"]],
                  given=[dict(g, statement=text_of[g["name"]]) for g in problem["given"]],
                  options=[dict(o, statement=text_of[o["name"]]) for o in problem["options"]])
    record["renamed"] = True
    return record


def check(problems, renamed, library, codes):
    """The three checks; returns a list of what failed (empty when all hold)."""
    failed = []
    for problem, record in zip(problems, renamed):
        shown = {record["theorem"]: record["statement"], **{f["name"]: f["statement"]
                                                           for f in record["given"] + record["options"]}}
        for _, name in facts(problem):
            back = renaming.read_back(shown[name], codes)
            if statements.canonical(back) != statements.canonical(library.statement(name)):
                failed.append(f"{problem['id']}: {name} read back is not the library's statement")
        texts = ["".join(record["statement"].split())] + ["".join(f["statement"].split())
                                                           for f in record["given"] + record["options"]]
        if len(set(texts)) != len(texts):
            failed.append(f"{problem['id']}: two of its facts have the same renamed text")
        variables = {t for _, name in facts(problem) for t in statements.tokens(library.statement(name))
                     if t[0].isupper()}
        stray = renaming.stray_words(build_question(record), codes, variables, len(record["given"]))
        if stray:
            failed.append(f"{problem['id']}: words in its renamed question that are not allowed: {stray[:5]}")
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--library", required=True, help="the folder holding the library's files")
    parser.add_argument("--checksums", help="JSON {file: sha256} to check against instead of README.md "
                                            "(for the made-up library in the tests)")
    parser.add_argument("--run-seed", type=int, help="the named model run's --seed (default: the problems' seed)")
    args = parser.parse_args(argv)
    data = Path(args.data)
    problems = read_jsonl(data / "test_problems.jsonl")
    seeds = {p["seed"] for p in problems}
    if len(seeds) != 1:
        sys.exit(f"STOP: the test problems were built with {len(seeds)} seeds, not one: {sorted(seeds)}")
    seed = seeds.pop()
    answers_path = data / "raw" / "model_answers.jsonl"
    if not answers_path.exists():
        sys.exit(f"STOP: {answers_path} does not exist: the named run comes first")
    try:
        named = renaming.named_run(read_jsonl(answers_path), problems,
                                   seed if args.run_seed is None else args.run_seed)
    except renaming.RenamingError as error:
        sys.exit(f"STOP: {error}")
    try:
        library = Library(args.library, json.loads(Path(args.checksums).read_text()) if args.checksums else None)
        names = {name for p in problems for _, name in facts(p)}
        symbols = {s for name in names for s in statements.symbols(library.statement(name))}
        forbidden = set(library.mizar_names()) | set(library.mizar_names().values()) | renaming.fixed_words(0)
        codes = renaming.code_map(symbols, seed, forbidden)
        text_of = {name: renaming.show_renamed(library.statement(name), codes) for name in sorted(names)}
    except (LibraryError, renaming.RenamingError) as error:
        sys.exit(f"STOP: {error}")
    renamed = [renamed_problem(p, text_of) for p in problems]
    failed = check(problems, renamed, library, codes)
    if failed:
        for problem in failed[:20]:
            print(f"FAILED CHECK: {problem}")
        sys.exit(f"STOP: {len(failed)} failed checks on the renamed problems (see above)")
    (data / "rename_map.json").write_text(renaming.map_file(codes, seed))
    write_jsonl(data / "test_problems_renamed.jsonl", renamed)
    (data / "named_run.json").write_text(json.dumps(named, indent=1) + "\n")
    longest_named = max(len(build_question(p)) for p in problems)
    longest = max(len(build_question(r)) for r in renamed)
    print(f"{len(codes)} symbols coded (seed {seed}); the three checks hold on all {len(renamed)} problems")
    print(f"named run: {named['tries']} tries of {len(named['request_seeds'])} problems "
          f"({named['tries'] * len(named['request_seeds'])} request seeds), run seed {named['run_seed']}, model "
          f"{named['model_version']}")
    print(f"longest question: {longest_named} characters named, {longest} renamed")
    first, record = problems[0], renamed[0]
    print(f"{first['id']} theorem {first['theorem']}:\n  named:   {first['statement']}\n"
          f"  renamed: {record['statement']}")
    for named_option, renamed_option in list(zip(first["options"], record["options"]))[:3]:
        print(f"option {named_option['name']}:\n  named:   {named_option['statement']}\n"
              f"  renamed: {renamed_option['statement']}")


if __name__ == "__main__":
    main()
