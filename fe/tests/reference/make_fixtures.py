"""Makes the saved test material in tests/fixtures/ from the earlier run of this puzzle. Run once, by hand:

    python3 -I tests/reference/make_fixtures.py ARCHIVE tests/fixtures

ARCHIVE is the earlier run's folder (holding code/ and results/deep/). Everything written comes from the
earlier run's own files and its own code (its renderer for the text of identities, its candidate list, its
surface reader's inputs); nothing comes from fe_ladder, so the tests compare the rebuilt code against the
earlier run and not against itself. Run with -I so that nothing in the current folder is imported by accident.
"""
import json
import sys
from pathlib import Path

POOLS = ("deep_K3", "deep_K4", "deep_K5")
NAMES = ["x=0, y=0", "y=0", "x=0", "y=x", "y=-x", "swap x,y", "y=1", "x=x+y, y=-y", "y=x+y", "x=1", "x=-x", "y=-y",
         "x=x-y, y=x+y"]
FEATURE_NAMES = ([f"sigma_{s}" for s in range(1, 14)] + ["target_derived", "atoms_before", "atoms_after",
                 "goal_matched_after", "introduces_const", "depth_so_far", "new_f_atoms", "new_mono_atoms"])


def attempt_of(row):
    return int(row["id"].rsplit("-", 1)[1])


def main(archive, out):
    archive, out = Path(archive), Path(out)
    sys.path.insert(0, str(archive / "code"))
    from fe.core import _apply, _ivec, ident_from_json
    from fe.deep import bfs
    from fe.deep.pol import featurize_state
    from feh.identity import render_identity
    from feh.render import SYSTEM_TEXT

    def rows_of(name, folder="pools"):
        with open(archive / "results" / "deep" / folder / f"{name}.jsonl") as f:
            return [json.loads(line) for line in f if line.strip()]

    def problem_fields(row):
        equation, goal = ident_from_json(row["identities"][0]), ident_from_json(row["goal"])
        options = []
        for c in row["candidates"]:
            (i, s), = c["pairs"][:1]
            result = _apply(equation, s)
            options.append({"result": render_identity(_to_json(result)), "moves": [[i, NAMES[t - 1]] for i, t in c["pairs"]]})
        return {"id": row["id"], "seed": int(row["id"].split("-")[1]), "attempt": attempt_of(row),
                "equation": render_identity(row["identities"][0]), "goal": render_identity(row["goal"]),
                "options": options, "right_moves": [c["cls"] for c in row["candidates"] if c["live"]]}, equation, goal

    def _to_json(identity):
        return [[0, str(a[1]), str(a[2]), str(a[3]), str(c)] if a[0] == 0 else [1, a[1], a[2], str(c)] for a, c in identity]

    by_pool = {name: sorted(rows_of(name), key=attempt_of) for name in POOLS}
    scores = {r["id"]: r for name in POOLS for r in rows_of(name, "ladder")}

    # 1. The 20 lowest attempts at each of depths 3, 4, 5, with the earlier run's search results and lookahead scores.
    with open(out / "earlier_problems.jsonl", "w") as f:
        for name in POOLS:
            for row in by_pool[name][:20]:
                fields, _, _ = problem_fields(row)
                ladder = scores[row["id"]]
                fields.update(depth=row["k"], proofs=row["closing_seqs"], sequences=row["total_seqs"],
                              score_only_lookahead={"1": ladder["G"], "2": ladder["G2"], "3": ladder["G3"]})
                f.write(json.dumps(fields) + "\n")

    # 2. 50 problems with the earlier surface reader's inputs on the page of the equation: the next lowest attempts.
    with open(out / "earlier_surface_inputs.jsonl", "w") as f:
        for name, how_many in zip(POOLS, (17, 17, 16)):
            for row in by_pool[name][20:20 + how_many]:
                fields, equation, goal = problem_fields(row)
                bfs.reset()
                page = [bfs.intern(equation)]
                candidates = bfs.ordered_candidates(page, 13)
                post, _ = featurize_state(page, frozenset(_ivec(goal)), candidates)
                fields.update(input_names=FEATURE_NAMES, inputs=post)
                f.write(json.dumps(fields) + "\n")

    # 3. One question text, with the problem it was built for.
    with open(archive / "results" / "deep" / "prompt_audit_dump.jsonl") as f:
        dump = [json.loads(line) for line in f if line.strip()]
    first = next(d for d in dump if d["readout"] == "first" and d["budget"] == "b0")
    pool = first["problem_id"].split("-")[0]
    row = next(r for r in rows_of(f"deep_{pool}") if r["id"] == first["problem_id"])
    fields, _, _ = problem_fields(row)
    (out / "earlier_question.json").write_text(json.dumps(
        {"id": row["id"], "equation": fields["equation"], "goal": fields["goal"], "system_text": SYSTEM_TEXT,
         "user_text": first["user_text"]}, indent=1) + "\n")

    # 4. 50 problems with the attempt that made them: the lowest attempts over the three sets.
    every = sorted((r for name in POOLS for r in by_pool[name]), key=attempt_of)[:50]
    with open(out / "earlier_attempts.jsonl", "w") as f:
        for row in every:
            hidden = row["hidden"]
            f.write(json.dumps({"id": row["id"], "seed": int(row["id"].split("-")[1]), "attempt": attempt_of(row),
                                "family": row["sol_family"], "equation": render_identity(row["identities"][0]),
                                "goal": render_identity(row["goal"]),
                                "first_chain": [NAMES[s - 1] for s in hidden["A_sigmas"]],
                                "second_chain": [NAMES[s - 1] for s in hidden["B_sigmas"]]}) + "\n")
    print("written to", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
