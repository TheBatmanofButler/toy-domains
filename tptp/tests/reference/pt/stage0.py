"""Stage 0 (no prover): distinct unit-equational theories in TPTP v9.3.1 and eligible ones (>= 4 axioms).

Sources: every file under Axioms/ (all formulas, includes resolved, must be positive unit equations: cnf `l = r` or fof
`![..]: l = r`), and every Problems/ file whose header SPC ends in _UEQ (all non-negated-conjecture formulas, includes
resolved, must be positive unit equations).  Theory = set of axioms deduplicated by canon_eq_str (variable renaming,
side swap); theories deduplicated by the archive's canonical form (canon.canonical_form) of (axioms, X=X, []) i.e. up to
arity-preserving symbol bijection + variable renaming + side swap + reordering.

usage: python3 -I stage0.py <TPTP root> <spc_lines.txt> <out.json>
"""
import sys, os, re, json, hashlib, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fol import tptp as TP
from fol.terms import *
from fol import canon as CN

TYPED = re.compile(r"^\s*(thf|tff|tcf|tpi)\s*\(", re.M)
QUANT = re.compile(r"^!\s*\[[^\]]*\]\s*:\s*")


def read_formulas_fixed(path, root, seen=None):
    """archive tptp.read_formulas with one fix (amendment A1): the annotation split counts [] as well as (), so
    fof quantifier lists `! [X,Y]` are not cut at their comma."""
    if seen is None:
        seen = set()
    txt = TP._COMMENT.sub("", open(path, errors="ignore").read())
    out, pos = [], 0
    pat = re.compile(r"\b(cnf|fof|include)\s*\(")
    while True:
        m = pat.search(txt, pos)
        if not m:
            break
        j = m.end() - 1
        k = TP._balanced_end(txt, j)
        if k < 0:
            break
        inner = txt[j + 1:k - 1]
        pos = k
        if m.group(1) == "include":
            fn = inner.split(",")[0].strip().strip("'")
            p2 = os.path.join(root, fn)
            if os.path.exists(p2) and p2 not in seen:
                seen.add(p2)
                out.extend(read_formulas_fixed(p2, root, seen))
            continue
        parts = inner.split(",", 2)
        if len(parts) < 3:
            continue
        name, role, body = parts[0].strip(), parts[1].strip(), parts[2].strip()
        depth = 0
        for i, ch in enumerate(body):
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                body = body[:i]
                break
        out.append((m.group(1), name, role, body.strip()))
    return out


READER = TP.read_formulas


def strip_fof(body):
    b = TP._strip_parens(body)
    while True:
        m = QUANT.match(b)
        if not m:
            break
        b = TP._strip_parens(b[m.end():])
    return b


def sym_arity_ok(eqs):
    ar = {}
    def walk(t):
        if is_var(t):
            return True
        a = len(t) - 1
        if ar.setdefault(t[0], a) != a:
            return False
        return all(walk(x) for x in t[1:])
    return all(walk(e[0]) and walk(e[1]) for e in eqs)


def read_theory(path, root, is_problem):
    """-> (ok, reason, axioms[list of eq], conj_ok bool)"""
    try:
        raw = open(path, errors="ignore").read()
    except OSError:
        return False, "unreadable", None
    if TYPED.search(TP._COMMENT.sub("", raw)):
        return False, "typed_language", None
    try:
        fs = READER(path, root)
    except RecursionError:
        return False, "parse", None
    if not fs:
        return False, "no_formulas", None
    axioms = []
    for kind, name, role, body in fs:
        if is_problem and role == "negated_conjecture":
            continue
        if role in ("conjecture", "negated_conjecture"):
            return False, "conjecture_in_axiom_file", None
        b = body if kind == "cnf" else strip_fof(body)
        if kind == "fof" and re.search(r"[?&|~]|=>|<=", b.replace("!=", "")):
            return False, "fof_not_unit_eq", None
        p = TP.parse_unit_eq_body(b)
        if p is None or p[0] != "eq":
            return False, "not_unit_eq", None
        axioms.append(p[1])
    if not axioms:
        return False, "no_axioms", None
    if not sym_arity_ok(axioms):
        return False, "mixed_arity", None
    seen, ax2 = set(), []
    for a in axioms:
        if a[0] == a[1]:
            continue
        k = canon_eq_str(a)
        if k not in seen:
            seen.add(k)
            ax2.append(a)
    return True, "", ax2


def theory_key(axioms):
    cf, exact = CN.canonical_form(axioms, ("X", "X"), [])
    return hashlib.sha256(cf.encode()).hexdigest()[:20], exact, cf


def main(root, spc_file, out):
    files = []
    for dp, dn, fn in os.walk(os.path.join(root, "Axioms")):
        for f in sorted(fn):
            if f.endswith(".ax"):
                files.append(("ax", os.path.join(dp, f)))
    ueq = []
    for line in open(spc_file):
        p, _, spc = line.partition(":% SPC")
        if spc.strip().split(":")[-1].strip().endswith("_UEQ"):
            ueq.append(os.path.join(root, p) if not p.startswith("/") else p)
    files += [("ueq", p) for p in sorted(ueq)]
    files.sort(key=lambda x: (x[0], x[1]))
    reasons = collections.Counter()
    theories = {}
    n_read = collections.Counter()
    nonexact = 0
    for kind, p in files:
        n_read[kind] += 1
        ok, why, ax = read_theory(p, root, kind == "ueq")
        if not ok:
            reasons[kind + ":" + why] += 1
            continue
        reasons[kind + ":ok"] += 1
        key, exact, cf = theory_key(ax)
        rel = os.path.relpath(p, root)
        t = theories.get(key)
        if t is None:
            if not exact:
                nonexact += 1
            ground = sum(1 for a in ax if not eq_vars(a))
            t = theories[key] = dict(key=key, exact=exact, n_axioms=len(ax), n_ground=ground,
                                     axioms=[eq_str(a) for a in ax], canonical=cf, sources=[], domains=[])
        t["sources"].append(rel)
        d = os.path.basename(p)[:3]
        if d not in t["domains"]:
            t["domains"].append(d)
    for t in theories.values():
        t["primary_domain"] = t["domains"][0] if t["domains"] else "?"
        t["from_axfile"] = any(s.startswith("Axioms/") for s in t["sources"])
        t["ueq_sources"] = [s for s in t["sources"] if s.startswith("Problems/")]
        t["eligible"] = t["n_axioms"] >= 4
    elig = [t for t in theories.values() if t["eligible"]]
    by_dom = collections.defaultdict(lambda: [0, 0])
    for t in theories.values():
        by_dom[t["primary_domain"]][0] += 1
        if t["eligible"]:
            by_dom[t["primary_domain"]][1] += 1
    summ = dict(files_read=dict(n_read), parse_outcomes=dict(reasons), distinct_theories=len(theories),
                eligible=len(elig), nonexact_canonical=nonexact,
                eligible_without_ground_axioms=sum(1 for t in elig if t["n_ground"] == 0),
                eligible_from_axiom_files=sum(1 for t in elig if t["from_axfile"]),
                eligible_with_ueq_source=sum(1 for t in elig if t["ueq_sources"]),
                axiom_count_hist_eligible=dict(collections.Counter(min(t["n_axioms"], 40) for t in elig)),
                by_primary_domain={d: dict(distinct=v[0], eligible=v[1]) for d, v in sorted(by_dom.items())})
    json.dump(dict(summary=summ, theories=sorted(theories.values(), key=lambda t: t["key"])), open(out, "w"), indent=0)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 4 and sys.argv[4] == "fixed":
        READER = read_formulas_fixed
    main(*sys.argv[1:4])
