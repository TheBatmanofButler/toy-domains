"""Pilot H pod job: shallow (single-lemma) labeling on the prefix theories (pre-registration H3-H6, H12).

usage: python3 label_h.py det <theories.json> <det_goals.json> <outdir>         (H12, 3 concurrent repetitions)
       python3 label_h.py run <theories.json> <outdir> <workers> <deadline_epoch> (H5/H6)
Every engine call's raw stdout is stored (raw_*.jsonl.gz); compact records in goals.jsonl.gz."""
import sys, os, json, random, hashlib, time, gzip, subprocess, traceback
from multiprocessing import Pool, Manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("EPROVER", "/workspace/fol/engine/eprover.sh")
from fol.terms import parse_eq, canon_eq_str, eq_str
from fol import engine as EN, oracle

B_L = 160
EXTRA = (20, 40, 80, 320)
CPU_CAP = 60
GEN_CPU = 60
N = 30
MAX_LIVE = 15
STOP = 5
THEORY_CAP_S = 8000


def hseed(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:16], 16)


def draw(T, gi):
    """H3: goal-blind seeded draw of 30 bank facts; the goal enters only through the exclusion."""
    U = T["U"]
    if len(U) < N:
        return None
    gk = canon_eq_str(parse_eq(T["goals"][gi]))
    order = random.Random(hseed("shallow|cand|%s|%d" % (T["key"], gi))).sample(U, len(U))
    out = [v for k, v in order if k != gk][:N]
    return out if len(out) == N else None


class Caller:
    def __init__(self, axioms, cands, goal):
        self.ax = [EN.eq_clause("ax%d" % i, a) for i, a in enumerate(axioms)]
        self.cl = [EN.eq_clause("lem%d" % i, c, "lemma") for i, c in enumerate(cands)]
        self.goal = EN.skolemize_conjecture(goal)
        self.raw = {}
        self.ncpu = 0

    def call(self, ids, limit):
        text = "\n".join(self.ax + [self.cl[i] for i in sorted(ids)] + [self.goal]) + "\n"
        fn = "/dev/shm/h_%d.p" % os.getpid()
        open(fn, "w").write(text)
        r = subprocess.run(EN.engine_args(limit, CPU_CAP, "S1") + [fn], capture_output=True, text=True)
        os.unlink(fn)
        out = r.stdout + r.stderr
        ok, st = EN.parse_output(out, r.returncode)
        if st["cpu_cap"]:
            self.ncpu += 1
        key = "%d|%s" % (limit, ",".join(map(str, sorted(ids))) or "base")
        self.raw[key] = out
        return ok, dict(closed=int(ok), status=st["status"], processed=st["processed"], generated=st["generated"],
                        unprocessed=st["unprocessed"], tb=st["tb_inserts"])


def singletons(c, limit):
    base = c.call((), limit)[1]
    s = [c.call((i,), limit)[1] for i in range(N)]
    return base, s


# ------------------------------------------------------------------ determinism (H12)
def det_task(arg):
    T, gi, rep = arg
    ax = [parse_eq(a) for a in T["axioms"]]
    cands = draw(T, gi)
    c = Caller(ax, [parse_eq(x) for x in cands], parse_eq(T["goals"][gi]))
    res = {}
    for lim in (160, 320):
        b, s = singletons(c, lim)
        res[str(lim)] = [b] + s
    return dict(theory=T["key"], gi=gi, rep=rep, res=res, raw=c.raw)


def do_det(theories, detf, outdir):
    TH = {t["key"]: t for t in json.load(open(theories))}
    goals = json.load(open(detf))
    os.makedirs(outdir, exist_ok=True)
    tasks = [(TH[k], gi, rep) for rep in range(3) for k, gi in goals]
    t0 = time.time()
    with Pool(96) as p:
        res = p.map(det_task, tasks, chunksize=1)
    with gzip.open(os.path.join(outdir, "det_raw.jsonl.gz"), "wt") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    by = {}
    for r in res:
        by.setdefault((r["theory"], r["gi"]), {})[r["rep"]] = r["res"]
    mism_cs, mism_stats, ncalls = 0, 0, 0
    detail = []
    for g, reps in by.items():
        for lim in ("160", "320"):
            for j in range(N + 1):
                v = [reps[k][lim][j] for k in range(3)]
                ncalls += 1
                if len({(x["closed"], x["status"]) for x in v}) > 1:
                    mism_cs += 1; detail.append([g, lim, j, v])
                if len({json.dumps(x, sort_keys=True) for x in v}) > 1:
                    mism_stats += 1
    summ = dict(goals=len(by), call_sets=ncalls, reps=3, closed_status_mismatch=mism_cs, any_stat_mismatch=mism_stats,
                n_closed_160=sum(reps[0]["160"][j]["closed"] for reps in by.values() for j in range(N + 1)),
                n_closed_320=sum(reps[0]["320"][j]["closed"] for reps in by.values() for j in range(N + 1)),
                detail=detail[:20], wall_s=time.time() - t0)
    json.dump(summ, open(os.path.join(outdir, "determinism.json"), "w"), indent=1)
    print(json.dumps(summ))


# ------------------------------------------------------------------ main run (H5/H6)
TH, SH = {}, {}


def _init(theories, shared, lock, deadline):
    for t in json.load(open(theories)):
        TH[t["key"]] = t
    SH.update(d=shared, lock=lock, deadline=deadline)


def goal_task(arg):
    key, gi = arg
    d = SH["d"]
    st = d[key]
    if st["n_prob"] >= STOP:
        return dict(theory=key, gi=gi, status="skipped_theory_done"), None
    if st["s"] >= THEORY_CAP_S:
        return dict(theory=key, gi=gi, status="skipped_theory_cap"), None
    if time.time() > SH["deadline"]:
        return dict(theory=key, gi=gi, status="skipped_deadline"), None
    T = TH[key]
    t0 = time.time()
    rec = dict(theory=key, gi=gi, goal=T["goals"][gi])
    raw = None
    try:
        cands = draw(T, gi)
        if cands is None:
            rec["status"] = "draw_short"
        else:
            rec["cands"] = cands
            ax = [parse_eq(a) for a in T["axioms"]]
            goal = parse_eq(T["goals"][gi])
            c = Caller(ax, [parse_eq(x) for x in cands], goal)
            ok, b = c.call((), B_L)
            rec["base160"] = b
            if ok:
                rec["status"] = "base_closes_160"
            else:
                cr = T["cert"].get(str(gi))
                if cr is not None:
                    rec["cert"] = dict(proved=cr["proved"], cpu_s=cr.get("cpu_s"), source=cr["from_"])
                else:
                    r = oracle.prove(ax, goal, cpu=GEN_CPU)
                    rec["cert"] = dict(proved=bool(r["proved"]), cpu_s=round(r["cpu_s"], 2), source="pilotH")
                if not rec["cert"]["proved"]:
                    rec["status"] = "not_theorem"
                else:
                    s = [c.call((i,), B_L)[1] for i in range(N)]
                    rec["s160"] = s
                    live = [i for i in range(N) if s[i]["closed"]]
                    rec["live160"] = live
                    if not live:
                        rec["status"] = "zero_live"
                    elif len(live) > MAX_LIVE:
                        rec["status"] = "gt15_live"
                    else:
                        rec["status"] = "problem"
                        for lim in EXTRA:
                            if lim == 320:
                                rec["base320"] = c.call((), 320)[1]
                            rec["s%d" % lim] = [c.call((i,), lim)[1] for i in range(N)]
            rec["cpu_cap_calls"] = c.ncpu
            rec["n_calls"] = len(c.raw)
            raw = dict(theory=key, gi=gi, raw=c.raw)
    except Exception:
        rec["status"] = "error"
        rec["err"] = traceback.format_exc()[-2000:]
    rec["s"] = time.time() - t0
    with SH["lock"]:
        st = d[key]
        st["s"] += rec["s"]
        if rec.get("status") == "problem":
            st["n_prob"] += 1
        d[key] = st
    return rec, raw


def do_run(theories, outdir, workers, deadline):
    T = json.load(open(theories))
    os.makedirs(outdir, exist_ok=True)
    mgr = Manager()
    shared = mgr.dict({t["key"]: dict(n_prob=0, s=0.0) for t in T})
    lock = mgr.Lock()
    act = [t for t in T if len(t["U"]) >= N]            # bank < 30: theory does not yield, no goal is run
    maxg = max(len(t["goals"]) for t in act)
    tasks = [(t["key"], gi) for gi in range(maxg) for t in act if gi < len(t["goals"])]
    fo = gzip.open(os.path.join(outdir, "goals.jsonl.gz"), "wt")
    fr = gzip.open(os.path.join(outdir, "raw_calls.jsonl.gz"), "wt")
    n = 0
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(theories, shared, lock, deadline)) as p:
        for rec, raw in p.imap(goal_task, tasks, chunksize=1):
            fo.write(json.dumps(rec) + "\n")
            if raw is not None:
                fr.write(json.dumps(raw) + "\n")
            n += 1
            if n % 300 == 0:
                fo.flush(); fr.flush()
                done = sum(1 for v in shared.values() if v["n_prob"] >= STOP)
                print("%d/%d tasks %.0fs theories_at_5 %d" % (n, len(tasks), time.time() - t0, done), flush=True)
    fo.close(); fr.close()
    json.dump(dict(shared), open(os.path.join(outdir, "theory_state.json"), "w"), indent=1)
    print("DONE", n, time.time() - t0, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "det":
        do_det(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        do_run(sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5]))
