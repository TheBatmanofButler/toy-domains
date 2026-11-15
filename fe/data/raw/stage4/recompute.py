"""Own recomputation of the stage 4 figures, from the raw answers, the picks and the test problems only.

Does not import fe_ladder.scoring, report, wrong_moves or run_settings. Uses fe_ladder.answers.read_move to read
a move; the move is matched to a problem's options by looking for [number, substitution] in each option's
saved `moves` list (the same lower-level rule as fe_ladder.answers.option_of, written out here; option_of is
also called once per answer only to confirm the two agree).
Usage: python3 -I checks/recompute.py FE_DIR DATA_DIR RESULTS_DIR OUT_JSON
"""
import json
import sys
from math import sqrt

FE, DATA, RESULTS, OUT = sys.argv[1:5]
sys.path.insert(0, FE)
from fe_ladder.answers import read_move, option_of  # noqa: E402


def mean(v):
    return sum(v) / len(v)


def se(v):
    n = len(v)
    if n < 2:
        return None
    m = mean(v)
    return sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) / sqrt(n)


def jl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


problems = {p["id"]: p for p in jl(f"{DATA}/test_problems.jsonl")}
depths = sorted({p["depth"] for p in problems.values()})
ids_at = {d: sorted(i for i, p in problems.items() if p["depth"] == d) for d in depths}


def my_option(problem, move):
    for k, opt in enumerate(problem["options"]):
        if [move[0], move[1]] in opt["moves"]:
            return k
    return None


picks = {}
for p in jl(f"{DATA}/program_picks.jsonl"):
    picks.setdefault(p["program"], {})
    assert p["problem_id"] not in picks[p["program"]]
    picks[p["program"]][p["problem_id"]] = p
programs = sorted(picks)
pscore = {name: {i: sum(picks[name][i]["weights"][k] for k in problems[i]["right_moves"]) for i in problems}
          for name in programs}

# Read the answers, keeping only what is needed.
ans = []
mismatch = {"move": [], "option": [], "right": [], "option_of_disagrees": []}
with open(f"{DATA}/model_answers.jsonl") as f:
    for line in f:
        r = json.loads(line)
        prob = problems[r["problem_id"]]
        mv = None if r["failed"] else read_move(r["answer_text"])
        opt = None if mv is None else my_option(prob, mv)
        right = opt is not None and opt in prob["right_moves"]
        saved_move = None if r["move"] is None else tuple(r["move"])
        if (None if mv is None else tuple(mv)) != saved_move:
            mismatch["move"].append((r["problem_id"], r["try"], saved_move, mv))
        if opt != r["option"]:
            mismatch["option"].append((r["problem_id"], r["try"], r["option"], opt))
        if right != r["right"]:
            mismatch["right"].append((r["problem_id"], r["try"], r["right"], right))
        if mv is not None and option_of(prob, mv) != opt:
            mismatch["option_of_disagrees"].append((r["problem_id"], r["try"]))
        own = r["thinking_tokens_before_end_text"] if r["forced"] else r["thinking_tokens"]
        ans.append({"pid": r["problem_id"], "try": r["try"], "depth": prob["depth"], "move": mv, "opt": opt,
                    "right": right, "forced": bool(r["forced"]), "failed": bool(r["failed"]), "own": own,
                    "used": r["tokens_used"], "rec_depth": r["depth"]})
        del r

assert len(ans) == 6000
assert all(a["depth"] == a["rec_depth"] for a in ans)
by_pid = {}
for a in ans:
    by_pid.setdefault(a["pid"], []).append(a)
assert set(by_pid) == set(problems) and all(sorted(x["try"] for x in v) == [1, 2, 3, 4, 5] for v in by_pid.values())
model = {i: sum(a["right"] for a in by_pid[i]) / 5 for i in problems}
right_count = {i: sum(a["right"] for a in by_pid[i]) for i in problems}

out = {"mismatch_counts": {k: len(v) for k, v in mismatch.items()},
       "mismatch_examples": {k: v[:5] for k, v in mismatch.items()}, "depths": {}}
tpe = json.load(open(f"{DATA}/model_run_check.json"))["tokens_per_equation"]

for d in depths:
    ids = ids_at[d]
    here = [a for a in ans if a["depth"] == d]
    row = {"model": mean([model[i] for i in ids]), "model_se": se([model[i] for i in ids]),
           "programs": {n: mean([pscore[n][i] for i in ids]) for n in programs},
           "programs_se": {n: se([pscore[n][i] for i in ids]) for n in programs},
           "gap": {n: {"mean": mean([model[i] - pscore[n][i] for i in ids]),
                       "se": se([model[i] - pscore[n][i] for i in ids])} for n in programs},
           "answers": len(here),
           "forced_share": mean([a["forced"] for a in here]),
           "unreadable_share": mean([(not a["failed"]) and a["move"] is None for a in here]),
           "not_available_share": mean([a["move"] is not None and a["opt"] is None for a in here]),
           "failed": sum(a["failed"] for a in here),
           "thinking_tokens_mean": mean([a["own"] for a in here]),
           "tokens_used_mean": mean([a["used"] for a in here])}
    row["most_identities_written"] = row["tokens_used_mean"] / tpe
    best = max(row["programs"].values())
    row["best"] = sorted(n for n, s in row["programs"].items() if s >= best - 1e-12)
    row["room"] = 1 - best
    fo = [a for a in here if a["forced"]]
    un = [a for a in here if not a["forced"]]
    row["forced_n"], row["unforced_n"] = len(fo), len(un)
    row["forced_right"] = mean([a["right"] for a in fo]) if fo else None
    row["unforced_right"] = mean([a["right"] for a in un]) if un else None
    row["forced_right_count"] = sum(a["right"] for a in fo)
    row["unforced_right_count"] = sum(a["right"] for a in un)
    # Problem by problem for every program (brief asks for lookahead_2, lookahead_3, surface_strict).
    row["four"] = {}
    for n in programs:
        c = {"both": 0, "only_model": 0, "only_program": 0, "neither": 0}
        for i in ids:
            mg, pg = 2 * right_count[i] > 5, pscore[n][i] > 0.5
            c[{(1, 1): "both", (1, 0): "only_model", (0, 1): "only_program", (0, 0): "neither"}[(mg, pg)]] += 1
        p = (c["both"] + c["only_model"]) / len(ids)
        m = c["only_model"] + c["neither"]
        c["expected_if_independent"] = m * p
        c["expected_if_independent_se"] = sqrt(m * p * (1 - p))
        g = 0.0
        for i in ids:
            if not pscore[n][i] > 0.5:
                q = len(problems[i]["right_moves"]) / len(problems[i]["options"])
                g += sum(__import__("math").comb(5, k) * q ** k * (1 - q) ** (5 - k) for k in (3, 4, 5))
        c["expected_if_guessing"] = g
        row["four"][n] = c
    # Same wrong moves, for every program.
    wrong = {}
    left_out = 0
    for i in ids:
        for a in by_pid[i]:
            if a["move"] is not None and a["opt"] is None:
                left_out += 1
            if a["opt"] is not None and a["opt"] not in problems[i]["right_moves"]:
                wrong.setdefault(i, []).append(a["move"])
    row["left_out"] = left_out
    row["wrong_problems"] = len(wrong)
    row["wrong_tries"] = sum(len(v) for v in wrong.values())
    # Weight a program puts on a move on a problem; total over the depth for the shuffle.
    def w_on(n, i, mv):
        k = my_option(problems[i], mv)
        return 0.0 if k is None else picks[n][i]["weights"][k]
    moves_needed = {mv for v in wrong.values() for mv in v}
    swm = {}
    for n in programs:
        total = {mv: sum(w_on(n, i, mv) for i in ids) for mv in moves_needed}
        per = {}
        for i, mvs in wrong.items():
            match = mean([w_on(n, i, mv) for mv in mvs])
            wo = [k for k in range(len(problems[i]["options"])) if k not in problems[i]["right_moves"]]
            uniform = sum(picks[n][i]["weights"][k] for k in wo) / len(wo)
            shuffle = mean([(total[mv] - w_on(n, i, mv)) / (len(ids) - 1) for mv in mvs])
            per[i] = (match, uniform, shuffle)
        swm[n] = per
    row["wrong_moves"] = {}
    for n in programs:
        per = swm[n]
        exc = {i: per[i][0] - per[i][2] for i in per}
        r2 = {"match": mean([v[0] for v in per.values()]), "match_se": se([v[0] for v in per.values()]),
              "uniform": mean([v[1] for v in per.values()]), "shuffle": mean([v[2] for v in per.values()]),
              "excess": mean(list(exc.values())), "excess_se": se(list(exc.values())), "over": {}}
        for c in ("recall", "surface_strict"):
            if c != n:
                ce = {i: swm[c][i][0] - swm[c][i][2] for i in per}
                diffs = [exc[i] - ce[i] for i in per]
                r2["over"][c] = {"mean": mean(diffs), "se": se(diffs)}
        row["wrong_moves"][n] = r2
    out["depths"][d] = row

json.dump(out, open(OUT, "w"), indent=1, default=str)

# Compare with the stage's files.
sbd = json.load(open(f"{RESULTS}/scores_by_depth.json"))
pbp = json.load(open(f"{RESULTS}/problem_by_problem.json"))
wm = json.load(open(f"{RESULTS}/wrong_moves.json"))
diffs = []
compared = 0


def cmp(label, mine, theirs):
    global compared
    compared += 1
    if mine is None or theirs is None:
        if mine is not theirs:
            diffs.append((label, mine, theirs))
        return
    if isinstance(mine, list):
        if mine != theirs:
            diffs.append((label, mine, theirs))
        return
    if abs(mine - theirs) > 1e-9 or f"{mine:.3f}" != f"{theirs:.3f}":
        diffs.append((label, mine, theirs))


for d in depths:
    r, s = out["depths"][d], sbd[str(d)]
    cmp(f"{d} model", r["model"], s["model"])
    cmp(f"{d} model_se", r["model_se"], s["model_standard_error"])
    for n in programs:
        cmp(f"{d} {n} score", r["programs"][n], s["programs"][n])
        cmp(f"{d} {n} score_se", r["programs_se"][n], s["programs_standard_error"][n])
        cmp(f"{d} {n} gap", r["gap"][n]["mean"], s["model_minus_program"][n]["mean"])
        cmp(f"{d} {n} gap_se", r["gap"][n]["se"], s["model_minus_program"][n]["standard_error"])
    cmp(f"{d} best", r["best"], s["best_programs"])
    cmp(f"{d} room", r["room"], s["room"])
    for k, k2 in (("forced_share", "forced_share"), ("unreadable_share", "unreadable_share"),
                  ("not_available_share", "not_available_share"), ("thinking_tokens_mean", "thinking_tokens_mean"),
                  ("tokens_used_mean", "tokens_used_mean"), ("most_identities_written", "most_identities_written"),
                  ("forced_n", "forced_answers"), ("unforced_n", "unforced_answers"),
                  ("forced_right", "forced_share_right"), ("unforced_right", "unforced_share_right")):
        cmp(f"{d} {k}", r[k], s[k2])
    for n in programs:
        f, t = r["four"][n], pbp[n][str(d)]
        for k in ("both", "only_model", "only_program", "neither"):
            cmp(f"{d} {n} {k}", f[k], t[k])
        cmp(f"{d} {n} exp_indep", f["expected_if_independent"], t["only_model_expected_if_independent"])
        cmp(f"{d} {n} exp_indep_se", f["expected_if_independent_se"], t["only_model_if_independent_standard_error"])
        cmp(f"{d} {n} exp_guess", f["expected_if_guessing"], t["only_model_expected_by_chance"])
        w, t = r["wrong_moves"][n], wm[n][str(d)]
        cmp(f"{d} {n} wm problems", w and r["wrong_problems"], t["problems"])
        cmp(f"{d} {n} wm tries", r["wrong_tries"], t["wrong_tries"])
        cmp(f"{d} {n} wm left_out", r["left_out"], t["not_available_left_out"])
        cmp(f"{d} {n} match", w["match"], t["match_rate"])
        cmp(f"{d} {n} match_se", w["match_se"], t["match_rate_standard_error"])
        cmp(f"{d} {n} uniform", w["uniform"], t["uniform"])
        cmp(f"{d} {n} shuffle", w["shuffle"], t["shuffle"])
        cmp(f"{d} {n} excess", w["excess"], t["excess"])
        cmp(f"{d} {n} excess_se", w["excess_se"], t["excess_standard_error"])
        for c, v in w["over"].items():
            cmp(f"{d} {n} over_{c}", v["mean"], t["excess_over_control"][c]["mean"])
            cmp(f"{d} {n} over_{c}_se", v["se"], t["excess_over_control"][c]["standard_error"])

print("mismatches against saved fields:", out["mismatch_counts"])
for k, v in out["mismatch_examples"].items():
    if v:
        print(" ", k, v)
print("figures compared with the stage's files:", compared, "differences:", len(diffs))
for x in diffs:
    print("  DIFF", x)
