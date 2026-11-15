# The TPTP experiment

How many small algebra problems from the TPTP library are ones where choosing a fact matters at all: a problem
is a set of equations, a goal, and 30 derived facts to choose from; the E prover with a limit of 160 processed
clauses is the judge. Started 2026-11-13.

- `tptp_plan.md`: the experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- `tptp_count/`: the code. `equations.py` reads and writes equations and says when two lists of them are the
  same up to renaming (the search for that is in `renaming.py`); `tptp_file.py` reads one TPTP file;
  `prover.py` is the only code that knows the prover (its command line, its input, how a call ended);
  `derived.py` derives the facts of an axiom set; `options.py` draws the 30; `bins.py` decides a file's bin;
  `count.py` does stage 1's work, `settle.py` settles its two counts into the final files and `checks.py`
  holds stage 1's checks; `report.py` works out every figure.
- `stages/`: one command per stage. Stages talk only through files in a data folder.
- `tests/`: one test file per code file, an end-to-end test, a stand-in prover (`stand_in_prover.py`) that
  answers from a table, the made-up library of twelve files and its hand-worked bins (`made_up.py`), saved
  fixtures (see `tests/fixtures/README.md`), and a copy of the earlier pilots' code used by tests only
  (`tests/reference/`, with the script that made the fixtures).

## The prover and the library

**E 2.6** ("E 2.6 Floral Guranse (8e8bfa2a3f682a4a7d96975eaa7b1133c4267b13)", which `eprover --version` must
print exactly). It is the one used by the earlier pilots: the Debian package file `e26.deb`, sha256
`b3468fd0b0c59c451ea05867f4820af40ba826ac2ce2577533a6059a658b4c55`, with its dependency `picosat_965-2_amd64.deb`,
sha256 `6624843a227421db9e565e4d841f0921b54d02061ffca86d3cdb4bdd4eb2c5aa`. Unpacked (`dpkg-deb -x`), its
`eprover` binary has sha256 `03d2c2a37cf88dee8730aa2755146934e225d0f537815ac16365e69032d54cc4`. E's sources and
releases are at https://www.eprover.org. The code is given a command that starts the prover (`--prover`), for
example a two-line script that sets `LD_LIBRARY_PATH` to the unpacked package's library folder and runs its
`eprover`. Whenever `--prover` is such a script, also give the `eprover` program behind it as
`--prover-program`: the checksum of each is recorded, so that a different program behind the same script is
noticed.

The prover's environment matters, so the code fixes it. E 2.6's search depends on the C library's memory
settings: with `MALLOC_MMAP_THRESHOLD_`, `MALLOC_TOP_PAD_` or `GLIBC_TUNABLES` set, the same input gives other
clause counts, other derived facts and, on a few borderline calls, another ending. So every prover process is
started with the one environment written in `tptp_count/prover.py` (`ENVIRONMENT`: a fixed `PATH`, which a start
script needs to find its own tools, and `LC_ALL=C`), and nothing from the caller's environment reaches it. The
stages can be started from any environment. Stage 1 checks, before it counts anything, that the prover gives the
earlier pilot's endings and counts on 200 of its calls.

Limits set by the shell (`ulimit`) do reach the prover, and a limit on computing time or memory can change how
a run ends. So stage 1 refuses to start unless its limits on computing time (`ulimit -t`), address space
(`ulimit -v`) and data (`ulimit -d`) are all unlimited.

**TPTP v9.3.1**, from the TPTP distribution page (https://www.tptp.org). The folder given as `--library` holds
`Problems/` and `Axioms/`; for the copy used here, the sha256 of the list of the sha256 of every file under them
(`find Axioms Problems -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum`, run inside the library) is
`8a6174f086a7eb1739ce5613e843ef63c29721334e49414eb2b80518edf8e18d` (29,932 files).

## Set up

Python 3.12 or later.

```
python3 -m pip install -r requirements.txt
```

## Run the tests

From this folder:

```
python3 -m pytest                       # everything that does not need the prover (about 3 minutes)
python3 -m coverage run --source=tptp_count -m pytest && python3 -m coverage report -m
python3 -m pytest tests --run-slow --prover PROGRAM -m slow   # needs the pinned prover (about 3 minutes)
```

The slow tests: 200 calls rebuilt from the earlier single-fact pilot's saved problems must give its ending and
its counts; one call run three times at once must give the same result each time; 50 borderline pilot calls
must give the pilot's ending and counts with each of the three memory settings above in the caller's
environment; for 20 of the pilot's axiom sets, the derived facts must equal the pilot's before any topping-up
(one of them, whose deriving runs reach the time cap, must have no usable list of facts).

## Run each stage

Each stage reads from and writes to the folder given as `--data`, prints what it did, and ends with an error if
one of its checks fails.

1. Read the library and count (CPU machine with the prover):
   ```
   python3 stages/1_count.py --library TPTP_FOLDER --data data --prover PROGRAM --prover-program EPROVER \
       --seed 20261112 --pilot-calls tests/fixtures/pilot_calls.jsonl.gz --workers 32
   ```
   First refuses to start under a shell limit on computing time or memory, then checks the prover's version and
   the earlier pilot's 200 calls, and stops on any difference. Then it makes the whole count twice, into
   `data/first/` and `data/second/`, and settles the two into the final files in `data/`, because whether a
   deriving run reaches the 60-second cap can change from one count to the next. An axiom set is used only if
   both counts derived the same facts for it, or both none; if one derived facts and the other none, nothing
   derived from it is used and its files that needed the facts go to "stopped for another reason" (the
   sets and their files are listed in `settled.json`). In the final `derived_facts.jsonl` such a set's record
   has `"unsettled": true` and no facts; each count's own record stays under `first/` and `second/`. Any other
   difference between the counts stops the stage.
   Then it runs the plan's other checks on the final files.

   The final folder holds `files.jsonl` (one line per problem file, with its bin), `problems.jsonl`,
   `derived_facts.jsonl`, `calls/` (every call's full output, one compressed file per problem, and the output
   of each axiom set's deriving runs apart from the clauses they print, one file per axiom set), `settled.json`
   and `stage1_checks.json`; the time taken is printed. The prover's lines on time and memory used are never
   kept, and of a deriving run that was cut off only how it ended is written. Each count saves its results
   under its own `work/` as they are made, so the same command carries on after a stop, and settling is done
   again from scratch; each count's `work/settings.json` holds the seed, the limit, the prover's version, the
   checksums of `--prover` and `--prover-program`, the prover's environment, the shell's limits, the C library's
   version and the TPTP version, and a count started again refuses to carry on if any of them differs. The
   number of workers does not change any file written. Two finished count folders can also be settled on
   their own, without starting the prover:
   ```
   python3 stages/1_count.py --data data --settle data/first data/second
   ```
2. The report (no special machine):
   ```
   python3 stages/2_report.py --data data
   ```
   Writes `bins.json` and prints the tables, with the number of files set aside because the two counts did not
   derive the same facts for their axioms, and the number of such axiom sets.
