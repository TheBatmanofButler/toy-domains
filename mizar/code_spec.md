# The Mizar experiment: code specification

2026-11-14. This says what the code must do, file by file, so that it can be built and then read by a person. The experiment itself is described in `mizar_plan.md`; read that first. The layout and the rules follow `cube/code_spec.md`. The files that ask the model, score and report are copied from the cube's code. The file that calls the prover is built from the TPTP code's, keeping its safeguards.

## 1. Rules for the code

The cube's nine rules, unchanged: one idea per file (aim for under 200 lines); plain names; every function that produces a number in the report has a test; no locations typed into the code; one place that knows the library's files and one that knows the prover; stages talk only through files in `data/`; same input and seed, same output; fail loudly, nothing silently dropped or skipped; comments say why, and each file starts with two or three sentences on what it is for.

Python 3.12 or later. Allowed libraries: numpy, scikit-learn, pytest, coverage. The prover is E, version 2.6, installed outside the code; where it is and where the library's files are are given as settings.

Two rules taken from the TPTP code:
- **Nothing depends on clock time.** The only time limit is the prover's own cap on computing time per call, and a call that reaches it is recorded as such.
- **The number of workers does not change any output.**

## 2. Words used

- **Fact:** one named statement of the library (a theorem, a lemma, a definition, or one of the kinds Mizar adds on its own).
- **Theorem:** a fact that has a problem file. The **33 articles** are the test articles; every other article is a training article.
- **Cited facts:** the different facts the author's proof of a theorem refers to, from the library's file of references.
- **Background facts:** the facts in a theorem's problem file that are not cited.
- **Usable theorem:** at least two cited facts, at least one of them a theorem or lemma.
- **Held-back fact:** the one cited theorem or lemma drawn for a problem.
- **Given facts:** the other cited facts.
- **Neighbours of a fact, for a theorem:** the theorems and lemmas of the fact's own article that are stated before the theorem, are not cited by it, and do not have the same statement as the fact.
- **Problem:** a usable theorem, its given facts, and 30 options: the held-back fact and 29 neighbours of it, in an order set by the seed.
- **Pick:** what a program answers for one problem: 30 non-negative weights that add up to 1.
- **Score of a pick:** under a key, the total weight on the options that key calls right.
- **Author's key:** the held-back fact is right; the other 29 are wrong.
- **Call:** one run of the prover on a theorem's background and given facts, at most one option, and the theorem.
- **How a call ended, and which endings decide:** as in the TPTP code (`proved`, `clause limit`, `nothing left`, `term cap`, `memory cap`, `time cap`, `unreadable`; the first three decide).
- **Prover's key:** defined only for a problem whose call without an option ended as `clause limit`. An option is right if its call ended as `proved` and the option is among the facts the proof uses.

## 3. Files in `data/`

One JSON object per line unless noted. Bulky raw output (the prover's full output, the model's transcripts) goes under `data/raw/`, which is not tracked by git, as in the cube's folder.

**`theorems.jsonl`**: one line for every theorem of the 33 articles: its name, article, cited facts, and its bin (`not usable`, `too few neighbours`, `qualifies`), with whether it was drawn into the test set.

**`test_problems.jsonl` and `train_problems.jsonl`**

| Field | Meaning |
|---|---|
| `id` | For example `test-0042` |
| `theorem`, `article` | The theorem's name in the library, and its article |
| `statement` | As shown to the solver |
| `given` | Each given fact: name and statement as shown |
| `options` | The 30, in the order shown: name and statement as shown |
| `held_back` | The number of the held-back option |
| `cited_count`, `group` | How many facts the author cited; which of the three article groups |
| `seed` | The build's seed |

Names of facts are kept in these files for the programs and the prover. They are never in the question.

**`prover_calls.jsonl`**: `problem_id`, `option` (a number, or null for the call without an option), how the call ended, its counts, and the facts its proof uses. **`raw/calls/`**: the prover's full output, compressed, one file per problem.

**`prover_key.jsonl`**: per problem: its bin (`proved without an option`, `has right options`, `no option proves it`, `stopped for another reason`), the right options, and the options whose call ended as `proved` without the option being used.

**`limit_probe.json`**: the probe's table and the limit chosen. Not one object per line.

**`program_picks.jsonl`**: `problem_id`, `program`, `weights` (30), `score` (under the author's key).

**`raw/model_answers.jsonl`**: the cube's fields, with `problem_id` in place of `state_id`, and `option` (1 to 30, or null if unreadable) in place of `turn`.

**`scores.json`**, **`problem_by_problem.json`**, **`wrong_answers.json`**, **`second_table.json`**: the tables in the report.

## 4. The code, file by file

### `mizar_ladder/library.py`
The one place that knows the library's files.
- `facts()`: every fact's name and statement, in the library's order. `position(name)`.
- `problem_file(theorem)`: the theorem's statement and the names of the facts in its file, in the file's order.
- `cited(theorem)`: the different facts the author's proof refers to, in order of first mention.
- `mizar_names()`: for each coded symbol, the name the library gives it; the first one listed when there are several.
- `article(name)`, `kind(name)` (theorem, lemma, definition, other), `TEST_ARTICLES` (the 33, written out).
- At start it checks the sha256 of each of the five files against the values in `README.md` and stops if one differs.

Tests: small saved pieces of each real file; `kind` and `article` on hand-made names, including an article whose name contains an underscore; a wrong checksum stops the run. **Slow test (needs the real files):** every cited fact of every theorem is in that theorem's problem file and is stated earlier than it; the counts of facts, theorems and articles equal the ones written in the test.

### `mizar_ladder/statements.py`
Reads one statement in the provers' format.
- `symbols(statement)`: the coded symbols in it. `length(statement)`: the number of symbols and variables.
- `show(statement, names)`: the text the solver sees. Each coded symbol is replaced by its Mizar name; a symbol with no name stays as it is. A two-place symbol whose name has no letters in it is written between its arguments (`(A /\ B)`, `A c= B`). Quantifiers and connectives stay in the provers' notation. Nothing else is changed.
- `same_statement(a, b)`: equal after variables are renamed in order of appearance.

Tests: `show` on ten real statements, each saved with its expected text, including one with a symbol that has no name; `symbols` on hand cases; `same_statement` on pairs that do and do not differ only in variable names.

### `mizar_ladder/problems.py`
Builds the two sets.
- For every theorem of the 33 articles, in the library's order: find its cited facts; if not usable, bin it. Otherwise draw the held-back fact at random from its cited theorems and lemmas, with a generator made from the seed and the theorem's name. If the held-back fact has fewer than 29 neighbours, bin it. Otherwise it qualifies.
- The test set is 300 qualifying theorems drawn at random with the seed. For each, 29 neighbours are drawn at random and the 30 options are put in a random order, both from the seed and the theorem's name.
- The training set is built the same way from the training articles: 5,000 qualifying theorems drawn at random with the seed.

Checks that stop the build: a cited fact missing from the theorem's problem file or stated after the theorem; an option stated after its theorem; a wrong option that the author cited or that has the held-back fact's statement; the held-back fact among the given facts; a theorem of the 33 articles in the training set; a test count that is not exactly 300; a theorem in no bin or in two.

Tests: on a made-up library of four small articles, the bins, the problems and the drawn options are as worked out by hand; same seed, same files; a different seed, different draws; each check above is made to fail once.

### `mizar_ladder/prover.py`
The one place that knows the prover. Built from the TPTP code's `prover.py` and its tests.
- **Kept as they are:** the one fixed environment every prover process is started with (the prover's search changes with the machine's memory settings unless its environment is fixed); the version check and the checksum of the program; the memory cap, the term cap and the cap on computing time; the seven endings and the rule that only three of them decide; taking the lines on time and memory used out of every output; giving the prover its input as a file.
- **Changed, because these problems are full first-order statements and not equations:**
  - `input_text(background_and_given, option, theorem)`: each fact as a `fof(name, axiom, ...)` line with its library name, in the problem file's order; then the option if there is one, under its library name; then the theorem as the conjecture. Nothing else.
  - The search setting is the prover's automatic mode, and the prover is asked to print its proof.
  - The exact lines of the prover's output that each ending rests on are taken again from real outputs on these problems (a proof here ends with the status `Theorem`, and a finished search without a proof with `CounterSatisfiable`). Each rule is written in the file with the words it rests on. None is guessed.
  - `used_facts(output)`: the library names of the facts in the printed proof.
  - The prover prints the name of its input file in a proof. That name differs from run to run, so it is taken out of every output before it is read or kept.
  - Everything about deriving facts and reading equations is left out.

Tests: the TPTP tests for the kept parts, still passing; a stand-in prover that prints its environment shows it is exactly the fixed one; `how_it_ended` on real saved outputs of every ending that can be produced on these problems, and a list in the tests of any that could not; `used_facts` on three real saved proofs; `input_text` for one fixed problem equals a saved copy letter for letter. **Slow tests (need the prover):** the version check; one call run three times at once gives the same ending, counts and used facts.

### `mizar_ladder/settle.py`
Every set of prover calls is made twice, into two folders, and then settled, as the TPTP code does. Whether a call reaches the cap on computing time can change from one run to the next; nothing else may.
- A call is **settled** if both runs give the same ending, counts and used facts. It is **unsettled** if the runs differ and at least one of them ended on the time cap or the memory cap; an unsettled call counts as a call that did not decide. Any other difference stops the stage, naming the problem and the option.
- `settle(first, second, out)` writes the final `prover_calls.jsonl`, with each unsettled call marked, and a `settled.json` naming them. It starts no prover.

Tests: hand-made pairs of runs: identical; one call at the time cap in one run only; a difference in an ending with no cap involved (stops); a difference in used facts only (stops).

### `mizar_ladder/limit_probe.py`
On the first 200 training problems, at each of five limits (250, 500, 1,000, 2,000 and 4,000 processed clauses): the call without an option and the call with the held-back fact. The calls are made twice and settled. Counts, per limit, the problems where the first ended as `clause limit` and the second as `proved` with the held-back fact used. The limit with the highest count is chosen; of equal counts, the smaller limit. Calls that did not decide are counted per limit and shown.

Tests: with a stand-in prover that answers from a table, the table and the chosen limit are as worked out by hand, including a tie.

### `mizar_ladder/prover_key.py`
For each test problem, at the chosen limit: the call without an option, then one call per option; all of it twice, then settled. Writes `prover_calls.jsonl`, `raw/calls/` and `prover_key.jsonl`. Stage 2 refuses to start under a shell limit on computing time or memory, and writes `settings.json`: the seed, the limit, the prover's version and checksum, the fixed environment and the version of the system's C library. The bin is decided in this order: the call without an option ended as `proved` (`proved without an option`); it did not decide, or ended as `nothing left` (`stopped for another reason`); some option is right (`has right options`); every option's call decided (`no option proves it`); otherwise `stopped for another reason`.

Tests: one hand-made case for every line above, and one where an option's call ended as `proved` without the option being used; one worker and four write the same files; a run stopped half-way and started again writes the same files.

### `mizar_ladder/programs/`
Each file has one function, `picks(problems, ...)`, returning one pick per problem. Programs that learn also have `train(training_problems)` and refuse a training set that contains a theorem of the 33 articles. `common.py` holds what they share: making a pick from a set of tied options, and the citation counts.

- **Citation count of a fact:** the number of theorems that cite it, counting every theorem of the library except the 300 theorems of the test set. Theorems of the 33 articles that were not drawn into the test set do count. (A training problem's own theorem is also left out of its counts.) The same rule holds for every count a program takes from the library, including "cited together with a given fact".
- **`guessing.py`**: equal weight on all 30.
- **`recall.py`**: the option with the highest citation count. This is also the lookup rung: a fact is "right in another problem" exactly when another theorem cites it.
- **`options_only.py`**: logistic regression predicting "this option is the held-back one" from the option alone: its length, its number of different symbols, its citation count, how many facts stand between it and the start of its article, and its rank among the 30 on each of those. It is never given the theorem or the given facts.
- **`surface_symbols.py`**: for each option, the sum over the symbols it shares with the theorem of the logarithm of (number of facts in the library divided by number of facts containing the symbol). The pick is the option with the highest sum. Nothing is trained.
- **`surface_trained.py`**: logistic regression predicting "this option is the held-back one" from: everything `options_only` sees; the shared-symbol sum with the theorem and with the given facts; the share of the option's symbols that are in the theorem; the number of other theorems that cite the option together with at least one given fact; the number of facts between the option and the theorem; and the option's rank among the 30 on each. The strength of its one setting is chosen by cross-validation inside the training set, splitting by article.
- **`search.py`**: reads `prover_calls.jsonl`. Equal weight on the options whose call ended as `proved`. If there is none, or the call without an option ended as `proved`, equal weight on all 30. It does not ask whether the option is used in the proof.

Tests: guessing scores 1/30; `recall` and `surface_symbols` on made-up problems worked by hand, including a tie; the citation count leaves out every test theorem and, for a training problem, its own theorem; `options_only` and `surface_trained` trained on a made-up rule learn it and score about chance on shuffled answers; `options_only` raises an error if handed the theorem's statement; `search` on hand-made call records for each of its three cases.

### `mizar_ladder/question.py`
Builds the text the model is shown: one sentence on what the notation is; the theorem; the given facts, numbered G1, G2 and so on; the 30 options, numbered 1 to 30; and the last paragraph as written in `mizar_plan.md`. No names of facts.

Tests: the text for one fixed problem equals a saved copy letter for letter; the text contains no fact name, no article name and nothing that marks the held-back option.

### `mizar_ladder/answers.py`
`read_option(answer_text)`: finds the last line that starts with the label `FACT:` (in any letter case) and returns the number if the rest is a whole number from 1 to 30, with backticks, asterisks and a closing full stop ignored. Otherwise nothing.

Tests: hand-written answers, including two `FACT:` lines, a number out of range, a number written as a word, a number followed by a reason, and no `FACT:` line.

### Copied from the cube: `model_run.py`, `model_server.py`, `thinking_end.py`, `run_check.py`, `run_settings.py`, `scoring.py`, `wrong_turns.py` (here `wrong_answers.py`), `report.py`
Taken from the cube's code as it stands after its run, with their tests. The changes are these and no others: "state" becomes "problem", "turn" becomes "option"; there are 30 options in place of 18 turns; the question comes from `mizar_ladder/question.py` and the answer is read by `mizar_ladder/answers.py`; there are no distances, so every table has one row for all problems and then rows by number of cited facts (2 to 3, 4 to 6, 7 or more) and by article group; the order of asking is the first try of every problem before the second try of any, problems in an order set by the seed; the controls for the same-wrong-answers comparison are `recall` and `surface_symbols`. The report draws a bar for each program and the model in place of the curve against distance.

Tests: the cube's tests for these files, changed in the same way, and still passing.

### `mizar_ladder/second_table.py`
From `raw/model_answers.jsonl`, `program_picks.jsonl` and `prover_key.jsonl`, over the problems in the bin `has right options`:
- every program's and the model's score under the prover's key, and under "right by either key", with standard errors and the model-minus-program differences on the same problems; `search` is left out;
- the same programs' and the model's scores under the author's key on those same problems, so the two tables can be set side by side;
- how often the held-back option is right under the prover's key; how many of the other 29 are, per problem on average; how many option calls ended as `proved` without the option being used;
- the counts of the four prover bins.

Numbers only: no rule about whether the model's position "changed" is in the code.

Tests: a made-up set of ten problems where every figure was worked out by hand.

### `probe/`
The functional-equations probe script (itself the cube's), copied with its test and changed in the same way: the 32 training problems with the lowest numbers, one answer each, no thinking budget, 64,000 tokens per reply. Not part of the package.

### `stages/`
Four short scripts, each one command: `1_build_problems.py`; `2_programs_and_prover.py` (the limit probe, then the prover's key, then the programs); `3_model_run.py`; `4_report.py`. Each runs the checks from `mizar_plan.md` for its stage, and a failed check is printed first. Stage 2 prints first how far `options_only` and `recall` sit above guessing.

### `tests/test_end_to_end.py`
The whole chain on the made-up library, with a stand-in prover that answers from a table and a stand-in model scripted to be always right, always wrong, unreadable, or out of thinking. Both final tables must equal ones worked out by hand.

## 5. What "done" means

As for the cube: all tests pass on a laptop without the prover and without the library's files, and the slow tests pass where both are present; the tests exercise at least 90% of the lines in `mizar_ladder/`, leaving out only the lines that start the real prover and talk to the real model server; `README.md` says where each of the library's files comes from, with its checksum, how to get the pinned prover, and how to set up, test and run each stage; a second reader who has not seen the code being written has read every file, and what they found is fixed.

## 6. Not to be built

Matching wrong options on how often they are cited; random wrong options; a second prover limit after the probe; any study of options that help without being used, beyond the one count; renaming of symbols to meaningless codes; hints; a second prover; the library outside the 33 articles as test problems; any rule in the code for what counts as "above" or as a changed position; any scoring other than right or wrong; saving the model's internal activity; a neural network.

## 7. Where the reusable earlier code is

In this repository: the cube's model-run, check, scoring and report files (`cube/cube_ladder/`), and the TPTP code's prover file and settling file (`tptp/tptp_count/prover.py`, `settle.py`). Each is the starting point for the file named above, changed as listed. Nothing is imported across the three folders at run time.

## 8. Settled points

1. **Recall and lookup are one rung.** With the 33 articles held out of training, "right most often in other problems" and "cited most often" are the same count.
2. **Every count taken from the library leaves out the 300 test theorems,** and, for a training problem, its own theorem. The other theorems of the 33 articles are counted.
3. **How statements are shown.** Mizar's names in place of the coded symbols, two-place symbols with symbolic names written between their arguments, everything else as the provers write it. The saved example in the tests is for reading before the model run.
4. **The prover's search setting** is its automatic mode.
5. **The five limits tried by the probe** are 250, 500, 1,000, 2,000 and 4,000 processed clauses (above a few thousand the cap on terms stops the prover before the limit does), with the TPTP caps (memory 2,000 MB, 60 seconds of computing time) unchanged.
6. **The training set is 5,000 problems.**
7. **The search program counts an option as working whenever the prover succeeds with it,** whether or not the option is in the proof. The prover's key is stricter.
8. **Prover calls are made twice and settled,** as in the TPTP code, and the prover always runs in one fixed environment.
9. **The prover is started with the system's address randomisation turned off,** as well as in the fixed environment. In its automatic mode the prover's search otherwise changes from one run to the next.
10. **The prover is told to read numerals as plain symbols** (`--free-numbers`). Without it it cannot read the background facts of about half the problems.
11. **A call counts as stopped by the clause limit when the clauses it processed are at least the limit:** the automatic mode processes some clauses before the limit starts to count. A call in which the prover left out any given fact before searching does not decide.
