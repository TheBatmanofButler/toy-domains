# The functional-equations experiment: code specification

2026-11-12. This says what the code must do, file by file, so that it can be built and then read by a person. The experiment itself is described in `fe_plan.md`; read that first. The layout and the rules follow `cube/code_spec.md`, and the files that ask the model, score and report are copied from the cube's code and changed as little as possible.

## 1. Rules for the code

The cube's nine rules, unchanged: one idea per file (aim for under 200 lines); plain names; every function that produces a number in the report has a test; no locations typed into the code; one place that knows the puzzle; stages talk only through files in `data/`; same input and seed, same output; fail loudly, nothing silently dropped or skipped; comments say why, and each file starts with two or three sentences on what it is for.

Python 3.12 or later. Allowed libraries: numpy, scikit-learn, pytest, coverage. All arithmetic on identities is exact (Python's `fractions`).

## 2. Words used

- **Term:** `f(...)` of a linear expression in x and y with rational numbers (for example `f(2x + y)`, `f(0)`, `f(-x)`), or a power product of x and y, or the constant 1.
- **Identity:** a sum of terms with rational coefficients that equals zero for all rational x and y. It is always held in one fixed form: everything on one side, zero coefficients dropped, scaled so the first term in a fixed order has coefficient 1, and, if y is the only variable present, y renamed to x.
- **Substitution:** one of 13 names, always in this order: `x=0, y=0`; `y=0`; `x=0`; `y=x`; `y=-x`; `swap x,y`; `y=1`; `x=x+y, y=-y`; `y=x+y`; `x=1`; `x=-x`; `y=-y`; `x=x-y, y=x+y`. The ones with two parts are applied at once.
- **Page:** the numbered identities so far. A problem starts with a page of one identity, the equation.
- **Move:** an identity number and a substitution. Its result is a new identity.
- **Option:** all the moves on a page that give the same result count as one option. A move is not available if its result is empty (0 = 0), is already on the page, or equals the identity it was applied to.
- **Proved:** the goal is a combination, with rational coefficients, of the identities on the page, each term treated as its own unknown.
- **Depth:** the fewest moves after which the goal is proved.
- **Right move:** an option that is the first move of some proof of exactly `depth` moves.
- **Pick:** what a program answers for one problem: non-negative weights over the options that add up to 1.
- **Score of a pick:** the total weight on right moves.
- **Same problem:** two problems are the same if one becomes the other by swapping x and y, or by scaling f, or both.

## 3. Files in `data/`

One JSON object per line.

**`test_problems.jsonl` and `train_problems.jsonl`**

| Field | Meaning |
|---|---|
| `id` | Unique name, for example `test-4-0042` (set, depth, number) |
| `equation`, `goal` | As text, in the form the question shows |
| `depth` | 2 to 5 |
| `options` | Each option: its result as text, and the moves that give it |
| `right_moves` | The numbers of the right options, never empty |
| `proofs`, `sequences` | How many move sequences of length `depth` prove the goal, and how many there are in all |
| `family` | Which of the seven families the equation was built from |
| `planted` | The two chains of substitutions used to build the goal. Never shown to any solver |
| `attempt`, `seed` | Which attempt of the build this was, and the build's seed |

**`program_picks.jsonl`**: `problem_id`, `program` (for example `lookahead_2`), `weights` (one per option), `score`.

**`model_answers.jsonl`**: the cube's fields, with `problem_id` in place of `state_id`, and in place of `turn`: `move` (identity number and substitution, or null if unreadable), `option` (the option that move belongs to, or null if the move is not available), `right`.

**`scores_by_depth.json`**, **`problem_by_problem.json`**, **`wrong_moves.json`**: the tables in the report.

## 4. The code, file by file

### `fe_ladder/identities.py`
Identities and substitutions. Nothing else in the code knows how a substitution changes an identity.
- `SUBSTITUTIONS`, `read_identity(text)`, `write_identity(identity)`.
- `apply(identity, substitution)`: the result in the fixed form, or nothing if it is empty.
- `terms(identity)`.
- `problem_key(equation, goal)`: equal for two problems exactly when they are the same problem.

Tests: each substitution on identities worked by hand; `swap x,y`, `x=-x` and `y=-y` applied twice change nothing; writing then reading an identity gives it back; scaling an identity does not change its fixed form; for a fixed test function (a cubic), an identity that the function satisfies at 50 random rational points is still satisfied after any substitution; agreement with the earlier run's code on 1,000 random identities and substitutions (the earlier code is used in tests only); `problem_key` on hand-made pairs that are and are not the same.

### `fe_ladder/proof.py`
`is_proved(page, goal)`: exact elimination over fractions.

Tests: hand cases (the goal is on the page; the goal is a combination of two identities; the goal has a term found nowhere on the page); random combinations of a page's identities are proved; agreement with the earlier run's code on 500 random pages.

### `fe_ladder/moves.py`
`options(page)`: the available options of a page, in a fixed order (by the lowest identity number, then the earliest substitution, among the moves that give each result).

Tests: hand cases, including two moves with the same result becoming one option, and a move whose result is already on the page.

### `fe_ladder/shortest.py`
Finds the depth and the right moves by trying everything.
- `solve(equation, goal, most_moves=5, time_limit)`: the depth, the right options, and the counts of proofs and of sequences. The order in which moves are made does not change the page, so pages reached by the same moves in another order are searched once; the counts still count every order.
- Outcomes other than a depth are named and returned, never hidden: already proved, deeper than `most_moves`, out of time.
- `PlainSearch`: the same answers by trying every sequence in order, for depths up to 3. Used by the tests and by nothing else.

Tests: `solve` agrees with `PlainSearch` on 300 small problems; a depth-3 problem worked by hand and written into the test; a problem that is already proved; a time limit that is reached is reported as such. **Slow test:** depth, right moves and both counts for 60 problems of the earlier run (20 at each of depths 3, 4 and 5) equal the archive.

### `fe_ladder/generator.py`
Makes one candidate problem from a seed and an attempt number: picks a family, builds an equation that is true for it, then builds a goal from two chains of random substitutions, as described in the plan.
- Every equation and goal is checked to hold for its family: exactly, and at 20 random rational points.

Tests: same seed and attempt, same problem; every equation and goal made in 500 attempts holds for a function of its family at random points; with the earlier run's seed, 50 attempts whose problems are in the earlier run's files give those equations and goals exactly.

### `fe_ladder/problems.py`
Builds the two sets.
- Take attempts in order, 0, 1, 2 and so on. Solve each.
- An attempt at depth 2 to 5 fills an open place at its depth: test places first, then training places. An attempt whose problem is the same as one already taken, in either set, is passed over.
- Attempts that are already proved, at depth 1, deeper than 5, or out of time are counted by kind and not used.
- Stop when every depth has 300 test problems and 1,000 training problems, or when a given number of attempts has been made; a depth short of training problems then records how many it has.

Checks that stop the build: a problem whose depth, solved again, is not the one recorded; an empty list of right moves; the same problem twice in one set or in both; a test count that is not exactly 300 at any depth; a training count above 1,000; more than 1% of attempts out of time.

Tests: with a small target (5 test and 10 training per depth), the build gives the right counts, no problem repeats within or across the sets, a depth with too few problems says so, the counts by kind add up to the attempts made, and the same seed gives the same files.

### `fe_ladder/programs/`
Each file has one function, `picks(problems, ...)`, returning one pick per problem. Programs that learn also have `train(training_problems)`. `common.py` holds what they share: making a pick from a set of tied options, and the page score.

- **The page score:** the number of the goal's terms that are present on the page, less the number of terms added since the equation that belong to neither the goal nor the equation; ties between pages go to the page with fewer different terms. This is the earlier run's score.
- **`guessing.py`**: equal weight on every option.
- **`lookup.py`**: counts, over the whole training set, how often each of the 13 substitutions applied to the equation is a right move, and picks the available one with the highest count. This is also the reader that sees only the options.
- **`recall.py`**: the first substitution in the list whose move on the equation is available.
- **`surface_strict.py`**: logistic regression with 13 possible answers, one per substitution. Input: yes-or-no facts about what is on the page before any move: for each of the 40 commonest kinds of term in the training set, whether it is in the equation and whether it is in the goal; and the number of terms in each. It never sees the result of a substitution. When a problem has several right moves, each counts in proportion. Its weights are spread over the options that those substitutions give. The strength of its one setting is chosen by cross-validation inside the training set. Trained on all depths mixed.
- **`surface_relaxed.py`**: the earlier run's reader. For each option: which substitution, the number of terms on the page before and after, how many of the goal's terms are present after, whether the substitution brings in a constant, and how many new terms of each kind the result has. Logistic regression predicts "this move is right"; the pick is the option with the highest value. Trained on all depths mixed.
- **`lookahead.py`**: `picks(problems, depth)` for depth 1, 2, 3. Try every sequence of up to `depth` moves. If any sequence proves the goal, the shortest such sequences win. Otherwise the winners are the sequences of `depth` moves whose page has the best page score. The pick is equal weight on the first moves of the winners.
- **`narrow_deep.py`**: `picks(problems, paths=3, most_moves=5)`. Start with the page of the equation. At each step, from every page kept, work out every option; if one proves the goal, stop and pick its path's first move (equal weight if several paths prove it at the same step); otherwise keep the `paths` pages with the best page score and go on. After `most_moves` steps with no proof, pick the first move of the best-scoring page. Pages tied for the last place kept are chosen among at random, with a random number generator made from the run's seed and the problem's id, so the same seed gives the same picks and no substitution is favoured for its place in the list.

Tests: guessing scores right moves divided by options; on 200 problems of depth up to 3, lookahead of depth k scores 1 on every problem of depth k or less; lookahead and narrow-and-deep on problems worked by hand, including one where narrow-and-deep is led astray; `surface_strict` trained on a made-up rule (a planted term decides the substitution) learns it and scores about chance on shuffled answers; `surface_relaxed` reproduces the earlier run's input values on 50 earlier problems; neither surface reader is ever given a test problem in training (the code refuses); `lookup` and `recall` on made-up sets. **In the tests only:** the earlier run's lookahead, which uses the page score alone and never asks whether the goal is proved; it must give the earlier run's score on each of the 60 earlier problems.

### `fe_ladder/question.py`
Builds the text the model is shown: the earlier layout (the sentence about f, the numbered equation, the goal, what counts as proved, the 13 substitutions with their numbers, the note on two-part substitutions, how to write a substitution), ending with the rule as written in `fe_plan.md`.

Tests: the text for one fixed problem equals a saved copy letter for letter; everything before the last paragraph equals the earlier run's text for the same problem; the text contains no depth, no right move and nothing from `planted`.

### `fe_ladder/answers.py`
`read_move(answer_text)`: finds the last line that starts with the label `MOVE:` (the label in any letter case) and returns the identity number and the substitution if the rest is `(<number>) <substitution>` with the substitution exactly one of the 13 as listed, spaces aside. Otherwise nothing. The move is then looked up among the problem's options; a readable move that is not available is recorded as such.

Tests: hand-written answers, including two `MOVE:` lines, a label in lower case, missing brackets, a substitution written with and without spaces, a substitution given by its number only, one that does not exist, an identity number that is not on the page, and no `MOVE:` line.

### Copied from the cube: `model_run.py`, `model_server.py`, `thinking_end.py`, `run_check.py`, `scoring.py`, `wrong_turns.py` (here `wrong_moves.py`), `report.py`
Taken from the cube's code as it stood on 2026-11-12 after its probe, with their tests. The changes are these and no others: "state" becomes "problem", "distance" becomes "depth", "turn" becomes "move"; the question comes from `fe_ladder/question.py` and the answer is read by `fe_ladder/answers.py`; the options differ from problem to problem, so weights are matched to options by number; the order of asking goes round the four depths; the controls for the wrong-moves comparison are `recall` and `surface_strict`. One addition to `scoring.py` and the report: the share right among forced answers and among unforced ones, at each depth, with how many there are of each.

Tests: the cube's tests for these files, changed in the same way, and still passing; the hand-worked table for the added figures.

### `stages/`
Four short scripts, each one command: `1_build_problems.py`, `2_run_programs.py`, `3_model_run.py`, `4_report.py`, each running the checks from `fe_plan.md` for its stage. A failed check is printed first.

### `tests/test_end_to_end.py`
The whole chain on a tiny set: a handful of problems of depth 2 and 3, `PlainSearch`, and a stand-in model that is scripted to be always right, always wrong, unreadable, not available, or out of thinking. The final table must equal one worked out by hand.

## 5. What "done" means

As for the cube: all tests pass on a laptop, and the slow tests pass where the earlier run's files are present; the tests exercise at least 90% of the lines in `fe_ladder/`, leaving out only the lines that talk to the real model server; `README.md` says how to set up, test and run each stage; a second reader who has not seen the code being written has read every file, and what they found is fixed.

## 6. Not to be built

Hints; answers that give a whole proof; problems that start part-way through a proof; comparing two pages; the 3%-to-40% filter; the earlier run's extra sets; any rule in the code for what counts as "above" or as a resemblance; any scoring other than right or wrong; saving the model's internal activity; a neural network; anything that reads the algebra in the model's thinking.

## 7. Where the reusable earlier code is

In the archive of the earlier run of this puzzle (kept outside this repository): identities, substitutions and the fixed form; the proof check; the search over pages; the generator in its second version; the page score, the lookahead and the surface reader's inputs; the question layout; the answer reader. Each is to be moved into the file named above, renamed to the words in section 2, and given tests. Nothing is imported from the archive at run time.

## 8. Settled points

1. **The answer reader is strict,** as the cube's is: the substitution must be spelled as in the list, spaces aside. (All 900 first-move answers saved from the earlier run are read correctly by this rule.)
2. **The strict surface reader** is given which of the 40 commonest kinds of term are in the equation and in the goal.
3. **Ties in the narrow-and-deep program** are broken at random from the run's seed.
4. **The time limit for solving one problem** is 10 minutes.
5. **The copied files** are built last, from the cube's code as it stood on 2026-11-12 after its probe. Any later fix to those files in the cube is brought across as a separate, listed change.
