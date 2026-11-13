# The cube experiment

A Rubik's cube experiment for a post on telling apart what a language model does when it picks a good next
move: memory, reading the surface, search, or something more. Started 2026-11-12.

- `cube_plan.md`: the whole experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- `cube_ladder/`: the code. `cube.py` is the only code that works out how turns move stickers (`cube_rows.py`
  applies them to many cubes at once); `solver.py` asks the perfect solver; `states.py` builds the states;
  `programs/` holds one file per simple program; `question.py`, `model_server.py`, `model_run.py`,
  `run_check.py` and `answers.py` ask the model, check the run and read its answers; `scoring.py` works out
  every figure; `report.py` writes the tables and the curve.
- `stages/`: one command per stage of `cube_plan.md`. Stages talk only through files in a data folder.
- `tests/`: one test file per code file, an end-to-end test, a stand-in model server and a stand-in solver
  program, saved fixtures (see `tests/fixtures/README.md`) and a copy of the old run's cube model used only
  as a second opinion (`tests/reference/`).
- `data/`: where the stages write, when given `--data data`.

## Set up

Python 3.12 or later (the pinned numpy does not install on 3.11).

```
python3 -m pip install -r requirements.txt
python3 -m pip install --no-deps rubik-solver==0.2.0
```

The perfect solver for stage 1 is Rokicki's nxopt (github.com/rokicki/cube20src at f430921a, built with the
half-turn metric) with its 22.8 GB table `nxopth23b.dat`; the folder holding `nxopt23` and the table is
passed as `--solver-dir`.

## Run the tests

From this folder:

```
python3 -m pytest                      # everything that needs neither the solver nor a model server
python3 -m coverage run --source=cube_ladder -m pytest && python3 -m coverage report -m
python3 -m pytest --run-slow --solver-dir FOLDER tests/test_solver.py   # on a machine with the solver
```

The slow tests check the real solver against the old run's 60 states and against the brute-force solver on
200 cubes within 5 turns.

## Run each stage

Each stage reads from and writes to the folder given as `--data`, prints what it did, and stops with a
message if one of its checks fails.

1. Build the states (CPU machine with the solver). The solver must first reproduce the old run:
   ```
   python3 stages/1_build_states.py --data data --seed SEED --solver-dir FOLDER --threads 32 \
       --old-states tests/fixtures/old_run_states.jsonl
   ```
   Writes `test_states.jsonl` (100 different states per distance 2 to 18), `train_states.jsonl` (up to 1,000
   per distance, none a test state, fewer close to solved where there are few cubes; the counts are in
   `build_summary.json`). A tiny trial without the solver: `--brute-force-scramble 4 --follow-home 2-3
   --as-drawn 4 --test-per-distance 4 --train-per-distance 30`.
2. Run the simple programs (no special machine):
   ```
   python3 stages/2_run_programs.py --data data
   ```
   Writes `program_picks.jsonl` and `programs_summary.json`, prints every program at every distance and the
   room, and checks guessing, lookahead and lookup.
3. The model run, every test state 5 times. `settings.json` holds the sampling settings the model's makers
   recommend for thinking mode and where they were read: `{"sampling": {"temperature": ..., "top_p": ...,
   "top_k": ..., "min_p": ...}, "source": "..."}`.
   ```
   python3 stages/3_model_run.py --data data --base-url http://HOST:PORT --model-name NAME \
       --model-version VERSION --settings settings.json --seed SEED --price-per-hour DOLLARS \
       [--api-key-env VARIABLE] [--workers N] [--stop-sentence qwen] [--carry-on] [--retry-failed]
   ```
   Writes `model_answers.jsonl`, saving each answer as it arrives; the same command carries on after a stop.
   After the first 100 answers the run checks itself and writes `model_run_check.json`: every record complete
   and thinking present on most answers; forced answers readable at least as often as unforced ones less
   `--readable-margin` (0.15); no more than 15% unreadable; projected cost under `--cost-ceiling` ($300). If a
   check fails it stops; after a decision, run again with `--carry-on`. Those 100 answers are real data.

   Thinking gets 8,000 tokens (`--thinking-allowance`) and the answer 200 more on top (`--answer-allowance`).
   If the allowance runs out before a readable answer, the thinking is closed with a stop sentence (for Qwen,
   the one its makers use; `--stop-sentence neutral` for a model with none) and the model continues into its
   answer in the same assistant turn, through vLLM's `continue_final_message`
   (`cube_ladder/model_server.py`, `continuation_request`). **This path has never met the real server: confirm
   it in the run's first 100 answers** (the continuation request is accepted, the answer comes back in a
   readable field, and the stop sentence matches this model version's documentation) before trusting it.

   Each request carries a fixed seed made from the run's seed, the state and the try, so running again sends
   the same requests. It does not always give the same answers: the server's arithmetic can change with
   batching and hardware.
4. Report:
   ```
   python3 stages/4_report.py --data data
   ```
   Writes `scores_by_distance.json`, `state_by_state.json`, `report.txt` and `curve.svg`.

## Margins of error

The report gives standard errors as numbers only; nothing in the code decides what counts as "above".
- Every score (the model's and each program's) at each distance: the sample standard deviation (n - 1 in the
  divisor) of the per-state scores over the square root of the number of states. Room's is the best program's
  (named; on a tie, the first alphabetically).
- The model against each program: the mean of the per-state differences (model minus program, same states) and
  its standard error, worked out the same way from the differences.
- State by state: beside the count of states only the model gets, the count expected if the model's successes
  were unrelated to the program's, m x p (m states the program misses, p the share of states the model gets),
  with standard error sqrt(m p (1 - p)).
- A distance with one state has no standard error (n/a). The curve shows a bar of one standard error above and
  below every point.

These margins reflect the choice of test states only. For the surface readers they do not say what a different
training set would give. With 17 distances, an occasional gap of two standard errors is expected by luck.
