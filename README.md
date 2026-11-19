# Toy domains

Code and results for a [post](https://thebatmanofbutler.substack.com/p/testing-for-mathematical-taste-with?r=2da4v3&utm_campaign=post&utm_medium=web&showWelcomeOnShare=true) on telling apart what a language model does when it picks a good next step in a
piece of mathematics: memory, reading the surface, search, or something more. The method, from
[the earlier post](https://www.lesswrong.com/posts/hMsmMRagzPpFxJzBc/how-to-find-the-basic-sauce-if-there-is-one),
is to set the model beside a ladder of simple programs on the same questions and see whether it beats the best
of them.

There are four experiments, one per folder. Each stands alone, with its own README, plan, code, tests and data.

| Folder | The question put to the solver | Who says which answer is right | Model run |
|---|---|---|---|
| [`cube/`](cube/README.md) | On a scrambled Rubik's cube, which of the 18 turns starts a shortest solution? | A perfect solver | Yes |
| [`fe/`](fe/README.md) | Given a functional equation, a goal identity and 13 allowed substitutions, which first move starts a shortest proof? | Trying every sequence | Yes |
| [`tptp/`](tptp/README.md) | Given the axioms and goal of a small TPTP algebra problem and 30 derived facts, which fact lets the prover finish? | The E prover at a fixed limit | No: a count of how many problems are worth asking |
| [`mizar/`](mizar/README.md) | Given a Mizar theorem and all but one of the facts its author cited, which of 30 options is the missing fact? | The author's proof, and the E prover as a second key | Yes, with the original names and with every symbol renamed |

## What is in each folder

The four folders are laid out the same way:

- `*_plan.md`: the experiment in plain words, with what counts as each outcome.
- `code_spec.md`: what the code must do, file by file.
- A package (`cube_ladder/`, `fe_ladder/`, `tptp_count/`, `mizar_ladder/`) holding the code. Its `programs/`
  folder has one file per simple program on the ladder: guessing, lookup, recall, the surface readers and the
  search programs.
- `stages/`: one command per stage (build the problems, run the simple programs, run the model, write the
  report). Stages talk only through files in a data folder.
- `tests/`: one test file per code file, an end-to-end test, and stand-ins for the model server, the solver
  and the prover so that the tests need none of them.
- `data/`: what the stages wrote. The small result tables are kept; see below for what is not.

## Set up and run

Python 3.12 or later. Each folder has its own `requirements.txt`; work from inside the folder:

```
cd mizar
python3 -m pip install -r requirements.txt
python3 -m pytest
```

The ordinary tests need no special machine. To run the stages themselves, each folder's README gives the
commands and what must be on the machine:

- `cube/`: Rokicki's nxopt solver and its 22.8 GB table.
- `tptp/` and `mizar/`: the E prover, version 2.6, and the TPTP or Mizar library files.
- `fe/`: nothing else.
- The model runs (`cube/`, `fe/`, `mizar/`): one or more vLLM servers. The runs here used Qwen3.8-27B, each
  question asked five times.

## Where the results are

In each folder's `data/`: `report.txt` is the full set of tables, and the `.json` files beside it hold the same
figures for reading by code (`scores_by_distance.json` for the cube, `scores_by_depth.json` for the functional
equations, `bins.json` for TPTP, and `scores.json`, `second_table.json`, `counted_together.json` and
`renamed_t21000.json` for Mizar). `program_picks.jsonl` holds every simple program's pick on every problem.

Standard errors are across test problems; each README's "Margins of error" section says how they are worked
out and what they do not cover.

## What is not here

- The model's transcripts and the solver and prover logs (`cube/data/raw/`, `mizar/data/raw/`) are too bulky
  to track.
- Working notes (`decisions.md`, `private/`) are not published.
- The libraries and tools the stages read (the TPTP and Mizar files, the E prover, the cube solver's table)
  are not copied here; each README names the version and checksum used.

## License

MIT. See [`LICENSE`](LICENSE).
