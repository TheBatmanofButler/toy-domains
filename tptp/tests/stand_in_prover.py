"""A stand-in for the prover, for tests: it answers from a table instead of proving anything.

The prover is started with a fixed environment that holds nothing of the caller's, so the table cannot be named
by a setting. Instead conftest.py writes, for each table, a small program that calls main() with the table's
path; that program is what the code under test is given as the prover.

Like the prover it reads its input from the file named last. The table is a JSON file: {"version": text or
null, "answers": [{"when": [texts], "output": answer}]}. The first answer whose texts all appear in the arguments
or the input decides what is printed; with none, nothing is printed (an output the real code must read as
"unreadable"). An answer is a text for the output stream, a pair [output stream, error stream], or
PRINT_ENVIRONMENT, which prints the environment the stand-in was started with, as JSON; or {"repeat": line,
"then": text}, which prints the line a different number of times on each start (from 1 to 1,000) and then the
text, with "{seconds}" in it replaced by a different number each time: an output that changes from one run to
the next, as a cut-off run's does; or {"first time": answer, "after": answer}, which gives the first answer the
first time the row is used and the second every time after (so that two counts made with the same stand-in can
differ in one deriving run, as two counts on the real prover can when a run sits at the time cap). `--version`
prints the pinned version, or the table's version if it gives one.
Every start, `--version` included, adds the environment it was started with as one line to the log file.
"""
import json
import os
import random
import sys

PINNED = "E 2.6 Floral Guranse (8e8bfa2a3f682a4a7d96975eaa7b1133c4267b13)"
PRINT_ENVIRONMENT = "<print the environment>"


def _first_time(marker):
    """True for the first start that asks, whichever process it is in: the marker file is made atomically."""
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def main(table_path, log_path):
    with open(log_path, "a") as f:
        f.write(json.dumps(dict(os.environ), sort_keys=True) + "\n")
    with open(table_path) as f:
        table = json.load(f)
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print(table["version"] or PINNED)
        return
    with open(arguments[-1]) as f:
        text = " ".join(arguments[:-1]) + "\n" + f.read()
    for number, entry in enumerate(table["answers"]):
        if all(part in text for part in entry["when"]):
            answer = entry["output"]
            if isinstance(answer, dict) and "first time" in answer:
                answer = answer["first time"] if _first_time(f"{log_path}.row{number}") else answer["after"]
            if answer == PRINT_ENVIRONMENT:
                sys.stdout.write(json.dumps(dict(os.environ), sort_keys=True))
            elif isinstance(answer, dict):
                varying = random.SystemRandom()
                sys.stdout.write(answer["repeat"] * varying.randint(1, 1000))
                sys.stdout.write(answer["then"].replace("{seconds}", f"{varying.uniform(0, 60):.3f}"))
            elif isinstance(answer, list):
                sys.stdout.write(answer[0])
                sys.stderr.write(answer[1])
            else:
                sys.stdout.write(answer)
            return
