# The cube experiment: code specification

2026-11-12. This says what the code must do, file by file, so that it can be built and then read by a person. The experiment itself is described in `cube_plan.md`; read that first.

## 1. Rules for the code

1. **One idea per file.** Aim for under 200 lines a file. If a file grows past that, split it.
2. **Plain names.** `right_turns`, `distance`, `cube`, `turn`. No abbreviations that need a glossary.
3. **Every function that produces a number in the report has a test.**
4. **No locations typed into the code.** Every stage is told where to read and write.
5. **One cube model.** `cube_ladder/cube.py` is the only code that knows how a turn moves stickers.
6. **Stages talk only through files** in `data/`, in the formats in section 3.
7. **Same input and seed, same output.** Every random choice takes a seed, and the seed is written into the output.
8. **Fail loudly.** A check that does not hold stops the stage with a message saying which state and why. Nothing is silently dropped or skipped.
9. **Comments say why, not what.** Each file starts with two or three sentences on what it is for.

Python 3.12 or later. Allowed libraries: numpy, scikit-learn, pytest, coverage, and `rubik-solver==0.2.0` (for the recall program only). Exact versions go in `requirements.txt`.

## 2. Words used

- **Cube:** a string of 54 letters, one per sticker, faces in the order U R F D L B, nine stickers per face read row by row as in the flat drawing. Letters are the face names. The solved cube is nine U, then nine R, and so on.
- **Turn:** one of 18 names, always in this order: `U U' U2 D D' D2 R R' R2 L L' L2 F F' F2 B B' B2`. `X` is a quarter turn clockwise seen from that face, `X'` the other way, `X2` a half turn.
- **Distance:** the fewest turns needed to solve a cube, counting a half turn as one.
- **Right turn:** a turn that leads to a cube exactly one closer to solved. A cube can have several.
- **Pick:** what a program answers for one cube: 18 non-negative weights that add up to 1, one per turn. A program sure of one turn puts weight 1 on it. A program torn between three puts a third on each.
- **Score of a pick:** the total weight on right turns. So a tie counts as the share of tied turns that are right.

## 3. Files in `data/`

One JSON object per line.

**`test_states.jsonl` and `train_states.jsonl`**

| Field | Meaning |
|---|---|
| `id` | Unique name, for example `test-07-0042` (set, distance, number) |
| `cube` | The 54 letters |
| `distance` | 2 to 18 |
| `right_turns` | List of turn names, never empty |
| `source_cube` | The random cube this state came from |
| `source_distance` | That random cube's distance |
| `seed` | The seed of the build |

**`program_picks.jsonl`**: `state_id`, `program` (for example `lookahead_2`), `weights` (18 numbers), `score`.

**`model_answers.jsonl`**: `state_id`, `try` (1 to 5), `question`, `thinking`, `answer_text`, `turn` (a turn name, or null if unreadable), `right` (true or false), `forced` (true if the thinking allowance ran out), `thinking_tokens`, `model_version`, `settings`.

**`scores_by_distance.json`** and **`state_by_state.json`**: the tables in the report.

## 4. The code, file by file

### `cube_ladder/cube.py`
(Faster forms of the turns and the two counts, working on many cubes at once, are in `cube_ladder/cube_rows.py`. They read the turn tables from `cube.py` and define no turns of their own.)
The cube and its turns. Nothing else in the code moves stickers.
- `SOLVED`, `TURNS`.
- `apply_turn(cube, turn)`, `apply_turns(cube, turns)`, `inverse_turn(turn)`.
- `is_valid(cube)`: true only for cubes that can be reached from solved (right pieces, corner twists add up, edge flips add up, swaps balance).
- `random_cube(rng)`: a valid cube drawn so that every valid cube is equally likely.
- `pieces_in_place(cube)` (0 to 20) and `stickers_in_place(cube)` (0 to 48, centres not counted).

Tests: every turn four times changes nothing; a turn then its inverse changes nothing; `R U R' U'` six times changes nothing; the number of different cubes exactly 1, 2, 3 and 4 turns from solved is 18, 243, 3,240 and 43,239; solved scores 20 and 48; three hand-built impossible cubes (one flipped edge, one twisted corner, two swapped pieces) are invalid; 1,000 random cubes are valid; agreement with the old run's cube model on 1,000 random turn sequences (the old model is used in tests only).

### `cube_ladder/solver.py`
Asks the perfect solver. The solver is an outside program (Rokicki's nxopt at source version f430921a, with its 22.8 GB table); its location is passed in.
- `distances(cubes)`: for each cube, its distance and one shortest solution.
- `right_turns(cube, distance)`: applies each of the 18 turns and asks whether the result can be solved in `distance - 1` turns.
- Every solution the solver returns is applied with `cube.py` and must reach `SOLVED` in the stated number of turns, or the call fails.
- `BruteForceSolver`: the same two functions, done by trying everything, for cubes within 5 turns of solved. Used by the tests and by nothing else.

Tests: on every cube within 3 turns of solved and 500 cubes at 4 and 5, `BruteForceSolver` agrees with a plain search written inside the test; the wrapper's reading of the solver's output is tested on saved output; a wrong solution is rejected. **Slow test, needs the real solver:** distance and right turns for 60 states from the old run equal the archive, and the real solver agrees with `BruteForceSolver` on 160 cubes 2 to 5 turns from solved (40 at each).

### `cube_ladder/states.py`
Builds the two sets.
- Draw random cubes one at a time and solve each.
- A cube at distance 17 or 18 fills an open place at that distance as it is.
- Any other cube, or one whose own distance is already full, fills an open place at a distance from 2 to 16: follow its shortest solution until it is that far from solved, and use that state. Places are filled in a fixed rotating order so every distance fills at the same rate.
- Each random cube is used once, in one set. Then find the state's right turns.
- Distance 1 is not used.
- **All test states are different.** A state already in the test set is not added again.
- **The training set never contains a test state,** and its own states are all different. The test set is filled first.
- Stop when every distance from 2 to 18 has 100 test states and 1,000 training states. Close to solved there are few cubes (243 at distance 2, 3,240 at distance 3), so a distance's training set is also complete once a set number of fresh random cubes in a row (passed in, default 2,000) have produced no new state for it; the build then records how many training states that distance has.

Checks that stop the build: a state that is not valid; a state whose measured distance is not the one intended; an empty list of right turns; the same cube in both sets; the same cube twice in one set; a random cube used twice; a test count that is not exactly 100 at any distance from 2 to 18; a training count above 1,000.

Tests: with `BruteForceSolver` and cubes scrambled 5 turns, the build produces the right counts, every recorded right turn leads one closer, no state repeats within or across the two sets, a distance with too few cubes ends with a smaller training set and says so, and the same seed gives the same files.

### `cube_ladder/programs/`
Each file has one function, `picks(cubes, ...)`, returning one pick per cube. Programs that learn also have `train(training_states)`.

- **`guessing.py`**: equal weight on all 18 turns.
- **`lookup.py`**: counts, over the whole training set with all distances together, how often each turn is right, and always picks the most frequent one. This is also the reader that sees only the options, because the options never change.
- **`recall.py`**: runs the scripted speedsolving method from `rubik-solver` and picks its first turn, in two versions: first layer built on the top face, and on the bottom face. The method's moves are converted to the 18 turns. If the method fails on a cube, the pick is equal weight on all turns, and the number of failures is reported.
- **`surface_strict.py`**: logistic regression with 18 possible answers. Input: 324 yes-or-no facts, one for each sticker position and colour. It never sees the result of a turn. When a training cube has several right turns, each counts in proportion. The strength of its one setting is chosen by cross-validation inside the training set. Trained on all distances mixed, because a reader is not told how far a cube is from solved.
- **`surface_relaxed.py`**: the old run's reader. For each cube and turn: counts describing the cube now, the same counts after the turn, their differences, which face, and which kind of turn. Logistic regression predicts "this turn is right"; the pick is the turn with the highest value. Trained on all distances mixed.
- **`lookahead.py`**: `picks(cubes, depth)` for depth 1, 2, 3. Try every sequence of `depth` turns that never turns the same face twice running. If any sequence reaches the solved cube, at `depth` turns or fewer, the shortest such sequences win. Otherwise the winners are the sequences whose end cube has the most pieces in place, with stickers in place breaking ties. The pick is equal weight on the first turns of the winners.

Tests: guessing scores right turns divided by 18; on every cube within 3 turns of solved, lookahead of depth 3 scores 1 and lookahead of depth k scores 1 on every cube within k turns; lookahead on five hand-worked cubes; `surface_strict` trained on a made-up rule (a planted sticker decides the turn) learns it and scores about chance on shuffled answers; `surface_relaxed` reproduces the old run's feature values on 50 old states; neither surface reader is ever given a test state in training (the code refuses); `lookup` on a made-up training set; `recall`'s converted moves solve the cube when all of them are applied.

### `cube_ladder/question.py`
Builds the text the model is shown: the old layout (role line, colour scheme, meaning of each turn, the 18 allowed turns, the flat drawing, the sticker string), ending with the rule as written in `cube_plan.md`.

Tests: the text for one fixed cube equals a saved copy letter for letter; everything before the last paragraph equals the old run's text for the same cube; the text contains no distance and no right turn.

### `cube_ladder/answers.py`
`read_turn(answer_text)`: finds the last line that starts with the label `MOVE:` (the label in any letter case) and returns the turn if it is exactly one of the 18 names, otherwise nothing. A lower-case turn is not read.

Tests: hand-written answers, including two `MOVE:` lines, a label in lower case and in title case, a lower-case turn, a stray `MOVE:` in later prose, extra spaces, a turn that does not exist, and no `MOVE:` line.

### `cube_ladder/model_run.py`
(The exact request sent to the model server, and the text the server must be started with to close cut-off thinking, are kept apart in `cube_ladder/model_server.py`. Working out how a reply's thinking ended is in `cube_ladder/thinking_end.py`.)
Sends each question to a model server the given number of times and saves every answer.
- **Order of asking.** The first try of every state before the second try of any. Within a try, states are taken one distance after another (one at the smallest distance, one at the next, and so on, then round again), in an order inside each distance set by the run's seed. So the first answers of a run are different states spread evenly over the distances, and the same seed gives the same order.
- **Several servers.** The run may be given more than one model server. Questions are spread evenly over them, each server gets the same number of requests at a time, and every record says which server answered. All records go to one file. Starting again with more (or fewer) servers carries on from what is saved.
- Settings (temperature and its companions) are passed in and written into every record.
- Thinking allowance of 8,000 tokens, and an allowance for the answer on top (1,000). The model server enforces the thinking allowance (vLLM's `thinking_token_budget`, sent with every request): at 8,000 thinking tokens the server itself writes the end-of-thinking text it was started with, which carries the stop sentence, and the model goes on to its answer in the same reply. There is one request per answer and no second request of any kind. The stop sentence is a setting (the Qwen sentence, or a neutral one for models with none); `model_server.py` gives the exact end-of-thinking text for it, so the server can be started with the same text the run records. The record says where the server's end-of-thinking text shows in the reply (`stop_sentence_found_in`: the end of the returned thinking, the completion's token ids, or a raw completion text), how many thinking tokens came before that end text (`thinking_tokens_before_end_text`), and whether that count is at the allowance (`at_allowance`): within 8 tokens either side, or short of it by no more than the end text's own length plus 8, since it is not documented whether the server counts its end text inside the budget (`end_text_inside_budget` records which). A record is `forced` when both hold: the end text is there, and it came at the allowance. The stop sentence showing up anywhere else (a model can write it itself) does not make an answer forced. `cut_off` says the reply ended on the length limit. A reply cut off by the total limit with no readable answer is saved as it is, unreadable and wrong, and marked as cut off.
- Saves after every answer, and on restart skips what is already saved.
- A failed request is retried a fixed number of times, then recorded as failed. It is never silently dropped.

Tests, all with a stand-in server that answers by script: five tries give five records; every request carries the thinking allowance as the server's thinking budget; a scripted "ran out of thinking" reply, whose thinking ends with the stop sentence, gets the `forced` mark and no second request is sent; a reply cut off with no answer is saved as unreadable and marked cut off; an unreadable answer is saved with `turn` empty and `right` false; stopping halfway and restarting gives the same set of records as an unbroken run (and, with one server and one request at a time, the same file); a server error is retried and then recorded; the first answers asked are different states spread evenly over the distances, and the same seed gives the same order; with two stand-in servers each gets its share of the questions, every record names its server, and a restart with a different number of servers asks nothing twice.

### `cube_ladder/scoring.py`
- A state's model score: the share of its five tries that are right.
- A distance's score, for the model and each program: the average over its states.
- Room at a distance: one minus the best program.
- Share of unreadable answers and share of forced answers, by distance. Thinking tokens used, by distance: the model's own thinking, so for a forced answer the tokens before the server's end text.
- State by state: the model "gets" a state when at least three of five tries are right; a program "gets" a state when its score there is more than one half (the same bar: more than half). For each program and distance: both, only the model, only the program, neither, the count of "only the model" expected if the model were guessing, and the count expected if the model's successes were unrelated to the program's.
- Standard errors, as numbers only (no rule about what counts as "above" is in the code): of every score at every distance; of the model-minus-program difference on the same states; of room (the best program's); and of the only-the-model count against the count expected if unrelated. A distance with one state has none.

Tests: a made-up set of ten states where every figure was worked out by hand and written into the test.

- Same wrong turns, for each program and distance (in its own file, `cube_ladder/wrong_turns.py`, if `scoring.py` would pass 200 lines):
  - A wrong try is a try whose answer reads as one of the 18 turns and that turn is not right. Unreadable and failed tries are left out.
  - A cube's match value is the average, over its wrong tries, of the weight the program's pick puts on the model's turn. The distance's match rate is the average over cubes that have a wrong try; its standard error is worked out across those cubes.
  - Uniform figure: for each such cube, the program's total weight on wrong turns divided by the number of wrong turns, averaged the same way.
  - Shuffle figure: for each wrong try, the average weight the program puts on that same turn over all the other test cubes at that distance; then averaged by cube as above. No random numbers are used.
  - The excess (match rate minus shuffle figure) with its standard error from the cube-by-cube differences, and, for each control program (both recall versions and the strict surface reader), the difference between this program's excess and the control's excess on the same cubes, with its standard error.
  - Also given: the number of wrong tries and of cubes behind each figure. A distance with fewer than two such cubes has no standard error.
  - Numbers only: no rule about what counts as a resemblance is in the code.
  Tests: a made-up set where every figure is worked out by hand, including a program with a three-way tie, a cube whose every try is right (left out), an unreadable try, and a distance with one cube.

### `cube_ladder/report.py`
Writes the tables as text, including the same-wrong-turns table, and draws the curve: score against distance for the model and every program, with a bar of one standard error above and below every point. No arithmetic happens here that is not in `scoring.py`.

### `stages/`
Four short scripts, each one command: `1_build_states.py`, `2_run_programs.py`, `3_model_run.py`, `4_report.py`. Each reads its inputs from and writes its outputs to the folder it is given, prints what it did, and runs the checks from `cube_plan.md` for its stage. A failed check is printed first.

`3_model_run.py` has no separate pilot. It asks the first 100 answers (100 different states spread over the distances, because of the order of asking), runs the four checks in `cube_ladder/run_check.py` (every record complete and thinking present on most answers; forced answers readable about as often as unforced ones; no more than 15% unreadable; projected cost under the ceiling), writes them to a file with the measured speed, and carries on only if all hold. The check file gives the number of forced and of unforced answers compared; if either is under 10 the comparison is reported as not tested (in the printed output and in the file), and the run carries on, with one exception: when there are 3 to 9 forced answers and fewer than half of them are readable, that is a failed check and the run stops. The check also fails if the server's budget is not behaving as the run assumes, judged against the allowance each answer was asked with: the end text found away from the allowance (the server closing the thinking early, or the model writing the sentence itself); thinking 8 or more tokens past the allowance with no end text; or thinking tokens that cannot be counted (and the message says why: no token ids, or no single end-of-thinking token). `--print-reasoning-config` prints the setting the server must be started with. The check is made once: it looks at exactly the first 100 answers, all of them complete (with `--retry-failed`, failed requests among them are asked again first; without it, they fail the check as incomplete), and its file records the servers and the total price at that moment. Once the check has passed, or has been overridden with `--carry-on`, a later start does not make it again and does not overwrite its file, because by then the servers and the price may have changed and the speed measured earlier would no longer match them.

### `tests/test_end_to_end.py`
The whole chain on a tiny set: cubes scrambled up to 4 turns, `BruteForceSolver`, and a stand-in model that is scripted to be always right, always wrong, unreadable, or out of thinking. The final table must equal one worked out by hand.

## 5. What "done" means

- All tests pass on a laptop without the solver; the slow tests pass on a machine with it.
- The tests exercise at least 90% of the lines in `cube_ladder/`, measured with `coverage`, leaving out only the lines that talk to the real solver and the real model server.
- `README.md` says how to set up, how to run the tests, and how to run each stage.
- A second reader, who has not seen the code being written, has read every file and listed anything unclear or untested, and those points are fixed.

## 6. Not to be built

A second cube size; sequences of turns as answers; comparing two cubes; rotated drawings; any rule in the code for what counts as "above"; any scoring other than right or wrong; saving the model's internal activity; a neural network.

## 7. Where the reusable old code is

In the archive of the earlier cube run (kept outside this repository): the solver wrapper, the question layout, the answer reader, the old surface features, the conversion of method moves to the 18 turns, and a faster cube model for use in tests. Each is to be moved into the file named above, renamed to the words in section 2, and given tests. Nothing is imported from the archive at run time.
