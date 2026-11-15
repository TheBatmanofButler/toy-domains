"""Check of the built problem files. Uses the code's own functions; changes nothing."""
import sys, json, time, multiprocessing
from collections import Counter
from pathlib import Path
FE = str(Path(__file__).resolve().parents[3]); RES = str(Path(__file__).resolve().parents[2])   # the code folder; data/
sys.path.insert(0, FE)
from fe_ladder.identities import problem_key
from fe_ladder.identity_text import read_identity, write_identity
from fe_ladder.moves import options
from fe_ladder.shortest import solve, DEPTH

def load(p): return [json.loads(l) for l in open(p) if l.strip()]

def resolve(p):
    t = time.monotonic()
    s = solve(read_identity(p["equation"]), read_identity(p["goal"]), 5)
    return p["id"], s.outcome, s.depth, s.right, time.monotonic() - t

def main(budget_s):
    test, train = load(RES + "/test_problems.jsonl"), load(RES + "/train_problems.jsonl")
    out = []
    out.append(f"test per depth: {dict(sorted(Counter(p['depth'] for p in test).items()))}")
    out.append(f"train per depth: {dict(sorted(Counter(p['depth'] for p in train).items()))}")
    ids = [p["id"] for p in test + train]
    out.append(f"ids unique across both files: {len(ids) == len(set(ids))} ({len(ids)} ids)")
    key = lambda p: repr(problem_key(read_identity(p["equation"]), read_identity(p["goal"])))
    tk, rk = [key(p) for p in test], [key(p) for p in train]
    out.append(f"test problems all different by problem_key: {len(set(tk)) == len(tk)}")
    out.append(f"training problems all different by problem_key: {len(set(rk)) == len(rk)}")
    out.append(f"test problems found in training set: {len(set(tk) & set(rk))}")
    bad_right = [p["id"] for p in test + train
                 if not p["right_moves"] or not all(isinstance(i, int) and 0 <= i < len(p["options"]) for i in p["right_moves"])]
    out.append(f"problems with empty right_moves or a right move outside its options: {len(bad_right)} {bad_right[:5]}")
    # options recomputed from the equation text with the code's options()
    def opts(p):
        return [{"result": write_identity(o.result), "moves": [list(m) for m in o.moves]} for o in options([read_identity(p["equation"])])]
    bad_opts = [p["id"] for p in test + train if opts(p) != p["options"]]
    out.append(f"problems whose saved options differ from options recomputed from the equation: {len(bad_opts)} {bad_opts[:5]}")
    out.append(f"records with seed != 20261112: {sum(p.get('seed') != 20261112 for p in test + train)}")
    print("\n".join(out), flush=True)
    # solve again
    by = {d: [p for p in test if p["depth"] == d] for d in (2, 3, 4, 5)}
    todo = by[2] + by[3] + by[4][:50] + by[5][:50]
    rec = {p["id"]: p for p in todo}
    start = time.monotonic(); done = Counter(); mism = []; secs = Counter()
    with multiprocessing.Pool(2) as pool:
        for pid, outcome, depth, right, s in pool.imap(resolve, todo, chunksize=1):
            p = rec[pid]; done[p["depth"]] += 1; secs[p["depth"]] += s
            if outcome != DEPTH or depth != p["depth"] or right != p["right_moves"]:
                mism.append((pid, outcome, depth, right, p["depth"], p["right_moves"]))
            if time.monotonic() - start > budget_s:
                pool.terminate(); print("time budget reached; stopped", flush=True); break
    print(f"solved again per depth: {dict(sorted(done.items()))} (wanted 300, 300, 50, 50); wall {time.monotonic()-start:.0f}s; "
          f"solver seconds per depth {dict((d, round(v)) for d, v in sorted(secs.items()))}")
    print(f"mismatches in depth or right moves: {len(mism)} {mism[:5]}")

if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 1800)
