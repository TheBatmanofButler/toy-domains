# Test fixtures

Small samples of saved output, copied once so the tests can run without the solver or the old archive.

- `pilot_random_cubes.jsonl`: 200 uniformly random cubes from the solver timing pilot of 2026-11-12, with the
  distance and shortest solution the pilot's solver wrapper reported.
- `pilot_random_cubes_nxopt.in`, `.log`: the exact input lines nxopt read for those 200 cubes and its printout
  (the program's folder was removed from the first two lines of the printout; nothing else was changed).
- `pilot_within_K.jsonl`, `pilot_within_K_nxopt.in`, `.log` (K = 0, 1, 12): nxopt asked whether each cube can
  be solved within K turns, for neighbours of the pilot's states; `solved` and `solution` are the pilot
  wrapper's reading.
- `pilot_path_states.jsonl`: 355 states found by following 20 random cubes home, distances 1 to 18, with the
  right turns the pilot found.
- `old_run_states.jsonl`: the 60 states of the earlier cube run that the pilot reproduced, with that run's
  distance, right turns, the scripted method's whole solution in both versions (`method_top`, first layer on
  U; `method_bottom`, on D), and its lookahead scores at depths 1 to 3 (old lookahead, which does not stop at
  solved; these states are 12 to 16 turns away, so stopping never applies).
- `old_run_question.json`: the old run's question text and role line for one cube, made with the old run's
  own code.
- `question_for_fixed_cube.txt`: the question this code builds for that cube, saved after it was read by eye.
