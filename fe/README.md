# The functional-equations experiment

The second puzzle of post 1: one equation an unknown function f satisfies, a goal identity, and 13 allowed
substitutions. A solver is asked for the first move of a shortest proof of the goal; the model is set beside a
ladder of simple programs. Started 2026-11-12.

- `fe_plan.md`: the whole experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- `fe_ladder/`: the code. `identities.py` is the only code that knows how a substitution changes an identity
  (`identity_text.py` writes identities as the question shows them and reads them back); `proof.py` checks
  whether the goal is proved; `moves.py` lists a page's options; `shortest.py` finds the depth and the right
  moves by trying everything (with `PlainSearch`, a plain version for the tests); `families.py` and
  `generator.py` make one candidate problem from a seed and an attempt number; `problems.py` builds the sets;
  `programs/` holds one file per simple program (`common.py` holds the pick, the page score and the guard
  against training on test problems); `question.py`, `model_server.py`, `model_run.py`, `thinking_end.py`,
  `run_check.py` and `answers.py` ask the model, see how its thinking ended, check the run and read its answers;
  `scoring.py` works out every figure, except the same-wrong-moves comparison, which is in `wrong_moves.py`;
  `run_settings.py` checks that every answer was asked under the same settings; `report.py` writes the tables
  and the curve. `model_server.py`, `model_run.py`, `thinking_end.py`, `run_check.py`, `scoring.py`,
  `wrong_moves.py`, `run_settings.py` and `report.py` are the cube experiment's files, adapted.
- `stages/`: one command per stage of `fe_plan.md`. Stages talk only through files in a data folder.
- `probe/`: the thinking-length probe that comes before the model run (the cube's, adapted); not part of the
  package, and no stage uses it.
- `tests/`: tests of every file (`run_settings.py` with the report stage that uses it, in `test_stage_4.py`),
  an end-to-end test, a stand-in model server (its tokenizer and scripted
  replies in `stand_in_replies.py`), small made-up problems (`small_problems.py`, `made_up.py`), saved fixtures
  from the earlier run of this puzzle (`tests/fixtures/`, made by `tests/reference/make_fixtures.py`), and a copy
  of the earlier run's core code used only as a second opinion (`tests/reference/earlier_core.py`). The earlier
  run's lookahead, which never asks whether the goal is proved, is kept for the tests only in
  `tests/score_only_lookahead.py`.
- `data/`: where the stages write, when given `--data data`.

## Set up

Python 3.12 or later.

```
python3 -m pip install -r requirements.txt
```

Nothing else is needed: the search, the proof check and every program are in this folder.

## Run the tests

From this folder:

```
python3 -m pytest                      # everything but the slow test (about 6 minutes on 2 cores)
python3 -m coverage run --source=fe_ladder -m pytest && python3 -m coverage report -m
python3 -m pytest --run-slow tests/test_shortest.py   # the slow test, about 3 minutes
```

The slow test searches the earlier run's 60 saved problems (20 at each of depths 3, 4 and 5) to depth 5 and
checks the depth, the right moves and both counts against the earlier run's.

The fixtures were made once with `python3 -I tests/reference/make_fixtures.py ARCHIVE tests/fixtures`, where
ARCHIVE is the earlier run's folder; the tests read only the saved files.

## Run each stage

Each stage reads from and writes to the folder given as `--data`, prints what it did, and stops with a message
(beginning `STOP`) if one of its checks fails.

1. Build the problems (CPU machine; `--workers` processes solve attempts side by side, taken in order, so the
   result does not depend on how many). The search must first reproduce the earlier run:
   ```
   python3 stages/1_build_problems.py --data data --seed 20261112 --workers 32 \
       --earlier-problems tests/fixtures/earlier_problems.jsonl
   ```
   Writes `test_problems.jsonl` (300 different problems per depth 2 to 5), `train_problems.jsonl` (up to 1,000
   per depth, none the same as a test problem; a depth left short is named in `build_summary.json`) and
   `build_summary.json` (attempts by kind, time taken, and per depth the right moves, the options and how often
   the shortest proof is shorter than the planted one). Each problem is solved with a time limit of
   `--time-limit` seconds (600); more than 1% of attempts out of time stops the build. Every kept problem is
   solved again from its text, and the plain search must agree on the first `--plain-check` (20) test problems
   at each of depths 2 and 3. A tiny trial: `--depths 2,3 --most-moves 3 --test-per-depth 3 --train-per-depth 5`
   (no `--earlier-problems` needed).
2. Run the simple programs (no special machine):
   ```
   python3 stages/2_run_programs.py --data data
   ```
   Writes `program_picks.jsonl` (with each search program's budget: `sequences_examined` for the lookaheads,
   `identities_worked_out` for narrow-and-deep) and `programs_summary.json`,
   prints every program at every depth and the room, and checks guessing and lookahead. The narrow-and-deep
   program breaks ties with the build's seed.
3. First the probe, on one card, before anything else of the model run: 32 training problems (the eight with the
   lowest numbers at each depth), one answer each, no thinking budget, 64,000 tokens per reply. On the pod, with
   the model server started by `probe/start_vllm.sh`:
   ```
   python3 probe/probe.py --train data/train_problems.jsonl --out probe_out [--deadline EPOCH_SECONDS]
   python3 probe/probe.py --train data/train_problems.jsonl --out probe_out --table --think-end-id ID
   ```
   It saves every raw reply and a table of thinking tokens per answer; nothing about right or wrong. The thinking
   allowance is chosen from it.

   Then the model run, every test problem 5 times, exactly as the cube's (see the cube's README for every option,
   the check after the first 100 answers, carrying on, and several servers). `settings.json` holds the sampling
   settings: `{"sampling": {"temperature": ..., "top_p": ..., "top_k": ..., "min_p": ...}, "source": "..."}`.
   ```
   python3 stages/3_model_run.py --print-reasoning-config [--stop-sentence qwen]
   python3 stages/3_model_run.py --data data --base-url http://HOST:PORT [--base-url ...] --model-name NAME \
       --model-version VERSION --settings settings.json --seed SEED --price-per-hour DOLLARS \
       [--cost-ceiling DOLLARS] --thinking-allowance TOKENS [--carry-on] [--retry-failed]
   ```
   The thinking allowance is chosen after the probe (`fe_plan.md`, stage 3); the default is the cube's 8,000.
   `--cost-ceiling` is $300 unless given; the plan's ceiling for this run is given by hand.
   The answer reader takes the last line starting with `MOVE:`; in `(<number>) <substitution>` spaces are ignored
   and the longest listed substitution that fits is taken, so `y = x + y` is never read as `y=x`. After it may
   come the end of the line, a full stop, comma or semicolon, or spaces and then a letter or an opening bracket;
   anything else (an operator or a digit, as in `y=x - y`) makes the answer unreadable.
   Within a try the problems go round the four depths (one at 2, one at 3, one at 4, one at 5, then again), so
   the first 100 answers are 100 different problems, 25 at each depth. Each record keeps the move read (`move`,
   identity number and substitution, or null if unreadable), the option it belongs to (`option`, null if the
   move is not available) and `right`. The check file records `tokens_per_equation`, the tokens one equation
   takes to write out.
4. Report:
   ```
   python3 stages/4_report.py --data data
   ```
   Writes `scores_by_depth.json`, `problem_by_problem.json`, `wrong_moves.json`, `report.txt` and `curve.svg`.
   Beside the cube's tables it gives the share of readable moves that are not available; at each depth, the
   share right among forced answers and among unforced ones, with how many there are of each; and, beside the
   same-wrong-moves figures, how many tries were left out because their move is not available. The budgets table
   gives each lookahead's sequences examined, narrow-and-deep's identities worked out, and, as an upper limit
   only, the most identities the model could have written out in its tokens. It reads only saved
   files, and run twice it writes the same files.

   It reads the settings of every answer, not just the first: if the thinking allowance, the answer
   allowance, the stop sentence, the sampling values or the model version differ between answers, it stops
   and names each setting that differs with every value and how many answers have it
   (`fe_ladder/run_settings.py`), rather than mixing answers asked in different ways under one allowance.

   The thinking-tokens figure at each depth is the mean over the answers whose thinking tokens were counted
   (the server gave token ids). Beside it, `answers_without_thinking_count` says how many answers that did not
   fail lack a count; the budgets table always shows it as a column (0 in the normal case), so the table has
   one shape. The figure is n/a only when no answer at the depth has a count.

## Words used in the files

- A problem's `options` are listed in a fixed order (by the lowest identity number, then the earliest
  substitution, among the moves that give each); `right_moves` and a pick's `weights` refer to options by their
  place in that list, counting from 0.
- Margins of error are as in the cube's README, with "state" read as "problem" and "distance" as "depth".
