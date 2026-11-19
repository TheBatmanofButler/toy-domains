# Test fixtures

Saved material, made once by `tests/reference/make_fixtures.py` (`python3 -I tests/reference/make_fixtures.py
--library FOLDER`) and, for the prover's outputs, by `tests/reference/make_prover_fixtures.py` (with `--library`
and `--prover`), so the tests can run without the library's files or the prover.

- `made_up_library/`: a library of four small articles in the real files' formats (`statements`, `seq`,
  `00mizrefs`, `00constrnames`, `problems_small_consist/`, and a one-line `xboole_1.miz`): `xboole_0` and
  `xboole_1` are the articles test and training problems are both drawn from; `basic_0` and `later_0`
  are the rest of the library. Its bins, problems and options are
  worked out by hand at the top of `tests/test_problems.py`.
- `real_pieces/`: small pieces of each real file, cut so that they still form a library the code can read: the
  problem files of t1_xboole_1 to t5_xboole_1 and t83_xboole_1 as they are, the lines of `statements` and `seq`
  for every fact named in them (in the real order), their lines of `00mizrefs`, every line of `00constrnames` for
  a symbol in those statements, and the first 60 lines of `xboole_1.miz`.
- `shown_statements.json`: ten real statements, each with the text `statements.show` must give for it. The
  expected texts were written by hand from the statements and the name table (they are in the script as
  written), not by running `show`; one has a symbol with no Mizar name (`o_0_0_xboole_0`), and three have names
  with brackets (`[..]`, `[:..:]`), written in front of their arguments.
- `fixed_problem.json`: one real problem, t70_zfmisc_1 built with seed 20261112 (id `test-fixed`).
- `question_for_fixed_problem.txt`: the question built for it, saved after it was read by eye.
- `endings.json.gz`: one real output of each of the seven endings on these problems, as the prover printed it
  (lines on time and memory used and the input file's name still in), with the limit, arguments and input. All
  but two were made with the pinned command line: the memory cap with a cap of 1 MB (the real cap is not reached),
  `unreadable` with an input with a syntax error. Two are clause-limit outputs; in one (the whole problem file of
  t47_knaster) the clauses printed as processed exceed the limit.
- `proofs.json.gz`: three real proofs, with the facts each uses as read by a plainer method than the code's.
- `input_text_fixed_problem.txt`: the prover's input for the fixed problem with its held-back option, read by
  eye; `input_parts_fixed_problem.json`: the facts, option and theorem it was made from.
