# The cube experiment

A Rubik's cube experiment for a post on telling apart what a language model does when it picks a good next
move: memory, reading the surface, search, or something more. Started 2026-11-12.

- `cube_plan.md`: the whole experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- `cube_ladder/`: the code. `cube.py` is the only code that works out how turns move stickers (`cube_rows.py`
  applies them to many cubes at once); `solver.py` asks the perfect solver; `states.py` builds the states;
  `programs/` holds one file per simple program; `question.py`, `model_server.py`, `model_run.py`,
  `thinking_end.py`, `run_check.py` and `answers.py` ask the model, see how its thinking ended, check the run
  and read its answers; `scoring.py` works out
  every figure, except the same-wrong-turns comparison, which is in `wrong_turns.py`; `run_settings.py`
  checks that every answer was asked under the same settings; `report.py` writes the tables and the curve.
- `stages/`: one command per stage of `cube_plan.md`. Stages talk only through files in a data folder.
- `tests/`: one test file per code file (three for `model_run.py`: the order of asking and several servers are
  in `test_model_run_servers.py`, how answers are saved in `test_model_run_saving.py`; two for
  `thinking_end.py`, on hand-made replies and, in `test_how_thinking_ended.py`, on runs against the stand-in
  server; the budget check apart from the rest of `run_check.py` in `test_budget_check.py`; the figures on
  the model's use of its answers apart from the rest of `scoring.py` in `test_answer_use.py`; and stage 3's
  own work around the run, beyond what `test_stages.py` covers, in `test_stage_3.py` and, for the thinking
  budget, `test_stage_3_budget.py`; `run_settings.py` with the report stage that uses it, in
  `test_stage_4.py`), an end-to-end test, a stand-in model server (its tokenizer and scripted
  replies in `stand_in_replies.py`) and a stand-in solver program, saved fixtures (see `tests/fixtures/README.md`) and a copy of the
  old run's cube model used only as a second opinion (`tests/reference/`).
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
160 cubes 2 to 5 turns from solved.

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
   Each model server is a vLLM server started with the reasoning parser and the end-of-thinking text the run
   records, which stage 3 prints for the chosen `--stop-sentence` (no other argument is needed for this):
   ```
   python3 stages/3_model_run.py --print-reasoning-config [--stop-sentence qwen]
   vllm serve MODEL ... --reasoning-parser qwen3 \
       --reasoning-config "$(python3 stages/3_model_run.py --print-reasoning-config)"
   ```
   Then:
   ```
   python3 stages/3_model_run.py --data data --base-url http://HOST:PORT [--base-url http://HOST2:PORT ...] \
       --model-name NAME --model-version VERSION --settings settings.json --seed SEED --price-per-hour DOLLARS \
       [--api-key-env VARIABLE] [--workers N] [--timeout SECONDS] [--stop-sentence qwen] [--carry-on] \
       [--retry-failed]
   ```
   Writes `model_answers.jsonl`, saving each answer as it arrives; the same command carries on after a stop.

   Order of asking: the first try of every state before the second try of any. Within a try the states go one
   distance after another (a state at 2, one at 3, and so on to 18, then round again), in an order inside each
   distance set by `--seed`; the same seed gives the same order. So the first 100 answers are 100 different
   states, 5 or 6 at each distance. "The first 100 answers" means the first 100 records in the file. If some of
   them failed and the run is started again with `--retry-failed`, the failed records are removed first and
   those same (state, try) pairs are asked again before the check; their new records go to the end of the file,
   so the first 100 records are again those 100 states, now with every answer complete, but they finished at two
   different times.

   Several servers: give `--base-url` once per model server. The questions are spread evenly over them,
   `--workers` (8) requests in flight at each; every record names its `server`, and all go to the one file.
   `--price-per-hour` is the total for all the servers given on this start, not the price of one. One key
   (`--api-key-env`) serves every server. The same address given twice is refused. The token lookups go to the
   first server that answers: one is found for the end-of-thinking token and the end-of-thinking text (in the
   model's tokens) each time questions are asked, and one for all 20 token counts of the check. A server that
   keeps failing gives failed records (ask them again with `--retry-failed`). Each request may take `--timeout`
   seconds (900) and is tried 3 times, so a server that accepts requests and never answers holds each of its
   requests for timeout x attempts (about 45 minutes by default) before it is recorded as failed. Either way a
   failing or hanging server does not hold up the others only in this sense: they keep answering their own share
   at their own pace. The run does not end sooner for it, because it ends only once that server's share has been
   tried too. Starting again with more or fewer servers carries on from what is saved, asking nothing twice: this
   is how cards are added after the check. `--retry-failed` writes the kept records to a new file beside the old
   one and then puts it in the old one's place, so a run stopped during that rewrite loses nothing.

   Starting again asks nothing twice and leaves nothing out: a run stopped and restarted holds the same
   records as an unbroken one. Only the order of lines in the file (the order answers finished in, with more
   than one request in flight) and which server answered a question can differ.

   After the first 100 answers the run checks itself and writes `model_run_check.json`: every record complete
   and thinking present on most answers; forced answers readable at least as often as unforced ones less
   `--readable-margin` (0.15); no more than 15% unreadable; projected cost under `--cost-ceiling` ($300): the
   speed measured on those 100 answers, at `--price-per-hour` as given on the start that makes the check. The
   speed is the number of answers over the time from the first request starting (an answer's `finished_at`
   less its `seconds`) to the last answer finishing. It is measured from the first start, not the first
   finish, because requests sent together also finish together. Answers saved without `seconds` stop the
   check with a plain message. The file and the printout give the number of
   forced and of unforced answers compared; if either is under 10, that comparison is reported as "not tested"
   (`forced_comparison`) and the run carries on, with one exception: 3 to 9 forced answers of which fewer than
   half are readable fail the check (`forced_comparison` still reads "not tested"); with 0, 1 or 2 forced
   answers nothing is judged. Beside the four, the check makes sure the server's thinking budget behaves as
   the run assumes (`budget_check`, its own line in the printout), judging each answer by the allowance it
   was asked with (in its own `settings`), not by this start's. An answer does not fit when the end text is
   found but not at the allowance (the server closing the thinking early or late, or the model writing the
   sentence itself); when there is no end text and the thinking is at or past the allowance plus 8 tokens (a
   server not enforcing the budget); or when its thinking tokens cannot be counted, with the reason: the
   server returned no token ids, or the end-of-thinking marker is not a single token. Thinking that ends by
   itself anywhere under the allowance, even a few tokens under, is healthy. Up to 10 answers that do not fit
   are named, each with why and its counts. The printout and the file also give how many forced answers had
   the end text after the allowance and how many inside it (`end_text_outside_budget_count`,
   `end_text_inside_budget_count`), which says how this server counts its end text. Answers saved before the
   run recorded these fields give a plain "budget not checked" message. If a check fails it stops; after a
   decision, run again with `--carry-on`. Those 100 answers are real data.

   The check is made once. Once `model_run_check.json` says it passed, or that the run was carried on after it
   (`carried_on`), a later start does not make it again and does not rewrite the file; it prints one line saying
   the check was made earlier and carries on. So adding servers later, with a higher total price, does not stop
   the run on a speed that belonged to the earlier servers. A check that failed and was not overridden is made
   again on the next start (the cause may have been put right), unless that start is given `--carry-on`, which
   is then recorded in the file. Besides the figures, the file records `servers`, the servers that gave the
   answers checked, `servers_given`, the servers given on the start that made the check, and `price_per_hour`,
   the total price given then. When the answers checked were saved over two starts (after `--retry-failed`, as
   above), the time between the starts counts in the speed and makes it look slower, and the price given on the
   second start may be for other servers than those that gave most of the answers. Read `servers` and
   `servers_given` beside the projected cost; if the cost check fails for such a reason alone, it is a case for
   `--carry-on`.

   Thinking gets 8,000 tokens (`--thinking-allowance`) and the answer 1,000 more on top (`--answer-allowance`).
   The answer's room is wide because an answer cut off before its `MOVE:` line counts as wrong, and a
   long-winded answer is not what is being measured. There is one request per answer, and no second request
   of any kind: it carries the thinking allowance as vLLM's `thinking_token_budget` and the two allowances
   together as `max_tokens`. The server enforces the budget itself: when the thinking reaches it, the server
   writes the end-of-thinking text it was started with (a blank line, the stop sentence, a line break and
   `</think>`) and the model answers from what it has so far, in the same reply. The stop sentence for Qwen
   is the one its makers give for cutting thinking short in the documentation of the earlier Qwen3 models; it
   is not stated for every version, and the card of the version run here does not mention one.
   `--stop-sentence neutral` gives a fixed neutral sentence for a model whose makers publish none.
   Two things are not documented: whether the end-of-thinking text counts toward `max_tokens` (if it does,
   the answer has some 20 to 30 tokens less), and whether the reply's reasoning field keeps the sentence.

   What each record says about how its thinking ended (worked out in `cube_ladder/thinking_end.py`):
   - `stop_sentence_found_in`: where the server's end-of-thinking text shows: the thinking ends with the stop
     sentence (`reasoning`), the raw completion text has it just before `</think>` (`text`, only if the server
     gives one), or the completion's token ids hold the end text's ids unbroken (`token_ids`). The sentence in
     the middle of the thinking shows nowhere.
   - `thinking_tokens`: every token before `</think>`, counted from the token ids, so for a forced answer it
     includes the server's end text. `thinking_tokens_before_end_text`: the thinking tokens before the end
     text (where the ids show it, the ids before it; where only the reasoning or the raw text shows it,
     `thinking_tokens` less the end text's length; with no end text, all of `thinking_tokens`). So a forced
     answer's thinking is given both with and without the server's end text. Both are empty when thinking
     tokens cannot be counted.
   - `at_allowance`: `thinking_tokens_before_end_text` is within 8 tokens of the allowance the answer was
     asked with, either side (`ALLOWANCE_TOLERANCE`: the server and this code may count the opening marker
     and the boundary token differently by a token or two). It is not documented whether the server counts
     its own end text inside the budget, so with an end text it also holds when the thinking is short of the
     allowance by up to the end text's length plus 8; `end_text_inside_budget` records which case it was
     (empty when not forced).
   - `forced`: the server closed the thinking: the end text is found and it is at the allowance. The stop
     sentence elsewhere (a model can write it itself, after short thinking) does not make an answer forced.
     If thinking tokens cannot be counted, the end text found is all there is to go on, and the check says
     the counts are missing.
   - `cut_off`: the reply ended on the length limit (finish reason "length"; any other reason is not a cut
     off); `cut_off_but_readable`: cut off, but a turn could already be read. A reply cut off with no readable
     answer is saved as it is, unreadable and wrong.

   The report's thinking-tokens figure is the model's own thinking: for a forced answer the tokens before the
   server's end text, for any other all its thinking tokens.

   **This path meets the real server for the first time in the run's first 100 answers.** The check's budget
   line says whether the server closed the thinking where the run expects; read a few forced records by hand
   too (the sentence, where it shows, and whether the answer after it is readable) before trusting the rest.

   Each request carries a fixed seed made from the run's seed, the state and the try, so running again sends
   the same requests. It does not always give the same answers: the server's arithmetic can change with
   batching and hardware.
4. Report:
   ```
   python3 stages/4_report.py --data data
   ```
   Writes `scores_by_distance.json`, `state_by_state.json`, `wrong_turns.json` (the same-wrong-turns
   comparison: for each program and distance, the match rate, the uniform and shuffle figures, the excess and
   the excess over each control, with their standard errors and the counts behind them), `report.txt` and
   `curve.svg`. It reads only saved files, and run twice it writes the same files.

   It reads the settings of every answer, not just the first: if the thinking allowance, the answer
   allowance, the stop sentence, the sampling values or the model version differ between answers, it stops
   and names each setting that differs with every value and how many answers have it
   (`cube_ladder/run_settings.py`), rather than mixing answers asked in different ways under one allowance.

   The thinking-tokens figure at each distance is the mean over the answers whose thinking tokens were
   counted (the server gave token ids). Beside it, `answers_without_thinking_count` says how many answers
   that did not fail lack a count; the budgets table always shows it as a column (0 in the normal case), so
   the table has one shape. The figure is n/a only when no answer at the distance has a count.

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
- Same wrong turns, for each program and distance, over the cubes where the model gave at least one readable
  wrong turn (unreadable and failed tries are left out). Each cube gives one figure of each kind, averaged over
  its wrong tries, and every margin is across those cubes: the five tries on one cube are not independent (they
  share the cube, and the program's pick there), so they are not counted as five separate pieces of evidence.
  - Match rate: the mean over cubes of the weight the program's pick puts on the model's wrong turn, with its
    standard error.
  - Uniform figure: what even guessing among the wrong turns would give on the same cubes. Shuffle figure: the
    model's same wrong turns set against the program's picks on every other test cube at that distance, which
    shows how much matching comes from habits alone (a model or a program that favours certain turns). Both are
    given without a margin, as yardsticks.
  - Excess: match minus shuffle, cube by cube; its standard error is that of the cube-by-cube differences.
  - Excess over each control (both versions of recall and the strict surface reader, programs that do no
    search): this program's excess minus the control's on the same cubes, cube by cube, with the standard
    error of those differences. A control is not set against itself.
  - The number of cubes and of wrong tries behind every row. With fewer than two such cubes there is no
    standard error (n/a); with no other cube at the distance there is no shuffle figure.
- A distance with one state has no standard error (n/a). The curve shows a bar of one standard error above and
  below every point.

These margins reflect the choice of test states only. For the surface readers they do not say what a different
training set would give. With 17 distances, an occasional gap of two standard errors is expected by luck.
