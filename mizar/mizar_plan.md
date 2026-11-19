# Post 1, Mizar: plan and outcome rules

Written 2026-11-14. It follows `cube/cube_plan.md` wherever it can; the differences are listed near the end. Every number here is a count from downloaded files or a figure from a paper. None is a result.

## What the experiment is for

It is the last puzzle of post 1 and the first on real theorems. The cube and functional equations have an exact answer key. TPTP shows that small algebra problems are too small for the question to arise. Here the problems are theorems from a library people wrote, and the task is the one post 2 uses in Lean: pick the fact this proof needs. It asks two things:

1. Where does the model sit against the simple programs, with the author's proof as the answer key?
2. Does that position change when the same answers are scored again with a prover as the judge?

The second question can be asked here and cannot be asked in Lean. That is the reason Mizar comes before Lean. The claim stays in its ceiling form: whatever the model scores beyond the best simple program is the most that could be taste.

## The puzzle

- **What a problem is.** A theorem from the Mizar library; the facts its author cited in the proof, with one of them held back; and 30 options, one of which is the held-back fact.
- **What the solver sees.** The theorem's statement, the statements of the cited facts that are given, and the 30 options as numbered statements.
- **What counts as right (the author's key).** The option the author cited. One right answer in 30.
- **What counts as right (the prover's key), used only for the second table.** An option is right if the prover cannot prove the theorem from the given facts within its limit, can once that option is added, and the option appears in the proof it finds.
- **One scoring rule.** An answer is right or wrong.

## The problems

- **The library.** Mizar library version 4.181.1147, in the form the prover community publishes: every statement in the provers' format, one problem file per theorem, and a file listing the facts each author's proof refers to. Downloads and checksums are in the code specification.
- **Which theorems ("well-known").** The 33 articles the Mizar library needs to prove the Bolzano-Weierstrass theorem: sets, relations, functions, orderings, lattices and basic topology. They are also the most used benchmark for this task (MPTP2078). The rule is "every theorem in those articles that passes the next rule". Nothing is picked by hand.
- **Which theorems are usable.** The author cites at least two different facts, at least one of them an earlier theorem or lemma.
- **Which fact is held back.** One cited theorem or lemma, drawn at random with the seed. Never a definition and never a background fact, and never a fact that reads the same as the theorem or as another fact the author cited. Each theorem supplies one problem.
- **What is given.** The author's other cited facts, shown to the solver. The prover is given those and also the background facts in the theorem's problem file, which it needs and which the author never wrote.
- **The 29 wrong options.** Drawn at random, with the seed, from the theorems and lemmas stated before the theorem in the same article as the right option, leaving out any fact the author cited, any statement identical to the right option, to the theorem or to a given fact, and any repeat of a statement already among the candidates. "Identical" is judged on the statement and on the text the solver is shown, because Mizar gives one name to several symbols. Nothing else is matched in this first run. A theorem whose right option has fewer than 29 such neighbours is not used.
- **Supply, as first counted** (a guide): 1,555 usable theorems in the 33 articles, of which about 1,200 have 29 wrong options under this rule.
- **Test set:** 300 of those, drawn at random with the seed.
- **Training set** for the programs that learn: every other theorem of the 33 articles that qualifies (about 900), built the same way. Test and training problems come from one pool and never share a theorem, as the cube's test and training states do. Training problems are therefore neighbours of test problems; that is intended, since a model that has read the library has seen those neighbours too.
- **Seed:** 20261112, the cube's.
- **Nothing dropped silently.** Every theorem in the 33 articles ends in one bin: not usable, too few wrong options, or a problem.

## The simple programs

| Rung | Program |
|---|---|
| Guessing | 1 in 30 |
| Options only | A reader trained on the options alone, never shown the theorem |
| Recall | The option cited most often in the rest of the library |
| Lookup | The option that was the right answer most often in the training problems |
| Surface, symbols | The option sharing the most symbols with the theorem, rare symbols counting more |
| Surface, trained | A reader trained on the theorem, the given facts and the options: shared symbols, lengths, which other theorems cite an option together with a given fact, how far above the theorem an option is stated |
| Search | For each option, the prover tries to prove the theorem from the given facts plus that option. Pick an option with which it succeeds; if none, guess |

No neural network is on the ladder. Ties are scored as the share of tied-best options that are right. **Room** is one minus the best simple program, counting all of them.

Under the prover's key the search program is the judge itself, so it is left out of the second table.

## The prover

- **Which.** E 2.6, the pinned version already set up for TPTP, with one fixed setting and one limit.
- **The limit** is 4,000 processed clauses: a number of steps, not a time, so that it does not depend on the machine. It was chosen after the prover's key had been made at 1,000 and at 4,000 on the test problems, with no model involved: at 4,000 the search program is stronger and the prover has right options for more problems (88 against 74), at the price of more problems on which a safety cap stops the prover before the limit does (41 against 4). Above 4,000 that cap stops most calls. The run at 1,000 is kept beside it.
- **Every call records how it ended.** A call ended by a memory, term or time cap is never counted as "does not prove".
- **Every call is made twice.** The prover's search is not exactly the same from one run to the next. Where the two runs disagree on the verdict, the call decides nothing, and the share of such calls is reported. So the prover's figures, like the model's, can differ a little between two runs of the experiment.
- **Four bins for the prover's key.** Proved from the given facts alone (the held-back fact is not needed by this prover: no right answer under its key); not proved alone and at least one option right; not proved with any option; stopped for another reason (a call that would decide the bin ended on a cap, or differed between two runs), with the reason recorded. "Not proved" means the prover reached its limit or finished its search with no proof. The second table is over the second bin only, and all four counts are reported.

## The model

- **Model:** the standard Qwen model used for the cube and functional equations, thinking on.
- **Question:** the theorem, the given facts, the 30 options in an order set by the seed, ending: "Exactly one of these facts is cited in the author's proof of the theorem, together with the given facts. Give its number. Answer with `FACT: <number>`."
- **How statements are shown.** In the provers' notation, with each coded symbol replaced by the name the Mizar library gives it (for example `k3_xboole_0` becomes `/\`). Facts are shown by statement only, without their library labels.
- **Thinking allowance:** chosen after a probe on this puzzle, as for functional equations. Enforced as in the cube run.
- **Tries:** five per problem, the cube run's settings.
- **What is kept:** the exact text and tokens of every question, all thinking and every answer.

## Scoring and reporting

As for the cube: unreadable answers count as wrong; a problem's score is the share of its five tries that are right; every score has a standard error; problem by problem (both, only the model, only the program, neither, with the count expected by chance); the same-wrong-answers comparison with its shuffle figure and controls.

There are no levels like the cube's distances. Scores are also reported by number of facts the author cited (2 to 3, 4 to 6, 7 or more) and by article group (sets, relations and functions; orderings and lattices; topology).

New for this puzzle:
- **The second table.** The same answers and picks, scored with the prover's key, on the problems where that key has a right answer.
- **How the keys relate.** On those problems: how often the author's option is right under the prover's key; how many of the 29 "wrong" options are right under it; how often an option made the prover succeed without appearing in its proof (one number, not discussed further).

## The stages and what counts as each outcome

### Stage 1. Build the problems (no pod)
- **Must hold, or the stage stops:** every cited fact is in the theorem's problem file and stated earlier; every option is stated earlier than its theorem; no option is a fact the author cited, other than the right one; no theorem in both the test and the training set; every theorem in the 33 articles is in exactly one bin; building twice from the seed gives the same files.
- **Reported as found:** the bins; options by where they came from; how close the wrong options are to the right one on each matched quantity.

### Stage 2. The simple programs and the prover (CPU pod)
- **Checks on the programs:** guessing is 1 in 30; the share of prover calls on which two runs disagreed is reported.
- **Reported first, and nothing waits on it:** how far the options-only reader and the recall rung sit above guessing. The wrong options are not matched on how often they are cited, so both may sit well above it. That is shown on the ladder as what it is: how much of the answer can be had without reading the theorem.
- **Reported as found:** every program; room; the three prover bins.

### Stage 3. The model run (GPUs)
The functional-equations way: a probe of 32 training problems for the thinking allowance, then the run with the cube's checks after the first 100 answers.
- **The thinking allowance is 16,000 tokens** (the cube's is 8,000). The probe is the reason: left alone on 30 training problems, the model finished its thinking within 8,000 tokens on 2, within 16,000 on 7 and within 32,000 on 15, with a middle of about 32,000. At 8,000 nearly every answer would be one the model was made to give before it had finished thinking; 32,000 would still cut half of them and costs most. Thinking that reaches the allowance is closed by the server and the model answers from there, as in the cube; the share of answers given that way is reported.
- **The answer allowance** is the cube's 1,000 tokens.

### Stage 4. The report
- **The model is above a program** when the gap on the same problems is more than two standard errors of the gap.
- **The second table is read in two cases.**
  - *The model's position against the simple programs is the same under both keys* (above the same programs, below the same programs): the author's key is a fair stand-in here. Post 2 says so when it uses it in Lean.
  - *The position changes:* the main Mizar table becomes "right under either key". The report then looks for a rule, needing no prover, that picks the problems where the keys agree, so that it can be carried to Lean; and post 2 adds Lean's own re-check of the author's proof with an option swapped in.
- **Expected shape, written down so a surprise is visible:** from the Lean pilots, the trained surface reader somewhere near .6 and the options-only reader near guessing. The model and the prover bins: unknown.

## Spending

| Stage | Ceiling | Basis |
|---|---|---|
| 1 and 2. CPU pod | $5 | 300 problems at 31 calls each, made twice: about 18,600 calls of under a second each |
| 3. Probe | $8 | As for functional equations |
| 3. Model run | to be set after the probe | 300 problems x 5 tries = 1,500 answers; the cube's run was 8,500 |

Prices and stock are read again and stated before anything is created; every pod is stopped when done and none is deleted.

## Not in this experiment

The prover given double its limit. Any study of facts that help without being used, beyond the one number above. Renaming (post 2). Wrong options matched on how often they are cited, or scored against random ones (post 2). Hints. Other models. A second prover. The library outside the 33 articles as test problems. Lean.

## Known differences from the cube, and why

- **The answer key is the author's choice, not exact.** That is what real theorems cost, and the second table measures how much it matters.
- **The options are a sample of 30,** not every legal move: the earlier facts run to thousands.
- **Wrong options come from the right option's own article.** On the cube the 18 turns are fixed. Here they are drawn from nearby theorems so that they are about the same subject. They are not matched further in this run; post 2 tightens this in Lean.
- **No levels.** Scores are broken down by number of cited facts and by article group.
- **The prover's limit is one fixed number,** as the cube's lookahead depths are.
- **The search program uses a prover,** and the same prover is the second judge.
- **One problem per theorem,** as one test state per random cube.
