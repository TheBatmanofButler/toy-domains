# Post 1, TPTP: plan and outcome rules

Written 2026-11-13. It follows `cube/cube_plan.md` where it can; the differences are listed near the end. Numbers quoted from the earlier pilot of this puzzle are a guide only and are not results.

## What the experiment is for

It is a short section between functional equations and Mizar, on small algebra problems from the TPTP library. In functional equations a move is one of thirteen fixed operations. Here a move is choosing a fact, and a prover with a limit is the judge. The section reports one thing: how many small algebra problems are ones where choosing a fact matters at all.

The expected answer is "very few", because the problems are too small for the prover to need help. That is the reason the post then moves to a library of larger mathematics. This experiment makes no claim about a model and none about taste.

## The puzzle

- **What a problem is.** A small set of equations (the axioms of a group, a lattice, a ring and so on), a goal equation that follows from them, and 30 further true equations to choose from.
- **The judge.** The E prover, version 2.6, with one fixed search setting and a limit of 160 processed clauses, always started in the same bare environment (see "One machine setting" below).
- **What counts as right.** A fact is right if the prover cannot prove the goal from the axioms within the limit, and can once that one fact is added.

## The problems

- **Where the goals come from.** The TPTP library, version 9.3.1: every problem file made only of equations, whose goal is a single equation written in denied form (TPTP's clause form, where the goal appears as an inequality to be refuted). Nothing is generated. Reading the library finds 1,280 such files. Files that state their goal the other way, as a conjecture, are not used (54 files made only of equations do), so that the goal reaches the prover exactly as TPTP wrote it. Files TPTP has withdrawn are not read.
- **Which are theorems.** TPTP records a status for each problem. Problems whose status says the goal follows from the axioms ("Unsatisfiable", for files in this form) are kept: 1,058 of the 1,280. The others are counted and left out. The prover is not asked to confirm it.
- **Duplicates.** Two files with the same axioms and the same goal, up to renaming of symbols and variables, count once. That leaves 1,026 problems on 462 different sets of axioms.
- **Where the 30 facts come from.** For each set of axioms, the prover is run on the axioms alone, without the goal, and the equations it derives are collected. Every one is a consequence of the axioms. Kept: equations of moderate size (5 to 16 symbols, at most 4 variables) that are not an axiom, not an instance of an axiom and not the goal. From these, 30 are drawn at random with the seed, without looking at the goal.
- **Seed:** 20261112, the cube's.
- **Nothing dropped silently.** Every file read ends in exactly one of the bins below.

## What is counted

Each problem file ends in one bin.

| Bin | Meaning |
|---|---|
| Left out: not usable | Not only equations, or the goal is not a single equation |
| Left out: status | TPTP does not record that the goal follows from the axioms |
| Left out: duplicate | Same axioms and goal as a file already counted |
| Left out: too few facts | Fewer than 30 derived facts pass the rules above |
| **Proved unaided** | The prover proves the goal from the axioms within the limit |
| **No single fact helps** | The prover fails unaided, and fails with each of the 30 facts added alone |
| **A problem** | The prover fails unaided, and at least one of the 30 facts rescues it |
| Stopped for another reason | The unaided call, or any call that would decide the bin, ended on something other than the clause limit or a proof; or one of the runs that derive the facts for this file's axioms did not finish; or the two counts (see below) did not derive the same facts for this file's axioms |

The last bin exists because the prover has three other stops besides the clause limit: a cap on the terms it may build, a memory cap and a 60-second cap on computing time. Each call records which stop ended it. A call ended by one of these three is never counted as "does not prove". The same holds for the runs that derive the facts: if one of them is cut off, the list of facts would depend on the machine's speed, so every file on those axioms that the prover does not prove unaided goes to this bin. (A file proved unaided needs no facts and stays where it is.) Whether a deriving run is cut off can itself depend on the machine's speed: a handful of the 462 sets of axioms sit at or near the cap, and a run that takes 59 seconds one time takes 61 the next.

**The count is made twice, and a set of axioms is used only if both counts agree on it.** The whole count is run two times. If both derive the same facts for a set of axioms, or both derive none, the set is settled. If one count derives facts and the other does not, nothing from that set is used: every file on it that needed the facts goes to "stopped for another reason". A file proved unaided needs no facts and is not affected. Everything else must come out identical in the two counts, or the stage fails. The post gives the size of this bin and says why.

**One machine setting.** The prover's search turns out to depend on memory settings of the machine it is started on: with one such setting present, the same prover on the same input processed different numbers of clauses, derived different facts, and on a few borderline calls ended differently. So the code starts every prover run in one fixed, bare environment, and the stage checks this before it counts anything. The post says so.

**The main result** is the three bold rows as shares of their total.

**Reported beside it, as found:**
- for problems proved unaided, how many clauses the prover needed (how far under the limit they are);
- for problems, how many of the 30 facts are right;
- the three bold rows by TPTP's subject area (groups, lattices, rings and so on).

**Every problem is saved in full** (axioms, goal, the 30 facts, which are right, and every prover call), so that examples can be chosen when the post is written.

## The stages and what counts as each outcome

Each stage is run from a written brief. Its report is unconfirmed until it has been reviewed. Nothing is a number for the post before that.

### Stage 1. Read the library and count (CPU pod)

- **Must hold, or the stage stops:**
  - **before anything is counted:** the prover is the pinned version, and on 200 calls from the earlier pilot (each input rebuilt exactly from the pilot's saved problems, each outcome on file) it gives the same ending and the same counts on every one. This is what shows that the machine the stage runs on behaves as the pilot's did;
  - a repeat of one call in twenty gives the same outcome every time;
  - every file read is in exactly one bin, and the bins add up to the number of files;
  - no call ended by the term cap, the memory cap or the time cap is counted as "does not prove";
  - the two counts agree, as described under "What is counted": apart from sets of axioms where one count derived facts and the other none (which are set aside and listed by name), every file has the same bin, every problem the same options and right facts, and every prover call the same output. If two counts derive two different lists of facts for the same axioms, the stage fails: that is not expected and would mean something other than the time cap differs.
- **Reported as found:** the bins; the figures listed above; time taken.

### Stage 2. The report (no pod)

- **How the result is read.** There is no pass or fail. The section reports the shares.
- **Expected shape, written down so a surprise is visible** (from the earlier pilot, which tried 130 of the library's own goals): about a quarter proved unaided; about two thirds where no single fact helps (the pilot left out 52 goals a stronger prover could not prove in 60 seconds, and most of those are expected here); fewer than one in ten a problem. How many land in "too few facts" and "stopped for another reason" is not known in advance.
- **What would change the story.** If problems turn out to be a large share, the claim "too small for the prover to need help" is wrong as stated, and the section is rewritten around what was found before the post moves on.

## Code

A folder `tptp/` beside `cube/` and `fe/`, with the same layout: a package with one idea per file (reading a TPTP file; equations; the prover call and its stop reasons; the derived facts; drawing the 30; the bins), two stage scripts, and tests. The earlier pilot's code is kept in the tests only, to show the new prover call gives the old outcomes. Nothing depends on clock time. The full output of every prover call is kept.

## Spending

| Stage | Ceiling | Basis |
|---|---|---|
| 1. CPU pod | $5 | 1,026 problems at up to 31 prover calls each, plus deriving the facts for 462 sets of axioms: on the order of 35,000 calls, made twice. The earlier pilot made 49,000 calls in about 20 minutes on a 32-core pod at $1.12 an hour |

The price and stock are read again and stated before anything is created; the pod is stopped when done and not deleted; no other pod is touched.

## Not in this experiment

A model run. The simple programs. A second prover limit. Whether a fact that helps is used in the proof. (The last two are asked on the Mizar problems.) Generated goals. Hidden axioms. TPTP problems that are not made only of equations.

## Known differences from the cube, and why

- **No model and no simple programs.** The section's result is that the problems are too small for the question to arise; with about 100 problems a ladder would say little.
- **No test and training sets.** Nothing is trained.
- **The options are a sample.** On the cube and in functional equations the options are every legal move. Here the true facts are without end, so 30 are drawn, at random and without looking at the goal, so that nothing about the answer shapes the list.
- **The answer key comes from a prover with a limit,** not from the puzzle itself. That is the point of the section.
- **The result is a count of problems,** not a score by level.
- **One CPU stage,** no GPUs.
