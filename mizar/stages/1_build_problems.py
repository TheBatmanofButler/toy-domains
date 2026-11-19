"""Stage 1: build the problems from the library's files and the seed.

Reads the library from --library (checked against the sha256 values in README.md) and writes to --data:
theorems.jsonl (every theorem of the 33 articles and its bin), test_problems.jsonl (300), train_problems.jsonl
(every other qualifying theorem of the 33 articles) and build_summary.json. The build is made twice and must give the same files. Every check of
mizar_ladder/problems.py stops the stage, and a failed check is printed first. Then it prints the bins, where the
options came from, and how close the wrong options are to the right one.
"""
import argparse
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mizar_ladder import problems, statements  # noqa: E402
from mizar_ladder.library import ARTICLES, Library, LibraryError, article  # noqa: E402


def bins_by_article(records):
    """{article: {bin: count}} in the order of the records, and the totals under "all"."""
    table = {"all": {name: 0 for name in problems.BINS}}
    for record in records:
        table.setdefault(record["article"], {name: 0 for name in problems.BINS})[record["bin"]] += 1
        table["all"][record["bin"]] += 1
    return table


def options_summary(test, library):
    """Where the options came from and how close the wrong options are to the right one. Every option comes from
    the held-back fact's article (the one matched quantity); that article is the theorem's own or an earlier one.
    Beside it, unmatched: the mean length of the right and of the wrong options, and how far above the theorem
    each is stated (facts between), averaged per problem first."""
    names = library.mizar_names()
    own = sum(article(p["options"][p["held_back"] - 1]["name"]) == p["article"] for p in test)
    same_article = sum(len({article(o["name"]) for o in p["options"]}) == 1 for p in test)
    kinds = {}
    for p in test:
        held = p["options"][p["held_back"] - 1]["name"]
        kinds[held[0]] = kinds.get(held[0], 0) + 1

    def per_problem(value, right):
        return mean(mean(value(p, o["name"]) for n, o in enumerate(p["options"], 1) if (n == p["held_back"]) == right)
                    for p in test)

    def length(p, name):
        return statements.length(library.statement(name))

    def above(p, name):
        return library.position(p["theorem"]) - library.position(name) - 1

    unnamed = sum(any(symbol not in names for name in [p["theorem"]] + [g["name"] for g in p["given"]]
                      + [o["name"] for o in p["options"]] for symbol in statements.symbols(library.statement(name)))
                  for p in test)
    return {"problems": len(test), "all_options_from_one_article": same_article,
            "held_back_from_the_theorems_own_article": own, "held_back_from_an_earlier_article": len(test) - own,
            "held_back_theorems": kinds.get("t", 0), "held_back_lemmas": kinds.get("l", 0),
            "right_option_length_mean": per_problem(length, True), "wrong_option_length_mean": per_problem(length, False),
            "right_option_facts_above_theorem_mean": per_problem(above, True),
            "wrong_option_facts_above_theorem_mean": per_problem(above, False),
            "problems_showing_a_symbol_without_a_mizar_name": unnamed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--library", required=True, help="the folder holding the library's files")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--test-count", type=int, default=300)
    parser.add_argument("--checksums", help="JSON {file: sha256} to check against instead of README.md "
                                            "(for the made-up library in the tests)")
    args = parser.parse_args(argv)
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    try:
        library = Library(args.library, json.loads(Path(args.checksums).read_text()) if args.checksums else None)
        records, test, train = problems.build(library, args.seed, args.test_count)
        if (records, test, train) != problems.build(library, args.seed, args.test_count):
            raise problems.BuildError("building twice from the same seed gave different problems")
    except (LibraryError, problems.BuildError) as error:
        sys.exit(f"STOP: {error}")
    problems.write_jsonl(data / "theorems.jsonl", records)
    problems.write_jsonl(data / "test_problems.jsonl", test)
    problems.write_jsonl(data / "train_problems.jsonl", train)
    summary = {"seed": args.seed, "articles": list(ARTICLES), "bins": bins_by_article(records),
               "test_problems": len(test), "training_problems": len(train), "options": options_summary(test, library)}
    (data / "build_summary.json").write_text(json.dumps(summary, indent=1))
    print(f"wrote {len(records)} theorems, {len(test)} test problems and {len(train)} training problems")
    print("bins: " + ", ".join(f"{name} {count}" for name, count in summary["bins"]["all"].items()))
    for name, count in summary["options"].items():
        print(f"  {name}: {count:.2f}" if isinstance(count, float) else f"  {name}: {count}")


if __name__ == "__main__":
    main()
