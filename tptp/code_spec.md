# The TPTP experiment: code specification

2026-11-13. This says what the code must do, file by file, so that it can be built and then read by a person. The experiment itself is described in `tptp_plan.md`; read that first. The layout and the rules follow `cube/code_spec.md`. There is no model and there are no simple programs, so this is the smallest of the three.

## 1. Rules for the code

The cube's nine rules, unchanged: one idea per file (aim for under 200 lines); plain names; every function that produces a number in the report has a test; no locations typed into the code; one place that knows the prover; stages talk only through files in `data/`; same input and seed, same output; fail loudly, nothing silently dropped or skipped; comments say why, and each file starts with two or three sentences on what it is for.

Python 3.12 or later. Allowed libraries: pytest, coverage. The prover is E, version 2.6, installed outside the code; where it is and where the TPTP library is are given as settings.

Three rules specific to this experiment:
- **Nothing depends on clock time.** No step is skipped, cut short or abandoned because of how long something took. The only time limit is the prover's own cap on computing time per call, and a call that reaches it is recorded as such.
- **The number of workers does not change any output.** Work is split over processes for speed; the files written are the same, line for line, whatever the number.
- **The prover is always started in the same environment.** Its search depends on memory settings of the machine (seen with `MALLOC_MMAP_THRESHOLD_`, `MALLOC_TOP_PAD_` and `GLIBC_TUNABLES`). Every prover process is started with one fixed environment written in `prover.py`, and nothing from the caller's environment reaches it. Limits set by the shell reach the prover too, so stage 1 refuses to start unless the limits on computing time and on memory are both unlimited.

## 2. Words used

- **File:** one problem file of the TPTP library, with any axiom files it includes read in.
- **Equation:** two terms with an equals sign between them; variables are read as "for all".
- **Axioms:** the equations a file gives as true.
- **Goal:** the equation a file asks to be proved. TPTP writes it in denied form (an inequality between terms with fixed constants in place of the variables); it is kept in that form for the prover.
- **Usable file:** every statement in it is a single equation, and the goal is a single denied equation. A file that states its goal as a conjecture is not usable. Files TPTP has withdrawn (named `.rm`) are not read and get no line; the code says so where it lists the files.
- **Status:** the word TPTP's header gives for the file. A file is a **theorem file** when its status is `Unsatisfiable`, the word TPTP uses for a file in denied form whose goal follows from the axioms.
- **Axiom set:** the axioms of a file, as a set. Two files have the same axiom set if one becomes the other by renaming symbols and variables.
- **Same problem:** the same axiom set and the same goal, under one renaming.
- **Derived fact:** an equation the prover derives from the axioms alone, without the goal, that passes the rules in `derived.py`.
- **Renaming, for facts:** two facts are the same if one becomes the other by renaming variables or swapping its two sides. Symbols are not renamed here; they are only for comparing axiom sets and problems.
- **Options:** the 30 derived facts drawn for a file.
- **Call:** one run of the prover on a file's axioms, at most one option, and the goal.
- **How a call ended:** exactly one of `proved`, `clause limit` (the 160 processed clauses were used up), `nothing left` (the prover finished without a proof: the goal does not follow from what it was given), `term cap`, `memory cap`, `time cap`, `unreadable` (the output fits none of the others).
- **Decides:** a call decides when it ended as `proved`, `clause limit` or `nothing left`. The last two mean "does not prove". A call that ended any other way does not decide.
- **Right fact:** an option whose call ended as `proved`, in a file whose unaided call ended as `clause limit`.
- **Bin:** the one row of the plan's table a file ends in.

## 3. Files in `data/`

One JSON object per line unless noted.

**`files.jsonl`**: one line for every TPTP file read.

| Field | Meaning |
|---|---|
| `path` | The file's path inside the library |
| `area` | TPTP's three-letter subject area |
| `status` | The status word from the header |
| `bin` | One of the eight bins |
| `why` | For the left-out bins and for "stopped for another reason": the reason in a few words (for example "goal is not a single equation", "same problem as GRP001-2", "unaided call: term cap") |
| `problem_id` | Set for files in the last four bins |

**`problems.jsonl`**: one line for every file in the bins "proved unaided", "no single fact helps", "a problem" and "stopped for another reason".

| Field | Meaning |
|---|---|
| `id`, `path`, `area` | As above |
| `axioms`, `goal` | As text, with TPTP's own names, axioms in the file's order |
| `unaided` | How the unaided call ended, and its counts (clauses processed, clauses generated, terms built) |
| `options` | The 30 facts as text, in the order drawn. Absent when the file was proved unaided or the unaided call did not decide |
| `calls` | For each option: how its call ended, and its counts |
| `right` | The numbers of the right facts |
| `undecided_options` | The numbers of the options whose call did not decide. When this is not empty, `right` may be missing facts, and the report counts such problems |
| `seed` | The run's seed |

**`derived_facts.jsonl`**: one line per axiom set: the derived facts that pass the rules, how many the prover printed before the rules were applied, and how each of the deriving runs ended. The part of each deriving run's output that is not a list of equations is kept under `calls/`. For a deriving run that did not finish, only how it ended is written: what it had printed by then, and its output, differ from one run to the next and are not kept in any file that is compared. Lines of the prover's output that report time or memory used are never kept.

**`work/settings.json`**: the seed, the limit, the prover's version, the checksum of the command that starts it and, when that command is a start script, the checksum of the prover program behind it (given as a setting), the fixed environment, the shell's limits on computing time and memory, the version of the system's C library, and the TPTP version read from the library. A run that is started again refuses to carry on if any of these differs from what is saved.

**`calls/`**: the prover's full output for every call, compressed, one file per problem.

**`bins.json`**: the counts in each bin, the three main bins as shares of their total, and the figures the plan lists beside them. Not one object per line.

## 4. The code, file by file

### `tptp_count/equations.py`
Terms and equations.
- `read_equation(text)`, `write_equation(equation)`.
- `size(equation)`, `variables(equation)`.
- `key(equations)`: equal for two lists of equations exactly when one becomes the other by renaming symbols and variables. Used for axiom sets and for "same problem".
- `is_instance(equation, of)`: whether one equation is another with its variables filled in.

Tests: reading then writing gives the text back; `key` on hand-made pairs that are and are not renamings of each other, including a renaming that swaps two symbols of the same kind; `is_instance` on hand cases; agreement with the earlier pilot's code on 1,000 equations taken from its saved problems (the earlier code is used in tests only).

### `tptp_count/tptp_file.py`
Reads one file.
- `read_file(path, library)`: the status, the area, the axioms and the goal, following `include` lines.
- `usable(file)`: yes, or the reason why not.
- `is_theorem(status)`: one fixed list of status words that mean the goal follows from the axioms. The list is written at the top of the file with a note on where TPTP defines each word.

Tests: five real TPTP files saved in the tests, chosen to cover: usable with no includes; usable with an included axiom file; a statement that is not a single equation; a goal made of two statements; a status that is not a theorem. The quantifier-list fault of the earlier reader (a list of variables cut at its comma) has its own test.

### `tptp_count/prover.py`
The one place that knows E.
- `COMMAND`: the pinned command line, written once: the fixed search setting of the earlier pilot (ordering KBO, no literal selection, clauses taken in turn by age and by size), `--processed-clauses-limit`, the term cap of 1,000,000 insertions, the memory cap of 2,000 MB, the cap of 60 seconds of computing time.
- `check_version()`: stops the run unless the prover reports exactly the pinned version.
- `input_text(axioms, option, goal)`: the axioms in the file's order, then the option if there is one, then the goal. Nothing else.
- `ENVIRONMENT`: the one fixed environment every prover process is started with, written once, with a comment saying why. Nothing else in the code starts the prover.
- `call(axioms, option, goal, limit=160)`: runs the prover and returns how the call ended, the counts, and the full output (both of the prover's output streams). The input is handed over as a file, because the prover prints its equations in another order when it reads from its input stream.
- `how_it_ended(output)`: reads the prover's output and returns one of the seven endings. The rules are written out in the file, one line per ending, each with the exact words of the prover's output it rests on.

Tests: a stand-in prover that prints its environment shows it is exactly `ENVIRONMENT` whatever the caller's environment holds; `how_it_ended` on real saved outputs of every ending (taken from the earlier pilot's kept outputs where they exist, and made once with the pinned prover where they do not); an output that fits none gives `unreadable`; `input_text` for one fixed problem equals a saved copy letter for letter. **Slow tests (need the prover):** 200 calls rebuilt from the earlier pilot's saved problems give the pilot's outcome and the pilot's counts on every one; one call run three times at once gives the same result each time; 50 borderline pilot calls give the same ending and counts when the caller's environment holds each of the three memory settings named in section 1.

### `tptp_count/derived.py`
The derived facts of an axiom set.
- Runs the prover on the axioms alone, six times with six fixed settings (the earlier pilot's list, written at the top of the file), each asked to print the equations it holds when it stops. These runs have a memory cap and a 60-second cap on computing time and, as in the pilot, no cap on terms.
- Of each run's printout, lines longer than 220 characters are passed over and only the first 1,500 equations are read. This is the pilot's rule and is kept so that the facts are the pilot's; the file says so.
- Keeps an equation if it has 5 to 16 symbols and at most 4 variables, is not an axiom, is not an instance of an axiom, and its two sides differ. Equations that are renamings of one another count once; the first one met is kept.
- The order of the result is fixed: by deriving run, then by the order the prover printed them.
- How each deriving run ended is recorded. If any of the six ended on the time cap or the memory cap, or its output cannot be read, the axiom set has **no usable list of facts**: nothing is drawn, and every file on it goes to "stopped for another reason" with that reason.
- Facts are derived once per axiom set, from its first file in the library's order, and carried to the set's other files by the renaming of symbols that matches their axioms.

Tests: the rules on hand-made equations; with a stand-in prover that prints a fixed list, the result and its order are as worked out by hand. **Slow test:** for 20 axiom sets of the earlier pilot, the facts before any topping-up equal the pilot's.

The earlier pilot topped up a short list with made-up variants of facts it already had. That is not built: an axiom set with fewer than 30 derived facts goes to "too few facts".

### `tptp_count/options.py`
`draw(derived_facts, goal, seed, problem_id)`: removes any fact that is the goal up to renaming, then draws 30 at random with a generator made from the seed and the problem's id. Fewer than 30 left means "too few facts".

Tests: same seed and id, same draw; a different id, a different draw; the goal is never among the 30; exactly 29 facts gives "too few".

### `tptp_count/bins.py`
`bin_of(...)`: the one function that decides a file's bin. In this order:
1. Not usable, not a theorem file, or a duplicate of a file earlier in the library's order: the matching left-out bin.
2. The unaided call ended as `proved`: "proved unaided".
3. The unaided call did not decide, or the axiom set has no usable list of facts: "stopped for another reason".
4. The unaided call ended as `nothing left`: "stopped for another reason", with the reason "the prover says the goal does not follow, TPTP says it does". (This should not happen and is counted if it does.)
5. Fewer than 30 options: "too few facts".
6. Any option's call ended as `proved`: "a problem".
7. Every option's call decided: "no single fact helps".
8. Otherwise: "stopped for another reason".

Tests: one hand-made case for every line above, and for the cases the order settles: a file with one `proved` option and one `time cap` option is "a problem" whichever of the two comes first among the 30; a file with no `proved` option and one `time cap` option is "stopped for another reason"; the same with each of the other endings that do not decide.

### `tptp_count/count.py`
Does the work: finds the files, reads each, groups them by axiom set, derives facts once per axiom set, draws options, makes the calls, writes `files.jsonl`, `problems.jsonl`, `derived_facts.jsonl` and `calls/`.
- Files are taken in the library's own order of names.
- A run that is stopped can be started again and carries on from what is saved; the files written at the end are the same as from one unbroken run.

Tests (with a stand-in prover that answers from a table): a made-up library of twelve small files gives the bins worked out by hand; every file is in exactly one bin; one worker and four workers write the same files; a run stopped half-way and started again writes the same files as an unbroken one.

### `tptp_count/settle.py`
`settle(first, second, out)`: applies settled point 9 and writes the final files and `settled.json`. It reads only the two counts' files; it starts no prover.

Tests (hand-made pairs of counts, built from the made-up library with the stand-in prover): two identical counts settle to the first; a set with no list in both and different runs cut off is settled and named; a set with a list in one count only is unsettled, and each kind of file on it goes where the rule says (one proved unaided, one whose unaided call did not decide, one that had been "a problem" in the count with the list, one that had been "no single fact helps"); two different lists for one set stop the stage; a difference in a file on a settled set (its bin, one right fact, one byte of a call's output) stops the stage; a difference in the unaided call of a file on an unsettled set stops the stage; settling the same two counts twice writes identical files.

### `tptp_count/report.py`
From `files.jsonl` and `problems.jsonl`: the bin counts; the three main bins as shares of their total; clauses needed by the files proved unaided; right facts per problem, with the number of problems that have an undecided option; the three main bins by area; the number of files set aside because the two counts did not derive the same facts for their axioms. Writes `bins.json` and prints the tables.

Tests: the made-up library's tables equal ones worked out by hand; the bins add up to the number of files read.

### `stages/`
Two short scripts, each one command.
- `1_count.py`: **before counting**, refuses to start under a shell limit, checks the prover's version and runs the 200 pilot calls, comparing endings and counts, and stops on any difference. Then it counts into `data/first/`, counts again into `data/second/`, settles the two into `data/`, and runs the stage's other checks from `tptp_plan.md` on the final files: a repeat of one call in twenty; every file in exactly one bin; no call that did not decide counted as "does not prove". A failed check is printed first. The time taken is printed at the end and written nowhere that is compared. It then counts a second time and settles the two counts, as settled point 9 says; there is no separate compare command. Each of the two counts can be stopped and started again on its own.
- `2_report.py`: runs `report.py`.

### `tests/test_end_to_end.py`
The whole chain on the made-up library with the stand-in prover: `1_count.py` then `2_report.py`. The final table must equal one worked out by hand.

## 5. What "done" means

As for the cube: all tests pass on a laptop without the prover, and the slow tests pass where the pinned prover and the earlier pilot's files are present; the tests exercise at least 90% of the lines in `tptp_count/`, leaving out only the lines that start the real prover; `README.md` says how to get the pinned prover and the TPTP library (with the checksum of each), and how to set up, test and run each stage; a second reader who has not seen the code being written has read every file, and what they found is fixed.

## 6. Not to be built

A model run, a question or an answer reader; any simple program; training and test sets; a second clause limit; a check of whether a right fact is used in the proof; a goal generator; hidden axioms; topping up a short list of facts; re-proving goals with a stronger prover setting; renaming of symbols; anything that reads TPTP's difficulty rating; any rule that picks a worked example; any step that depends on how long something took.

## 7. Where the reusable earlier code is

In the archives of the earlier pilots of this puzzle (kept outside this repository): terms and equations and their renaming key; the TPTP reader, with its later fix; the prover's command line and the reading of its output; the six deriving runs. Each is to be moved into the file named above, renamed to the words in section 2, and given tests. Nothing is imported from the archives at run time.

## 8. Settled points

1. **The package is `tptp_count`.** There is no ladder here.
2. **A file where the prover finishes with nothing left and no proof,** although TPTP records a theorem, goes to "stopped for another reason" with that reason, and is counted. None is expected.
3. **Short fact lists are not topped up.** An axiom set with fewer than 30 derived facts goes to "too few facts".
4. **The option goes after the axioms and before the goal** in the prover's input. The prover's search depends on the order, so it is fixed.
5. **Of duplicate files, the first in the library's order of names is kept.**
6. **Only files in denied form are used.** The 54 files made only of equations that state their goal as a conjecture are left out, so that the goal reaches the prover as TPTP wrote it.
7. **A set of axioms with a deriving run that did not finish has no list of facts,** and its files go to "stopped for another reason".
8. **The check against the pilot's 200 calls runs before the count** and compares counts as well as endings.
9. **The count is made twice and then settled.** Stage 1 runs `count.py` into `data/first/` and again into `data/second/`, then `settle.py` writes the final files into `data/`. Nothing that differs from run to run for other reasons (what a cut-off deriving run had printed, the prover's own time and memory figures) is written to any of these files. The rules of settling, in this order:
   - **An axiom set is settled** if both counts have the same usable list of facts for it (same facts, same order), or both have none. For a set with none in both, which of its deriving runs were cut off is not compared; sets where that differed are named.
   - **An axiom set is unsettled** if one count has a usable list and the other has none. Nothing from it is used.
   - **Two different usable lists for the same axiom set stop the stage,** with the set named.
   - **A file on a settled set** must have the same line in `files.jsonl`, the same line in `problems.jsonl` and the same file under `calls/` in both counts. Any difference stops the stage, with the file named.
   - **A file on an unsettled set:** its unaided call must be identical in both counts (a difference stops the stage). If that call ended as `proved`, the file is "proved unaided". If it did not decide, the file is "stopped for another reason" as before. Otherwise the file is "stopped for another reason" with the fixed reason "its axioms' facts were not the same in two counts", its `problems.jsonl` line carries the unaided call and no options, and only the unaided call is kept under `calls/`.
   - The final `files.jsonl`, `problems.jsonl`, `derived_facts.jsonl` and `calls/` are the first count's, changed only as the rule above says. `settled.json` lists the unsettled sets with their files, and the sets whose cut-off runs differed.
10. **Stage 1 refuses to start under a shell limit** on computing time or memory.
