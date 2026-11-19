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
- **Theorem:** a fact that has a problem file. Every problem, test or training, is built from a theorem of the **33 articles**.
- **Cited facts:** the different facts the author's proof of a theorem refers to, from the library's file of references.
- **Background facts:** the facts in a theorem's problem file that are not cited.
- **Usable theorem:** at least two cited facts, at least one of them a theorem or lemma that can be held back (see below).
- **Held-back fact:** the one cited theorem or lemma drawn for a problem.
- **Given facts:** the other cited facts.
- **Neighbours of a fact, for a theorem:** the theorems and lemmas of the fact's own article that are stated before the theorem, are not cited by it, and do not have the same statement as the fact, as the theorem, or as any fact the theorem cites. Of several such facts with one statement, only the first in the library's order is a neighbour. "The same statement" is judged on the statement itself and on the text the solver is shown, and in both cases two statements that differ only in the names of their variables, or in the order in which a quantifier lists its variables, are the same. Quantifiers of one kind nested directly inside one another (the library's way of writing "for A, B, C") count as one list. (Mizar gives one name to several symbols, so two different statements can be shown as the same text.) So no two options of a problem read the same, and no option reads the same as a given fact or the theorem.
- **Which cited fact can be held back:** a cited theorem or lemma whose statement, and whose shown text, differ from those of every other fact the theorem cites and from the theorem's.
- **Problem:** a usable theorem, its given facts, and 30 options: the held-back fact and 29 neighbours of it, in an order set by the seed.
- **Pick:** what a program answers for one problem: 30 non-negative weights that add up to 1.
- **Score of a pick:** under a key, the total weight on the options that key calls right.
- **Author's key:** the held-back fact is right; the other 29 are wrong.
- **Call:** one run of the prover on a theorem's background and given facts, at most one option, and the theorem.
- **How a call ended, and which endings decide:** as in the TPTP code (`proved`, `clause limit`, `nothing left`, `term cap`, `memory cap`, `time cap`, `unreadable`; the first three decide).
- **Does not prove:** a call that ended as `clause limit` or as `nothing left`. Here `nothing left` is an ordinary verdict: the prover was given fewer facts than the author used, finished its search and found no proof.
- **Prover's key:** defined only for a problem whose call without an option does not prove. An option is right if its call ended as `proved` and the option is among the facts the proof uses.

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

**`prover_key.jsonl`**: per problem: its bin (`proved without an option`, `has right options`, `no option proves it`, `stopped for another reason`), the reason when it is the last of these, the right options, the options whose call ended as `proved` without the option being used, and how the call with the held-back fact ended.

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
- `show(statement, names)`: the text the solver sees. Each coded symbol is replaced by its Mizar name; a symbol with no name stays as it is. A two-place symbol is written between its arguments (`(A /\ B)`, `A c= B`) when its Mizar name has a character other than a letter, a digit, `-` or `_`, and has no bracket of any kind (`(`, `)`, `[`, `]`, `{`, `}`) and no `..` in it. Every other symbol is written in front of its arguments. Brackets in the shown text always balance. Quantifiers and connectives stay in the provers' notation. Nothing else is changed.
- `same_statement(a, b)`: equal after variables are renamed in order of appearance.

Tests: `show` on ten real statements, each saved with its expected text, including one with a symbol that has no name; `symbols` on hand cases; `same_statement` on pairs that do and do not differ only in variable names.

### `mizar_ladder/problems.py`
Builds the two sets.
- For every theorem of the 33 articles, in the library's order: find its cited facts; if not usable, bin it. Otherwise draw the held-back fact at random from its cited theorems and lemmas, with a generator made from the seed and the theorem's name. If the held-back fact has fewer than 29 neighbours, bin it. Otherwise it qualifies.
- The test set is 300 qualifying theorems drawn at random with the seed. For each, 29 neighbours are drawn at random and the 30 options are put in a random order, both from the seed and the theorem's name.
- The training set is every other qualifying theorem of the 33 articles (about 900), built the same way. No theorem is in both sets.

Checks that stop the build: a cited fact missing from the theorem's problem file or stated after the theorem; an option stated after its theorem; a wrong option that the author cited or that has the held-back fact's statement; the held-back fact among the given facts; a theorem in both sets; a training problem whose theorem is not of the 33 articles; a test count that is not exactly 300; a theorem in no bin or in two.

Tests: on a made-up library of four small articles, the bins, the problems and the drawn options are as worked out by hand; same seed, same files; a different seed, different draws; each check above is made to fail once.

### `mizar_ladder/prover.py`
The one place that knows the prover. Built from the TPTP code's `prover.py` and its tests.
- **Kept as they are:** the one fixed environment every prover process is started with (it costs nothing and removes one source of difference between machines); the version check and the checksum of the program; the memory cap, the term cap and the cap on computing time; the seven endings and the rule that only three of them decide; taking the lines on time and memory used out of every output; giving the prover its input as a file.
- **Changed, because these problems are full first-order statements and not equations:**
  - `input_text(background_and_given, option, theorem)`: each fact as a `fof(name, axiom, ...)` line with its library name, in the problem file's order; then the option if there is one, under its library name; then the theorem as the conjecture. Nothing else.
  - The search setting is the prover's automatic mode, and the prover is asked to print its proof.
  - The exact lines of the prover's output that each ending rests on are taken again from real outputs on these problems (a proof here ends with the status `Theorem`, and a finished search without a proof with `CounterSatisfiable`). Each rule is written in the file with the words it rests on. None is guessed.
  - `used_facts(output)`: the library names of the facts in the printed proof.
  - The prover prints the name of its input file in a proof. That name differs from run to run, so it is taken out of every output before it is read or kept.
  - Everything about deriving facts and reading equations is left out.

Tests: the TPTP tests for the kept parts, still passing; a stand-in prover that prints its environment shows it is exactly the fixed one; `how_it_ended` on real saved outputs of every ending that can be produced on these problems, and a list in the tests of any that could not; `used_facts` on three real saved proofs; `input_text` for one fixed problem equals a saved copy letter for letter. **Slow tests (need the prover):** the version check; saved calls on problems far from the limit give their saved ending again. No test rests on a clause count of the real prover being the same twice.

### `mizar_ladder/calls.py`
Makes one set of prover calls into a folder: each problem's calls written whole or not at all, so that a run that is stopped carries on from what is saved, and the same files whatever the number of workers. The prover's key uses it for each of its two runs.

### `mizar_ladder/settle.py`
Every set of prover calls is made twice, into two folders, and then settled. In its automatic mode the prover's search is not the same from one run to the next (its clause counts change, and now and then its verdict), and nothing is done to force it to be. The two runs measure how steady it is.
- A call is **settled** if both runs give the same ending and, when both ended as `proved`, agree on whether the option is among the facts the proof uses. It is **unsettled** otherwise. An unsettled call counts as a call that did not decide. Differences in clause counts, or in which other facts a proof uses, are not compared. Nothing here stops the stage.
- `settle(first, second, out)` writes the final `prover_calls.jsonl` and a `settled.json`: how many calls there were, how many are unsettled and what share that is, split into "the endings differed" and "the use of the option differed", and the unsettled calls by name. A settled call's record is the first run's. An unsettled call's ending in the final file is the word `unsettled`, with both runs' endings beside it. Old files in `out` are cleared first. It starts no prover.

Tests: hand-made pairs of runs: identical; the same ending with different counts and different other facts (settled, first run kept); proved in one run and clause limit in the other (unsettled); proved in both with the option used in one only (unsettled); a cap in either run against a verdict in the other (unsettled); the shares in `settled.json` worked by hand.

### `mizar_ladder/prover_key.py`
For each test problem, at the limit (`LIMIT = 4000` processed clauses, written once in `prover.py`): the call without an option, then one call per option; all of it twice, then settled. Writes `prover_calls.jsonl`, `raw/calls/` and `prover_key.jsonl`. Stage 2 refuses to start under a shell limit on computing time or memory, and writes `settings.json`: the seed, the limit, the prover's version and checksum, the fixed environment and the version of the system's C library. It prints, with the bins, the share of calls on which the two runs disagreed. The bin is decided in this order: the call without an option is settled and ended as `proved` (`proved without an option`); it did not decide or is unsettled (`stopped for another reason`); some option is right (`has right options`); every option's call decided (`no option proves it`); otherwise `stopped for another reason`. Every problem in `stopped for another reason` carries the reason in a few words (for example "call without an option: term cap", "option 12: unsettled"). The list of right options is empty outside `has right options`. Also counted, as a check on the translation from Mizar: the problems whose call with the held-back fact ended as `nothing left` (every fact the author cited was given, the search finished, and there was no proof).

Tests: one hand-made case for every line above, and one where an option's call ended as `proved` without the option being used; one worker and four write the same files; a run stopped half-way and started again writes the same files.

### `mizar_ladder/programs/`
Each file has one function, `picks(problems, ...)`, returning one pick per problem. Programs that learn also have `train(training_problems)` and refuse a training set that contains a test problem's theorem. `common.py` holds what they share: making a pick from a set of tied options, and the citation counts.

- **Citation count of a fact:** the number of theorems that cite it, counting every theorem of the library except the 300 theorems of the test set. Theorems of the 33 articles that were not drawn into the test set do count. (A training problem's own theorem is also left out of its counts.) The same rule holds for every count a program takes from the library, including "cited together with a given fact".
- **`guessing.py`**: equal weight on all 30.
- **`recall.py`**: the option with the highest citation count.
- **`lookup.py`**: the option that is the held-back fact in the most training problems; ties share the weight; if none of the 30 was ever held back in training, equal weight on all 30.
- **`options_only.py`**: logistic regression predicting "this option is the held-back one" from the option alone: its length, its number of different symbols, its citation count, how many facts stand between it and the start of its article, and its rank among the 30 on each of those. It is never given the theorem or the given facts.
- **`surface_symbols.py`**: for each option, the sum over the symbols it shares with the theorem of the logarithm of (number of facts in the library divided by number of facts containing the symbol). The pick is the option with the highest sum. Nothing is trained.
- **`surface_trained.py`**: logistic regression predicting "this option is the held-back one" from: everything `options_only` sees; the shared-symbol sum with the theorem and with the given facts; the share of the option's symbols that are in the theorem; the number of other theorems that cite the option together with at least one given fact; the number of facts between the option and the theorem; and the option's rank among the 30 on each. The strength of its one setting is chosen by cross-validation inside the training set, splitting by article.
- **`search.py`**: reads `prover_calls.jsonl`. Equal weight on the options whose call ended as `proved`. If there is none, or the call without an option ended as `proved`, equal weight on all 30. It does not ask whether the option is used in the proof.

Tests: guessing scores 1/30; `recall` and `surface_symbols` on made-up problems worked by hand, including a tie; the citation count leaves out every test theorem and, for a training problem, its own theorem; `options_only` and `surface_trained` trained on a made-up rule learn it and score about chance on shuffled answers; `options_only` raises an error if handed the theorem's statement; `search` on hand-made call records for each of its three cases.

### `mizar_ladder/question.py`
Builds the text the model is shown: one sentence on what the notation is; the theorem; the given facts, numbered G1, G2 and so on; the 30 options, numbered 1 to 30; and the last paragraph as written in `mizar_plan.md`. No names of facts. An article's name can appear only inside a coded symbol that has no Mizar name, or where a Mizar name happens to be the same word as an article's (`real`, `subset`); stage 1 counts the questions where that happens.

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
- the counts of the four prover bins, and beside them the share of the key's calls on which the two runs disagreed.

Numbers only: no rule about whether the model's position "changed" is in the code.

Tests: a made-up set of ten problems where every figure was worked out by hand.

### Counted together (in `scoring.py`, or a file of its own if that would pass 200 lines)
The simple programs get different problems right, so the table of scores is followed by one that counts them together. A program gets a problem when more than half its weight is on the right option; the model gets it when at least three of its five tries are right. For every row of the tables: how many problems the best single program gets; how many at least one program gets; how many none gets. Stage 2 prints and saves these. Stage 4 adds, for the model: of the problems at least one program gets, how many the model gets; of the problems no program gets, how many the model gets. `guessing` is left out of "at least one program". Numbers only.

Tests: a made-up set where every count was worked out by hand, including a program with exactly half its weight on the right option (does not get it).

### `probe/`
The functional-equations probe script (itself the cube's), copied with its test and changed in the same way: 32 training problems drawn at random with the seed, one answer each, no thinking budget, 64,000 tokens per reply. Not part of the package.

### `stages/`
Four short scripts, each one command: `1_build_problems.py`; `2_programs_and_prover.py` (the prover's key, then the programs; `--limit N` runs the key at another limit than the experiment's 4,000, for looking at how the prover's verdicts move, and is recorded in `settings.json`); `3_model_run.py`; `4_report.py`. Each runs the checks from `mizar_plan.md` for its stage, and a failed check is printed first. Stage 2 prints any failed check first, and then, before anything else, how far `options_only` and `recall` sit above guessing.

### `tests/test_end_to_end.py`
The whole chain on the made-up library, with a stand-in prover that answers from a table and a stand-in model scripted to be always right, always wrong, unreadable, or out of thinking. Both final tables must equal ones worked out by hand.

## 5. What "done" means

As for the cube: all tests pass on a laptop without the prover and without the library's files, and the slow tests pass where both are present; the tests exercise at least 90% of the lines in `mizar_ladder/`, leaving out only the lines that start the real prover and talk to the real model server; `README.md` says where each of the library's files comes from, with its checksum, how to get the pinned prover, and how to set up, test and run each stage; a second reader who has not seen the code being written has read every file, and what they found is fixed.

## 6. Not to be built

Matching wrong options on how often they are cited; random wrong options; a second prover limit after the probe; any study of options that help without being used, beyond the one count; renaming of symbols to meaningless codes; hints; a second prover; the library outside the 33 articles as test problems; any rule in the code for what counts as "above" or as a changed position; any scoring other than right or wrong; saving the model's internal activity; a neural network.

## 7. Where the reusable earlier code is

In this repository: the cube's model-run, check, scoring and report files (`cube/cube_ladder/`), and the TPTP code's prover file and settling file (`tptp/tptp_count/prover.py`, `settle.py`). Each is the starting point for the file named above, changed as listed. Nothing is imported across the three folders at run time.

## 8. Settled points

1. **Recall and lookup are two rungs,** as in the plan. Now that training problems come from the same articles as test problems, "held back most often in training problems" is its own count and no longer the same as "cited most often".
2. **Every count taken from the library leaves out the 300 test theorems,** and, for a training problem, its own theorem. The other theorems of the 33 articles are counted.
3. **How statements are shown.** Mizar's names in place of the coded symbols, two-place symbols with symbolic names written between their arguments, everything else as the provers write it. The saved example in the tests is for reading before the model run.
4. **The prover's search setting** is its automatic mode.
5. **The prover's limit is 4,000 processed clauses.** There is no probe that chooses it. It was chosen by looking at the prover's key at 1,000 and at 4,000 on the test problems, before any model was run. (Above a few thousand the cap on terms stops the prover before the limit does.) The TPTP caps (memory 2,000 MB, 60 seconds of computing time) are unchanged.
6. **Test and training problems come from one pool:** the qualifying theorems of the 33 articles, 300 drawn for the test and all the others (about 900) for training.
7. **The search program counts an option as working whenever the prover succeeds with it,** whether or not the option is in the proof. The prover's key is stricter.
8. **Prover calls are made twice and settled,** and the prover always runs in one fixed environment. The two runs are not required to agree: where they disagree on the verdict the call decides nothing, and the share of such calls is reported.
9. **The prover is not forced to give the same search twice.** In its automatic mode its search changes from one run to the next unless the system's address randomisation is turned off, and rented containers commonly refuse that setting. The setting is not used. The experiment's other figures already vary from run to run (the model answers at random), and this variation is smaller and is measured.
10. **The prover is told to read numerals as plain symbols** (`--free-numbers`). Without it it cannot read the background facts of about half the problems.
11. **A call counts as stopped by the clause limit when the clauses it processed are at least the limit:** the automatic mode processes some clauses before the limit starts to count. A call in which the prover left out any given fact before searching does not decide.
12. **No two options of a problem say the same thing, and no option repeats a given fact or the theorem.** The library restates some lemmas as theorems; without this rule a repeated option is certainly wrong and can be struck out without reading the theorem.
13. **A search that finishes with no proof is a verdict, "does not prove",** for the call without an option and for a call with one.
14. **The problems for the thinking probe are drawn at random with the seed,** not taken in the library's order.

## Renaming
One new module, one new stage, one option on stage 3, one section in stage 4. Nothing that exists changes its output: `test_problems.jsonl`, every program's picks, and stage 4's files for a data folder without renamed answers stay byte-identical.

### `renaming.py`
- `code_map(symbols, seed)`: one code for each distinct symbol, `s` and five digits, from a shuffle of the sorted symbols with a generator made from the seed and the text "renaming". No code is the name of any symbol or a word of the question's fixed sentences.
- `show_renamed(statement, codes)`: the library's statement with every symbol replaced by its code, each written before its arguments in brackets (`s00412(A,B)`; a symbol without arguments is its code alone). Logic signs, `=`, variables and numerals are left as the named text shows them. A symbol with no code stops the stage loudly.
- `read_back(text, codes)`: undoes it, giving the statement in a form `statements.canonical` reads.

### Stage `1b_rename.py --data DATA --library LIBRARY`
Reads `test_problems.jsonl` and the library's statements. The symbols are those of the theorem, the given facts and the options of the 300 test problems; the seed is the problems' own. Writes `rename_map.json` (symbol to code, with the seed) and `test_problems_renamed.jsonl`: the same records in the same order with every `statement` replaced by its renamed form and one added field, `"renamed": true`. Run twice it writes the same bytes.
Checks, each stopping the stage: for every statement written, `read_back` then `canonical` equals the canonical form of the library's statement; within each problem no two of theorem, given facts and options have the same renamed text; every word of every renamed question (letters, digits, underscore) is a word of the two fixed sentences and headings, a variable, a code or a numeral. Prints the number of distinct symbols coded, and the theorem and first three options of the first problem, named and renamed.

### The question
`question.build_question(problem)` uses, for a problem with `"renamed": true`, a first sentence that ends "with each symbol of the Mizar Mathematical Library replaced by a meaningless code, the same code wherever the symbol appears." in place of "with each symbol written as its name in the Mizar Mathematical Library." Everything else is the same text.

### Stage 3: `--renamed`
Reads `test_problems_renamed.jsonl`; writes `raw/model_answers_renamed.jsonl` and `model_run_check_renamed.json`; each record's settings carry `"renamed": true`. Problem ids, tries, the order of asking and each request's seed are those of the named run. Without the option, stage 3 is unchanged, and it never mixes the two kinds in one file.

### Stage 4
If `raw/model_answers_renamed.jsonl` exists, it must hold the same problems and tries as the named answers and agree with them on every setting but `renamed`; else stop. It then adds a section "Named against renamed" to the report and writes `renamed.json`: per row, the model named and renamed with standard errors, the drop (mean of per-problem differences) with its standard error, the shares of paired tries right under both, named only, renamed only and neither, the forced share and mean thinking tokens under each, and the renamed model minus each program with standard errors. Nothing in the code decides what counts as a drop.

### Tests
Hand-made statements through `show_renamed` and `read_back`, including a symbol without arguments, nested applications, numerals and a quantifier over several variables; the code map for a seed is fixed and changes with the seed; two symbols sharing one Mizar name get two codes; stage 1b on the fixture library, twice, same bytes, and each of its three checks made to fail by a planted fault; the renamed first sentence; stage 3 with `--renamed` against the stand-in server writes only the renamed files and refuses a named file's records; stage 4 with and without renamed answers, the latter byte-identical to now, and its refusals (a missing try, a differing setting); the named-against-renamed figures on a hand-made case worked out by hand.

### Agreement with the named run
- Stage 1b also writes `named_run.json` from `raw/model_answers.jsonl`, which must be complete (every test problem, the same number of tries each, one settings record, one model version, no failed answer): the settings record, the model version, the number of tries, the run's seed, and the request seed of each problem and try.
- Stage 3 with `--renamed` needs `named_run.json` and, before its first request, stops unless its settings equal the named run's on every key (`renamed` aside), its model version and number of tries equal the named run's, and every request seed it will use equals the named run's.
- Stage 4 also stops if a renamed answer's request seed differs from the named answer's for the same problem and try, or if its question text is not the renamed question of that problem.
- Stage 4 removes a `renamed.json` from an earlier run when there are no renamed answers.
