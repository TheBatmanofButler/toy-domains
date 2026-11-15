"""Hand-back tables (i) to (vi), built from the stage's files in RESULTS. Marks are mechanical.
Usage: python3 -I checks/tables.py RESULTS RECOMPUTE_JSON"""
import json
import sys

R = sys.argv[1]
mine = json.load(open(sys.argv[2]))
sbd = json.load(open(f"{R}/scores_by_depth.json"))
pbp = json.load(open(f"{R}/problem_by_problem.json"))
wm = json.load(open(f"{R}/wrong_moves.json"))
D = sorted(sbd, key=int)
P = sorted(sbd[D[0]]["programs"])
f3 = lambda x: "n/a" if x is None else f"{x:.3f}"


def mark(mean, se):
    if se is None:
        return ""
    if mean > 2 * se:
        return " ABOVE"
    if mean < -2 * se:
        return " BELOW"
    return ""


print("(i) per depth")
print("| Depth | " + " | ".join(P) + " | Best | Room | Model (SE) | Forced | Unreadable | Not available | Mean thinking tokens |")
for d in D:
    s = sbd[d]
    print(f"| {d} | " + " | ".join(f3(s["programs"][p]) for p in P)
          + f" | {'+'.join(s['best_programs'])} | {f3(s['room'])} | {f3(s['model'])} ({f3(s['model_standard_error'])})"
          + f" | {f3(s['forced_share'])} | {f3(s['unreadable_share'])} | {f3(s['not_available_share'])} | {s['thinking_tokens_mean']:.3f} |")

print("\n(ii) model minus program, mean (SE), mark where |mean| > 2 SE")
marks = {}
print("| Depth | best (" + "/".join("") + ") | " + " | ".join(P) + " |")
for d in D:
    s = sbd[d]
    cells = []
    for p in P:
        g = s["model_minus_program"][p]
        m = mark(g["mean"], g["standard_error"])
        marks[(p, d)] = m.strip()
        cells.append(f"{g['mean']:+.3f} ({f3(g['standard_error'])}){m}")
    best = s["best_programs"]
    bg = [s["model_minus_program"][b] for b in best]
    bcell = "; ".join(f"{b} {g['mean']:+.3f} ({f3(g['standard_error'])}){mark(g['mean'], g['standard_error'])}"
                      for b, g in zip(best, bg))
    for b, g in zip(best, bg):
        marks[("BEST", d)] = mark(g["mean"], g["standard_error"]).strip()
    print(f"| {d} | {bcell} | " + " | ".join(cells) + " |")

print("\n(iii) problem by problem: both / only model / only program / neither; expected only-model if independent (SE); if guessing")
for p in P:
    for d in D:
        r = pbp[p][d]
        print(f"| {p} | {d} | {r['both']} | {r['only_model']} | {r['only_program']} | {r['neither']} | "
              f"{f3(r['only_model_expected_if_independent'])} ({f3(r['only_model_if_independent_standard_error'])}) | "
              f"{f3(r['only_model_expected_by_chance'])} |")

print("\n(iv) same wrong moves; rule met = excess > 2 SE AND excess over each control > 2 SE")
wmarks = {}
for p in P:
    for d in D:
        r = wm[p][d]
        a = r["excess_standard_error"] is not None and r["excess"] > 2 * r["excess_standard_error"]
        overs = r["excess_over_control"]
        b = {c: v["mean"] > 2 * v["standard_error"] for c, v in overs.items()}
        met = a and all(b.values())
        wmarks[(p, d)] = met
        oc = "; ".join(f"over {c} {v['mean']:+.3f} ({f3(v['standard_error'])}){' >2SE' if b[c] else ''}"
                       for c, v in overs.items())
        rec = wm["recall"][d]
        st = wm["surface_strict"][d]
        print(f"| {p} | {d} | {r['problems']} | {r['wrong_tries']} | {r['not_available_left_out']} | "
              f"{f3(r['match_rate'])} ({f3(r['match_rate_standard_error'])}) | {f3(r['uniform'])} | {f3(r['shuffle'])} | "
              f"{r['excess']:+.3f} ({f3(r['excess_standard_error'])}){' >2SE' if a else ''} | {oc} | "
              f"{'MET' if met else ''} |")
print("controls' own figures per depth: recall excess (SE); strict excess (SE)")
for d in D:
    rc, st = wm["recall"][d], wm["surface_strict"][d]
    print(d, f"{rc['excess']:+.3f} ({f3(rc['excess_standard_error'])})", f"{st['excess']:+.3f} ({f3(st['excess_standard_error'])})")

print("\n(v) forced vs unforced at depth 2")
s, m = sbd["2"], mine["depths"]["2"]
print(f"forced n={s['forced_answers']} right share={f3(s['forced_share_right'])} (right count {m['forced_right_count']}); "
      f"unforced n={s['unforced_answers']} right share={f3(s['unforced_share_right'])} (right count {m['unforced_right_count']})")

print("\n(vi) marks repeated at a neighbouring depth")
for key in sorted({k[0] for k in marks}):
    for i in range(len(D) - 1):
        a, b = marks[(key, D[i])], marks[(key, D[i + 1])]
        if a and a == b:
            print(f"(ii) {key}: {a} at depths {D[i]} and {D[i+1]}")
for p in P:
    for i in range(len(D) - 1):
        if wmarks[(p, D[i])] and wmarks[(p, D[i + 1])]:
            print(f"(iv) {p}: MET at depths {D[i]} and {D[i+1]}")
print("(iv) all MET cells:", [k for k, v in wmarks.items() if v])
