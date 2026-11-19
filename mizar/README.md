# The Mizar experiment

The last puzzle of post 1 and the first on real theorems: given a theorem of the Mizar library and all but one of
the facts its author cited, pick the missing fact from 30. Started 2026-11-14.

- `mizar_plan.md`: the whole experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- `mizar_ladder/`: the code. `library.py` is the only code that knows the library's files; `statements.py` reads
  one statement and writes it as the solver sees it; `problems.py` builds the problems; `programs/` holds one file
  per simple program; `question.py`, `model_server.py`, `model_run.py`, `thinking_end.py`, `run_check.py` and
  `answers.py` ask the model, see how its thinking ended, check the run and read its answers; `scoring.py` works
  out every figure, except the same-wrong-answers comparison, which is in `wrong_answers.py`, and the second table,
  in `second_table.py`, and the programs counted together, in `together.py`; `renaming.py` writes the problems
  with every symbol replaced by a meaningless code and compares the model named and renamed; `run_settings.py`
  checks that every
  answer was asked under the same settings; `report.py` writes the tables and the bars. `prover.py` is the only
  code that knows the prover; `calls.py` makes one set of prover calls into a folder; `settle.py` settles two runs
  of the same calls; `prover_key.py` makes the prover's key.
- `probe/`: the thinking-length probe of stage 3 (`probe.py`, copied from the functional-equations code, with the
  script that starts its model server, `start_vllm.sh FOLDER`, which works and logs in the folder it is given). It
  runs on the pod, before the model run, and is not part of the package.
- `stages/`: one command per stage of `mizar_plan.md`. Stages talk only through files in a data folder.
- `tests/`: one test file per code file (several for the files copied from the cube, as there), saved fixtures
  (see `tests/fixtures/README.md`), the scripts that made them (`tests/reference/`), a stand-in prover and a
  stand-in model server, and an end-to-end test of the four stages.
- `data/`: where the stages write, when given `--data data`. `data/raw/` is not tracked by git.

## The prover

E 2.6 (`E 2.6 Floral Guranse (8e8bfa2a3f682a4a7d96975eaa7b1133c4267b13)`), the version pinned for the TPTP code,
built from the E prover's release 2.6 and unpacked with a start script (`eprover.sh`, which sets the library
path of its own folder and starts `root/bin/eprover`). Its command is given to stage 2 as `--prover`; when it is
a start script, `--prover-program` names the program behind it, and the checksums of both are recorded. The
prover is always started:
- in one fixed environment, `PATH=/usr/bin:/bin` and `LC_ALL=C` (E's search changes with the C library's memory
  settings otherwise);
- with the input in a file, and the command line `--print-statistics --silent --cpu-limit=60
  --processed-clauses-limit=LIMIT --tb-insert-limit=1000000 --memory-limit=2000 --auto --proof-object
  --free-numbers`.
LIMIT is the experiment's limit, 4,000 processed clauses (`prover.LIMIT`, written once there): a number of steps,
not a time, so that it does not depend on the machine. It was chosen after the prover's key had been made at 1,000
and at 4,000 on the test problems, with no model involved: at 4,000 the search program is stronger and the prover
has right options for more problems (88 against 74), at the price of more problems on which a cap stops the prover
before the limit does (41 against 4). Above 4,000 that cap stops most calls. Stage 2 takes `--limit N` to make the
key at another limit instead, for looking at how the prover's verdicts move with the limit; the experiment's runs
use the default. The limit used is recorded in `settings.json` and in every call's record, and a stage started
again with another limit into the same data folder is refused. Stage 2 refuses to start under a shell limit on
computing time or memory (`ulimit -t`, `-v`, `-d`).

**The prover's search is not the same from one run to the next.** In its automatic mode E 2.6's search depends on
where its memory lies, which the system randomises: the same call can process other numbers of clauses, use other
facts in its proof and, now and then, reach another verdict. Nothing is done to force it to repeat itself (the
setting that would, turning address randomisation off, is refused by many rented machines). Instead every call is
made twice, and each run measures how steady the prover is. A call is settled when both runs give the same ending
and, when both proved the theorem, agree on whether the option is in the proof; otherwise it is unsettled and
decides nothing (it counts as a call that did not decide; its final record keeps no used facts or counts, and both
runs' records stay under `raw/`). Clause counts are not compared. `settled.json` gives the number and share of
unsettled calls, how they differed, and each by problem, option number and the option's fact name; the share is
also printed by stage 2, saved in `programs_summary.json`, and shown beside the prover's bins in the second table.
Running stage 2 again can therefore give slightly different prover figures: other unsettled calls, and now and then
another bin for a problem.

## The library's files

Mizar library version 4.181.1147 in the form the prover community publishes (the MPTP export used for the
"small, consistent" problems of the Mizar40 experiments): every statement in the provers' format, the library's
order, one problem file per theorem, the facts each author's proof refers to, and Mizar's names for the coded
symbols. The folder holding them is given to stage 1 as `--library`. At start the code checks each of these five
files against the sha256 below and stops if one differs:

| File | sha256 |
|---|---|
| `statements` | `ad845ce9a6a8ec2a846cbc24d594bc441b2f9530fb4319a657d7c9b272b8eec5` |
| `seq` | `7055dc8e1c5072473e62a3394efc607363ca623449c8fffde455a9a9dad08204` |
| `00mizrefs` | `f60583602420e38a87128f12afb1dd32858e1b261fe40d319e4e123239bfb131` |
| `00constrnames` | `f1f32f9e5f4380e0b0e8960c5233106310193f8746878bbdb5c8b41075d723a6` |
| `xboole_1.miz` | `9498cdb45f8a67a696f098d52eacd259a6b5b78e8851df5dc6ed5e9a82d857aa` |

- `statements`: one line `fof(name, axiom, formula).` per fact, 146,700 facts.
- `seq`: one fact name per line, in the library's order.
- `00mizrefs`: one line per theorem, `theorem:fact,fact,...`, the facts its proof refers to, with repeats.
- `00constrnames`: lines `coded_symbol mizar_name`; a symbol can have several lines and the first is used.
- `problems_small_consist/`: one sub-folder per article and one problem file per theorem, named
  `<article>__<theorem>`; 2.4 GB. As unpacked it holds 1,155 entries: 1,151 folders and 4 plain files. 1,148 of the
  folders are articles holding problem files, 57,897 files in all; 3 are named after articles but empty
  (`algstr_0`, `jordan13`, `schems_1`); the 4 plain files (`00all`, `00seq1`, `00seq3`, `00seq4`) are lists that
  came with the archive and are not problem files. The code reads only the article folders. It is unpacked from
  `problems_small_consist.tar.gz`, whose sha256 is
  `2eade50e809616935bffee542a553b1e8bae868ed020bc52941f1ff52e468b8f`; check the archive before unpacking it.
  The unpacked folder itself is not checked at start.
- `xboole_1.miz`: one article in Mizar's own language, kept for reading beside the other files. The code does not
  read it.

These files are downloaded data. Read them only from the code here (or with `python3 -I`); do not run anything
from inside the folder that holds them.

## Set up

Python 3.12 or later (the pinned numpy does not install on 3.11).

```
python3 -m pip install -r requirements.txt
```

## Run the tests

From this folder:

```
python3 -m pytest                      # everything that needs neither the library's files nor a model server
python3 -m coverage run --source=mizar_ladder -m pytest && python3 -m coverage report -m
python3 -m pytest --run-slow --library=FOLDER --prover=PROGRAM   # also the slow tests, on the real files and
                                                                 # the pinned prover
```

## Run each stage

Each stage reads from and writes to the folder given as `--data`, prints what it did, and stops with a message
if one of its checks fails; a failed check is printed first.

1. Build the problems (no special machine; about three minutes, as the build is made twice):
   ```
   python3 stages/1_build_problems.py --data data --library FOLDER --seed 20261112
   ```
   Writes `theorems.jsonl` (every theorem of the 33 articles with its bin), `test_problems.jsonl` (300 of the
   qualifying theorems, drawn with the seed), `train_problems.jsonl` and `build_summary.json` (the bins, where the
   options came from, and how close the wrong options are to the right one, and how many questions show a coded
   symbol with no Mizar name, the only place an article's name can appear), and prints the summary. No two options
   of a problem read the same and no option reads the same as a given fact or the theorem, judged on the statement
   and on the shown text (Mizar gives one name to several symbols); the build stops if one would.
   **The training set** is one pool with the test set: every qualifying theorem of the 33 articles that was not
   drawn for the test (about 900), built exactly as a test problem is. Nothing is built from any other article.
   The build stops if a theorem is in both sets, if a training problem's theorem is not of the 33 articles, or if
   there are not exactly 300 test problems. Every count a program takes from the library leaves out the 300 test
   theorems and, for a training problem, its own theorem; and every program that learns refuses a training set that
   holds a test problem's theorem.
2. The prover's key and the simple programs (a CPU machine with the prover):
   ```
   python3 stages/2_programs_and_prover.py --data data --library FOLDER --prover PROGRAM \
       [--prover-program PROGRAM] --seed 20261112 --workers N [--limit N]
   ```
   First the key, at the limit: every test problem without an option and with each of its 30 options
   (`prover_calls.jsonl`, `raw/calls/`, `prover_key.jsonl`, where a problem stopped for another reason says why). A
   search that finishes with no proof ("nothing left") counts as "does not prove". The calls are made twice, under
   `raw/`, and settled as described under "The prover": a call on which the two runs disagree is "unsettled", with
   both endings beside it, and decides nothing (`settled.json` gives their number and share, and names them). Then
   the programs (`program_picks.jsonl`, `programs_summary.json`): `guessing`; `recall`, the option cited most
   often; `lookup`, the option that is the held-back fact in the most training problems (given only the training
   problems' held-back facts by name; ties share the weight, and if none of the 30 was ever held back in training,
   equal weight on all 30); `options_only`; `surface_symbols`; `surface_trained`; and `search`. It writes
   `settings.json` (seed, limit, the prover's version and checksums, the environment and the C library's version)
   and, started again, carries on only with the same settings, making only the calls still missing. It prints any
   failed check first, then how far `options_only` and `recall` sit above guessing, then the limit, the prover's
   bins, the problems whose call with the held-back fact ended as nothing left, the share of the key's calls on
   which the two runs disagreed, the scores, and the programs counted together (per row, how many problems the best
   single program gets, how many at least one program gets, how many none gets; a program gets a problem when more
   than half its weight is on the right option, and `guessing` is left out of "at least one"); it checks that
   guessing scores 1 in 30.
3. The model run, every test problem 5 times, as in the cube's run. `settings.json` holds the sampling settings
   the model's makers recommend for thinking mode and where they were read: `{"sampling": {"temperature": ...,
   "top_p": ..., "top_k": ..., "min_p": ...}, "source": "..."}`. Each model server is a vLLM server started with
   the reasoning parser and the end-of-thinking text the run records:
   ```
   python3 stages/3_model_run.py --print-reasoning-config [--stop-sentence qwen]
   vllm serve MODEL ... --reasoning-parser qwen3 \
       --reasoning-config "$(python3 stages/3_model_run.py --print-reasoning-config)"
   ```
   Then:
   ```
   python3 stages/3_model_run.py --data data --base-url http://HOST:PORT [--base-url http://HOST2:PORT ...] \
       --model-name NAME --model-version VERSION --settings settings.json --seed SEED --price-per-hour DOLLARS \
       --thinking-allowance TOKENS [--api-key-env VARIABLE] [--workers N] [--timeout SECONDS] \
       [--stop-sentence qwen] [--carry-on] [--retry-failed]
   ```
   Writes `raw/model_answers.jsonl`, saving each answer as it arrives; the same command carries on after a stop.
   The thinking allowance is chosen after the probe (`mizar_plan.md`); the default is the cube's 8,000. The probe
   asks 32 training problems drawn at random with the seed once each, with no thinking budget and room for 64,000
   tokens, and writes each reply and a table of how long the thinking ran:
   ```
   python3 probe/probe.py --train data/train_problems.jsonl --out PROBE_FOLDER [--deadline EPOCH_SECONDS]
   python3 probe/probe.py --train data/train_problems.jsonl --out PROBE_FOLDER --table   # rebuild the table
   ```
   Order of asking: the first try of every problem before the second try of any, the problems in an order set by
   `--seed`. Everything else (several servers, the check after the first 100 answers written to
   `model_run_check.json`, `--carry-on`, `--retry-failed`, the server's thinking budget and how each record says
   how its thinking ended) is as in the cube's README.
4. Report:
   ```
   python3 stages/4_report.py --data data
   ```
   Writes `scores.json`, `problem_by_problem.json`, `counted_together.json` (the counts of stage 2 and, of the
   problems at least one program gets and of those none gets, how many the model gets: at least three of its five
   tries right), `wrong_answers.json`, `second_table.json` (the answers and picks scored again with the prover's
   key, on the problems where it has right options), `report.txt` and `bars.svg`. Every table has one row for all
   problems, then rows by number of cited facts (2 to 3, 4 to 6, 7 or more) and by article group. It reads only
   saved files, and run twice it writes the same files. It stops if the answers were not all asked under the same
   settings.

### Renaming (after the first run)

The same 300 problems asked again with every symbol replaced by a meaningless code (`mizar_plan.md`, "Renaming").
Each distinct symbol of the test problems' statements gets one code, `s` and five digits, from a shuffle with the
problems' seed; logic signs, `=`, variables and numerals are kept, and every symbol is written in front of its
arguments (`A c= B` becomes `s00645(A, B)`). The question's first sentence says the symbols are codes. The simple
programs are not run again: they work on the symbols underneath, which the renaming does not change.

1b. After stage 1, on any machine:
   ```
   python3 stages/1b_rename.py --data data --library FOLDER
   ```
   Writes `rename_map.json` (symbol to code, with the seed) and `test_problems_renamed.jsonl` (the same records,
   every statement renamed, `"renamed": true` added); run twice it writes the same bytes, and
   `test_problems.jsonl` is left as it is. It stops if a statement read back is not the library's, if two facts
   of one problem have the same renamed text, or if a renamed question holds a word that is not a fixed word, a
   variable, a code or a numeral. On the real files it codes 692 symbols in a few seconds. It also writes
   `named_run.json` from `raw/model_answers.jsonl`, which must be complete (every test problem, the same tries
   each, one settings record, one model version, no failed answer): the settings, model version, tries, run seed
   (`--run-seed`, by default the problems' seed, checked against every named request seed) and each problem's and
   try's request seed.
3. With `--renamed`, stage 3 asks the renamed problems with the same seed (the same problem ids, tries, order of
   asking and request seeds as the named run) and writes `raw/model_answers_renamed.jsonl` and
   `model_run_check_renamed.json`; every record's settings carry `"renamed": true`. Before its first request it
   stops unless its settings (`renamed` aside), model version, tries and every request seed equal those in
   `named_run.json`. A start whose answers file or problems file holds the other kind stops.
4. If `raw/model_answers_renamed.jsonl` exists, stage 4 checks that it holds the named answers' problems and tries
   under the same settings but `renamed`, with the named answers' request seeds and the renamed questions of
   `test_problems_renamed.jsonl`, writes `renamed.json` and ends `report.txt` with "Named against
   renamed": per row, the model named and renamed with standard errors, the drop (mean per-problem named minus
   renamed) with its standard error, the shares of paired tries right under both, named only, renamed only and
   neither, the forced share and thinking tokens under each, and the renamed model minus each program. Without
   that file stage 4 writes exactly what it wrote before, and removes a `renamed.json` left from an earlier run.

   **At another thinking allowance.** The renamed questions are longer in tokens, so the renamed side can also be
   run at a larger allowance: stage 3 with `--renamed --other-allowance --thinking-allowance N` lets
   `thinking_allowance`, and only that, differ from `named_run.json` (it must differ), and reads and writes
   `raw/model_answers_renamed_tN.jsonl` and `model_run_check_renamed_tN.json`. For each such file stage 4 makes
   the same checks with `thinking_allowance` equal to N, adds a section "Named against renamed at a thinking
   allowance of N" and writes `renamed_tN.json`; with the plain renamed answers present too, it adds the table
   "Renamed at the two allowances" (the renamed model at each allowance on the same problems and tries, the
   difference at N minus at the named allowance with its standard error, the four shares, forced shares and
   thinking tokens) and writes `renamed_tN_two_allowances.json`. Without such files nothing of that is written.

## Margins of error

As in the cube's README, with "problem" for "state" and rows for distances: every score has the standard error of
its per-problem figures; the model against each program, the mean of the per-problem differences and its
standard error; problem by problem, the count expected if the model's successes were unrelated to the program's,
m x p, with standard error sqrt(m p (1 - p)); the same-wrong-answers figures are across problems with a readable
wrong answer, with `recall` and `surface_symbols` as the controls. Nothing in the code decides what counts as
"above".
