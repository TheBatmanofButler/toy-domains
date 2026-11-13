# Post 1, the cube experiment: plan and outcome rules

Written 2026-11-12. Numbers in square brackets refer to a private working log that is not part of this repository.

## What the experiment is for

It demonstrates the ladder end to end on one puzzle with an answer key nobody can argue with. It is not a search for taste [33]. The claim stays in its ceiling form: whatever the model scores beyond the best simple program is the most that could be taste. The post also uses the cube to show what a fair test of taste needs: an exact answer key, room above the simple programs, and evidence that judgment can reach the answers. The cube has the first two and mostly lacks the third [34].

## The puzzle

- **What the solver sees.** A scrambled 3x3 cube drawn flat, plus the same cube as a string of 54 sticker letters. It picks one of 18 turns: six faces, each a quarter turn either way or a half turn.
- **What counts as right.** A turn is right if it is the first turn of a shortest possible solution. A half turn counts as one move. This comes from a perfect solver (Rokicki's nxopt at the old run's exact version, with its 22.8 GB table). The rebuilt solver reproduced the old run's answers on 60 of 60 states in the pilot (pilot of 2026-11-12, kept outside this repository).
- **One scoring rule.** An answer is right or wrong. Nothing graded [43].

## The states

- **Test set:** 100 different states at each distance from 2 to 18 turns from solved, 1,700 in all. Distance 1 is left out: only 18 cubes are one turn from solved, and the case adds little.
- **How they are drawn.** Take a uniformly random valid cube and have the perfect solver solve it. For distances 17 and 18, use random cubes that are that far away. For distances 2 to 16, use the state the solver passes through at that distance ("following random cubes home"). Each random cube supplies one test state only.
- **What the post must say.** The states at 2 to 16 are ones a perfect solver visits, not typical states at that distance.
- **Training set:** up to 1,000 different states per distance from other cubes, used only to train the surface readers. It never contains a test state. Close to solved there are few cubes (243 at distance 2), so the training set there is whatever is left after the test states are taken.
- **Known oddity.** In the pilot, states 18 away had about five right turns each (15 states), so guessing scores about .29 there against about .06 elsewhere. Random cubes also land at 16 (3.5%) and 19 (2%); those are not used.

## The simple programs

| Rung | Program | Decision |
|---|---|---|
| Guessing | Share of the 18 turns that are right | |
| Options only, and lookup | The turn that is right most often in other states. One line, because the 18 options never change | [32] |
| Recall | First move of a scripted speedsolving method, in two versions (first layer on the top face; on the bottom face). Both reported | [31] |
| Surface, strict | Logistic regression on the 54 stickers as they are now, with separate weights for each turn. Never sees the result of a turn | [30] |
| Surface, relaxed | The old run's reader: whole-cube counts before and after each turn. One turn of lookahead with a learned score | [29, 30] |
| Search | Lookahead of up to 1, 2 and 3 turns, scoring the end cube by pieces in place, then stickers in place. It stops as soon as it sees a solved cube | [28] |

No neural network is on the ladder [30]. Ties are scored as the share of tied-best turns that are right, as in the old run.

**Room** at each distance is one minus the best simple program, counting all of them [35].

## The model

- **Model:** the standard Qwen model used in the old runs (Qwen3.8-27B, same version), thinking on.
- **Question:** the old layout, ending with: "A move is correct if it is the first move of a shortest possible solution. Each of the 18 allowed moves counts as one move, so a 180 degree turn counts as one. Give one correct move, written exactly as it appears in the list of allowed moves. Answer with `MOVE: <move>`." The distance is not given [39].
- **Thinking allowance:** 8,000 tokens. If it runs out, the thinking is closed and the model answers from what it has so far. Where the model's makers publish a way of doing this, theirs is used; for Qwen that is the sentence its makers insert at the end of the thinking ("Considering the limited time by the user, I have to give the solution based on the thinking directly now."), to be confirmed in this model version's documentation. A model with no published way gets one fixed neutral sentence, the same for every such model.
- **Tries:** five per state, with the temperature and companion settings the model's makers recommend for thinking mode, read from the model's own documentation and recorded [44].
- **Total:** 1,700 states x 5 tries = 8,500 answers.
- **What is kept:** the exact text and tokens of every question, all thinking and every answer, with model version and settings. No internal activity is extracted now [45].

## Scoring and reporting [44, 41]

- An unreadable answer counts as wrong, and the model is not asked again. The unreadable share is reported at each distance. The thinking is cut short only when the allowance runs out before an answer.
- A state's score is the share of its five tries that are right. A distance's score is the average over its 100 states.
- State by state: the model "gets" a state when at least three of five tries are right. For each simple program and each distance, four counts: both, only the model, only the program, neither, with the number expected by chance.
- Budgets, each in its own units: the model's allowance, tokens actually used and share of forced answers at each distance; each lookahead's number of positions examined. One common figure, as an upper limit only: the most cubes the model could have written out in its tokens. The post says this places the model among the programs and does not rank them on equal terms.

## The stages, who runs them, and what counts as each outcome

Every stage is run from a written brief. Its report is unconfirmed until it has been reviewed. Nothing is a number for the post before that.

### Stage 1. Build the states (CPU pod)
- **Must hold, or the stage stops:** the rebuilt solver matches the old run's distance and right turns on 60 old states; every state is a valid cube and is at its intended distance; exactly 100 test states per distance, all different; no random cube supplies two test states; no test state appears in the training set; every state has at least one right turn.
- **Reported as found:** right turns per state at each distance; solver time.

### Stage 2. Run the simple programs (no pod)
- **Checks on the programs themselves:** guessing equals the average share of right turns; lookahead of up to k turns scores 1.0 at every tested distance of k or less (this tests the stopping rule); the options-only line is within .05 of guessing at every distance. If it is not, something other than the cube is giving answers away: stage 2 reports this first, and the later stages wait for a decision.
- **Reported as found:** every program at every distance, and room at every distance.
- **No pass-or-fail verdict on the experiment.** A distance with little room is a point on the curve, not a failure. The 30% line is used only to describe the curve: at which distances room is under 30%, and at which it is over.

### Stage 3. The model run's check on itself
There is no separate pilot. The full run pauses after its first 100 answers and checks four things. If all hold it carries on without waiting; if one fails it stops and reports. Those 100 answers are part of the real data.
- Every record is complete: question, thinking, answer, token count.
- Forced answers come back readable about as often as unforced ones. (This is the first time the follow-up path meets the real model server.)
- No more than 15% of answers are unreadable.
- The projected cost of the whole run is under the ceiling.

The same 100 answers give the speed, which sets the number of cards. A high share of forced answers does not stop the run: at one chosen budget a forced answer is the model's answer, and the share is reported.

### Stage 4. Full model run (GPUs)
- **Card:** the best available, in the order B300, B200, H200. The number of cards is whatever finishes fastest [46, 47].
- **How the result is read, at each distance** (with margins of error; the exact rule for "above" is given below the three cases):
  - *Model at or below the best simple program, and few states that only the model gets:* the simple programs account for what the model does here.
  - *Model above the best simple program, or clearly more only-the-model states than chance:* that gap is the ceiling on taste at this distance. The first rival explanation is more search than our programs do, which the later budget runs address.
  - *Model above the simple programs at the far end (about 10 turns or more):* treated as suspect first. Check the scoring and the answer key on those states before believing it.
- **Expected shape, written down so a surprise is visible:** simple programs near perfect at distances 2 and 3, fading to guessing by about 8; the model unknown.

## Spending

| Stage | Ceiling | Status |
|---|---|---|
| 1. CPU pod | $10 | approved 2026-11-12 |
| 4. Full run | $300 | approved 2026-11-12 |

Hourly prices read 2026-11-12: CPU pod $1.12; B300 $8.99 per card; B200 $7.99; H200 $5.29. With the number of cards chosen for speed, the hourly rate could reach about $72 (eight B300). Price and stock are read again before anything is created and written into the run's log; every pod is stopped when done, none is deleted, and no pod from another run is touched.

## Not in this experiment (noted for later)

Thinking off and larger allowances; a check of whether the model can apply one turn; a small neural network as a check on the ladder; rotated cubes, sequences of turns, and which-is-closer; closer-same-further scoring; saving internal activity; other puzzles.
