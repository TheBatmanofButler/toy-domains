# Post 1, functional equations: plan and outcome rules

Written 2026-11-12. It follows `cube/cube_plan.md` wherever it can; the differences are listed near the end. Numbers quoted from the earlier run of this puzzle are a guide only and are not results.

## What the experiment is for

It is the second puzzle of post 1. The cube shows the ladder on a game. This shows it on something that looks like mathematics and still has an exact answer key, and where simple search programs do well. It asks two things:

1. Where does the model sit against the simple programs at each depth?
2. When the model and a search program score alike, do they get the same problems right and make the same wrong moves, more than the model matches programs that do no search?

The claim stays in its ceiling form: whatever the model scores beyond the best simple program is the most that could be taste. The model's thinking is saved in full for every answer; how it is studied is left for later and is not part of this plan.

## The puzzle

- **What the solver sees.** One equation that an unknown function f satisfies for all rational x and y, a goal identity, and a list of 13 allowed substitutions (for example `y=0`, `y=-x`, `swap x,y`). A move applies one substitution to one numbered identity; the result is added to the list with the next number.
- **What counts as proved.** The goal is proved once it is a combination, with rational coefficients, of the numbered identities, treating each distinct term f(...) and each power of x and y as its own unknown. This is exact arithmetic with fractions; no prover with a limit is involved.
- **What counts as right.** A move is right if it is the first move of a shortest possible proof. The shortest length is found by trying every sequence of moves.
- **Depth.** The number of moves in a shortest proof.
- **One scoring rule.** An answer is right or wrong.

## The problems

- **How they are made.** An equation is built from one of seven families of functions (constant, linear, quadratic and so on), so that it is true for that family. A goal is then made by applying two short chains of random substitutions and combining what they produce. The depth is measured afterwards by the search; it can be shorter than the chains used.
- **What the post must say.** The goals are built this way, so they are long and do not look like textbook problems. Every problem has a planted route, and the shortest proof may be a different one. The planted routes are three to five moves long, so every depth-2 problem is one where a two-move shortcut happens to exist (about 6% of attempts in the earlier run); depths 3 to 5 are the generator's ordinary output.
- **Test set:** 300 different problems at each depth from 2 to 5, 1,200 in all. Two problems are "the same" if one becomes the other by swapping x and y or by scaling f.
- **No filter on the share of right moves.** The old run kept only problems where 3% to 40% of moves were right. Here every problem is kept and guessing is reported at each depth. The old run's extra sets, made only of problems that one-move lookahead got wrong, are not rebuilt.
- **Training set** for the programs that learn: up to 1,000 other problems per depth from the same generator (the cube's size), used all depths mixed, never containing a test problem or one that is the same in the sense above.
- **Seed:** 20261112, the cube's.
- **Nothing dropped silently.** A problem whose search exceeds its time limit is recorded as such and counted. If more than 1% of the problems searched do, the build stops.

## The simple programs

| Rung | Program |
|---|---|
| Guessing | Share of the available moves that are right |
| Options only, and lookup | The substitution that is right most often in other problems. One line, because the options are nearly the same in every problem |
| Recall | The textbook order: the first substitution in the list that produces something new |
| Surface, strict | Logistic regression on what is on the page before any move: which substitution it is, and counts of the terms in the equation and the goal. It never sees the result of a substitution |
| Surface, relaxed | The old run's reader: it also sees the result of each substitution (how many terms there are afterwards, how many of the goal's terms are then present). One move of lookahead with a learned score |
| Search | Lookahead of up to 1, 2 and 3 moves. A sequence that proves the goal wins outright, as the cube's lookahead stops when it sees a solved cube. Otherwise it scores the identities at the end of each sequence by how many of the goal's terms are present, less terms that belong to neither the goal nor the equation |
| Search, narrow and deep | At each step, work out every available move, score each as above, keep the three best, and go on from those, for up to five moves or until the goal is proved. The answer is the first move of the path that proved the goal, or of the best-scoring path if none did. It works out a few hundred identities per problem, where three-move lookahead works out about 5,000 |

The three paths and the five moves of the narrow-and-deep program are settings, fixed here before anything is scored, and the post names them. When pages tie for the last place kept, the choice among them is random, from the run's seed. Ties are scored as the share of tied-best moves that are right. No neural network is on the ladder. **Room** at each depth is one minus the best simple program, counting all of them.

The old run's lookahead scored the same way but never checked whether the goal was proved. It is not on the ladder. It is kept in the tests only, to show that the rebuilt code gives the old run's scores on old problems.

**A consequence to state plainly.** Lookahead of up to k moves is perfect at every depth up to k. So room is zero at depths 2 and 3 by construction, as it is close to solved on the cube. The open ground is depths 4 and 5.

## The model

- **Model:** the standard Qwen model (Qwen3.8-27B, same version as the cube run), thinking on.
- **Question:** the old layout, with the last lines changed to state the rule, in the same form as the cube's question: "A move is correct if it is the first move of a shortest possible proof of the goal. Each substitution applied to one identity counts as one move. Give one correct move, with the substitution written exactly as it appears in the list. Answer with `MOVE: (<identity number>) <substitution>`." The depth is not given.
- **Thinking allowance:** chosen after a probe on this puzzle that shows how long the model thinks when nothing cuts it off (see stage 3). On the cube the same probe found that thinking did not end even within 64,000 tokens, and 8,000 was kept; that is not assumed here. Known for this puzzle from the earlier run, with the old question: the model had finished within 8,000 tokens on 18, 10 and 1 of 300 problems at depths 3, 4 and 5, and within 16,000 on 73, 35 and 9.
- **Enforcing it:** as in the cube run. Up to 1,000 more tokens are allowed for the answer. When the thinking reaches the limit the model server closes it with the stop sentence from the Qwen3 documentation and the model answers from what it has, in the same turn. Such an answer is called forced.
- **Tries:** five per problem, with the cube run's settings, read from the model's own card: temperature 1.0, top-p 0.95, top-k 20, min-p 0.
- **Total:** 1,200 problems x 5 tries = 6,000 answers.
- **What is kept:** the exact text and tokens of every question, all thinking and every answer, with model version and settings. No internal activity is extracted now.

## Scoring and reporting

As for the cube:
- An unreadable answer counts as wrong and the model is not asked again. A readable move that is not available (it produces nothing new) also counts as wrong. Both shares are reported at each depth.
- A problem's score is the share of its five tries that are right; a depth's score is the average over its 300 problems; every score has a standard error.
- Problem by problem: the model "gets" a problem when at least three of five tries are right; a program gets it when more than half its weight is on right moves. For each program and depth: both, only the model, only the program, neither, with the count expected if the two were unrelated.
- Budgets, each in its own units: the model's allowance, tokens actually used and share of forced answers at each depth; each lookahead's number of sequences examined; the narrow-and-deep program's number of identities worked out. One common figure, as an upper limit only, as for the cube: the most identities the model could have written out in its tokens. The post says this places the model among the programs and does not rank them on equal terms.
- **Same wrong moves,** defined exactly as in the cube plan. For each simple program and each depth, take every try where the model gave a readable move that is available and wrong (a move that is not available is left out, as an answer that is not one of the 18 turns is on the cube; how many are left out is reported), and look up how much weight the program put on that same move for that problem. The average, problem by problem, is the match rate. Two figures stand beside it: what uniform guessing among the wrong moves would give on those problems, and a shuffle figure (the same model moves set against the program's choices on the other problems at that depth), which shows how many matches come from habits alone. The recall rule and the strict surface reader serve as controls. It is worked out afterwards from the saved answers and picks.

New for this puzzle:
- **Forced and unforced answers are reported separately** at each depth: how many, and the share right.

## The stages and what counts as each outcome

### Stage 1. Build the problems (CPU pod)
- **Must hold, or the stage stops:** the rebuilt search gives the old run's depth and right moves on 60 old problems (20 at each of depths 3, 4, 5); on small cases it agrees with a plain search that tries everything; every problem is at its stated depth; exactly 300 test problems per depth, all different; no test problem in the training set; every problem has at least one right move; no more than 1% of problems timed out.
- **Reported as found:** right moves and available moves per problem at each depth; how often the shortest proof is shorter than the planted route; time taken.

### Stage 2. Run the simple programs (no pod, or the same CPU pod)
- **Checks on the programs:** guessing equals the average share of right moves; lookahead of up to k moves scores 1.0 at every depth up to k; the old run's score-only lookahead, kept in the tests, reproduces the old run's score on each of the 60 old problems.
- **Reported as found:** every program at every depth, and room at every depth. The options-only line is expected to sit above guessing here (the old run found some substitutions are right more often than others); it is reported, and nothing waits on it.
- **No pass-or-fail verdict on the experiment.**

### Stage 3. The model run (GPUs)
**First, a probe, copied from the cube's.** 32 problems from the training set, eight at each depth from 2 to 5, never test problems; one answer each; the real question and settings; no thinking limit, and up to 64,000 tokens per reply. Reported: thinking tokens per answer and by depth; how many finish within 8,000, 16,000, 32,000 and 64,000; whether an answer can be read. Nothing about right or wrong, no pass or fail, and none of it enters the experiment's data. One card for at most an hour. The allowance is chosen from its figures, before the run.

The cube run's code as it stands after the cube's own run, and the cube's way of running: one pod with the asking program on the same pod as the model servers; first one card for the first 100 answers and the run's checks, then several cards of the same type once the checks have passed. The checks are the cube's: every record complete; forced answers readable about as often as unforced ones; no more than 15% unreadable; projected cost under the ceiling.

### Stage 4. The report
- **Where the model sits, at each depth.** The model is above a program when the gap on the same problems is more than two standard errors of the gap. One depth alone is not a finding.
- **Do its wrong moves resemble a program's?** The cube's rule: at a depth, the model's wrong moves resemble a program's when the match rate is more than two standard errors above the shuffle figure, and the excess is also more than two standard errors above the excess of each control (the recall rule and the strict surface reader). The post reports this as a resemblance between mistakes and claims nothing more from it.
- **Same problems** is reported with the controls beside it and carries no verdict, because problems that are easy for one solver tend to be easy for all.
- **Expected shape, written down so a surprise is visible** (from the old run): room zero at depths 2 and 3, where lookahead is perfect; the best program somewhere between .4 and .6 at depths 4 and 5; the model unknown under the new question and five tries.

## Code

A folder `fe/` beside `cube/` with the same layout: a package with one idea per file (the identities and substitutions; the proof check; the shortest-proof search, with a plain try-everything version for tests; the problem builder; one file per program; the question; the answer reader), four stage scripts, and tests of the same four kinds. The cube's model-run, check, scoring and report code is copied in and adapted; it is not shared until the cube run has finished, so that nothing under a running experiment changes.

## Spending

| Stage | Ceiling | Basis |
|---|---|---|
| 1 and 2. CPU pod | $10, approved 2026-11-12 | The old build took about 10 minutes on 32 cores for 10,000 attempts; $1.12 an hour when last read |
| 3. Probe | $8, approved 2026-11-12 | One card for at most an hour, as for the cube |
| 3. Model run | $250, approved 2026-11-12 | 6,000 answers. At 8,000 tokens of thinking the cube's first measurement projects about $36 for 8,500 answers on one card; a larger allowance costs in proportion. To be looked at again once the allowance is chosen |

The run is set up for speed, not cost: the answers are independent of each other, so the number of cards is whatever finishes fastest, as for the cube. Spreading the work over more cards shortens the run and leaves the total about the same. Prices and stock are read again and stated before anything is created; every pod is stopped when done and none is deleted.

## Not in this experiment

Hints; answers that give a whole proof; problems that start part-way through a proof; which-of-two-is-closer; other models; thinking off or other allowances; saving internal activity; any study of the model's thinking (the text is saved so this can be done later without a new run).

## Known differences from the cube, and why

- 300 problems per level against 100: there are four depths against 17 distances, so each depth has to stand on its own.
- The options-only line is expected to sit above guessing: some substitutions are right more often than others. On the cube it must sit within .05 of guessing.
- A narrow-and-deep search program: specific to this puzzle.
- Problems are built from templates with a planted route; the cube's states come from random cubes.
- A time limit on the search for each problem, with a rule that stops the build if more than 1% run out.
