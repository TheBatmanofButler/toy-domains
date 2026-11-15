# Test fixtures

Saved once, so that the tests run without the prover or the earlier pilot's folder. Everything except
`tptp/`, `made_up_library/` and `input_text_GRP001-2.txt` was made by `tests/reference/make_fixtures.py`
(seed 20261112), with the copy of the earlier code in `tests/reference/` and the pinned prover.

- `tptp/`: five real files of TPTP v9.3.1, in the library's own layout, copied unchanged: `GRP001-4.p`
  (usable, no includes), `GRP001-2.p` (usable, includes `Axioms/GRP004-0.ax`, also here), `GRP001-5.p` (a
  statement that is not a single equation), `GRP664-10.p` (a goal of two statements), `GRP112-10.p` (status
  Satisfiable).
- `endings.json`: one real output of each of the seven endings. `proved` and `clause limit` are outputs the
  earlier pilot kept. The others were made once with the pinned prover: `nothing left` and `term cap` with the
  pinned command line; `time cap` with a cap of 1 second and no term cap or clause limit, and `memory cap` with
  a cap of 1 MB, because the real caps are not reached within a few seconds; `unreadable` is the prover's answer
  to an input with a syntax error. Each record holds the arguments (null for the pilot's) and the input.
- `pilot_calls.jsonl.gz`: 200 calls of the single-fact pilot at the limit of 160: 25 problems whose 30 options
  were all tried (the unaided call and 6 options each) and 25 whose unaided call proved the goal, each with the
  input as the pilot's code built it, the goal as the pilot denied it, the pilot's result and its full output.
- `pilot_equations.jsonl.gz`: 1,000 equations from the pilot's saved problems with the earlier code's keys
  (one equation, and one equation as an axiom set), size, variables, and whether each is an instance of a
  second equation of the same axiom set.
- `pilot_derived.json`: for 20 of the pilot's axiom sets, the facts the pilot's harvest derives, filtered as
  its bank was before any topping-up, and how many of them are in the pilot's saved bank (all are). Made with
  no memory setting in the prover's environment (see `ENVIRONMENT` in `tptp_count/prover.py`).
- `borderline_calls.jsonl.gz`: 50 calls of the single-fact pilot at the limit of 160, drawn with the seed: 25
  from the calls that proved in 140 or more processed clauses and 25 from those that stopped at the limit of
  160, each with the pilot's result. A change in the prover's search moves such calls across an ending first.
- `input_text_GRP001-2.txt`: the prover's input for GRP001-2 with one option, saved after it was read by eye.
- `made_up_library/`: twelve small made-up files (and one axiom file) for the count, report and end-to-end
  tests; their bins are worked out by hand in `tests/made_up.py`. Their headers give the TPTP version as 0.0,
  so that the version the count reads from a library is not taken for a real one.
