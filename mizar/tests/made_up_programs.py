"""Made-up libraries and problems for the tests of the simple programs.

`hand_library` is small enough to work every figure by hand. `rule_problems` makes many problems in which the
held-back option follows a planted rule ("longest": its statement is the longest; "shares": it shares three of
the theorem's symbols, the others at most one), or no rule at all ("shuffled": the held-back option is drawn at
random), over enough made-up articles for cross-validation by article.
"""
import random

from mizar_ladder.programs.common import Counts


def problem(problem_id, theorem, options, held_back, given=()):
    return {"id": problem_id, "theorem": theorem, "article": theorem.split("_", 1)[1], "held_back": held_back,
            "given": [{"name": g, "statement": "?"} for g in given],
            "options": [{"name": o, "statement": "?"} for o in options]}


OPTIONS = [f"t{n}_aa" for n in range(1, 31)]


def hand_library():
    """30 options t1_aa .. t30_aa, then three theorems of article bb citing some of them, and one of article cc
    (left out). Statements: t2_aa has r1_x; t4_aa has k1_y; t6_aa and t8_aa have both; the rest have k9_z only.
    The theorem t1_bb has r1_x and k1_y. Citations: t1_bb cites t3_aa and t5_aa; t2_bb cites t3_aa and t7_aa;
    t3_bb cites t5_aa; t1_cc (left out) cites t7_aa twice over."""
    special = {"t2_aa": "r1_x(A, A)", "t4_aa": "k1_y(A)=A", "t6_aa": "r1_x(A, k1_y(A))", "t8_aa": "r1_x(k1_y(B), B)"}
    facts = [(o, special.get(o, "k9_z(A)=A")) for o in OPTIONS]
    facts += [("t1_bb", "r1_x(A, k1_y(A)) & k9_z(A)=A"), ("t2_bb", "k9_z(A)=A"), ("t3_bb", "k9_z(B)=B"),
              ("t1_cc", "k9_z(A)=A")]
    references = {"t1_bb": ["t3_aa", "t5_aa"], "t2_bb": ["t3_aa", "t7_aa"], "t3_bb": ["t5_aa"],
                  "t1_cc": ["t7_aa"]}
    return Counts(facts, references, left_out={"t1_cc"})


def _statement(rng, symbols, conjuncts):
    """Each of `symbols` in turn (so all of them are there when there are enough conjuncts), shuffled."""
    used = [symbols[n % len(symbols)] for n in range(conjuncts)]
    rng.shuffle(used)
    return " & ".join(f"{symbol}(A{n})" for n, symbol in enumerate(used))


def rule_problems(rule, count, seed, prefix="train"):
    """(problems, counts) with `count` problems following `rule`, over 8 made-up articles."""
    rng = random.Random(seed)
    symbols = [f"k{n}_sym" for n in range(40)]
    facts, problems = [], []
    for i in range(count):
        theorem_symbols = rng.sample(symbols, 5)
        others = [s for s in symbols if s not in theorem_symbols]
        held_back = rng.randrange(1, 31)
        lengths = [rng.randint(2, 6) for _ in range(30)]
        if rule == "longest":
            lengths[held_back - 1] = max(lengths) + 1
        options = []
        for n in range(1, 31):
            name = f"t{i * 30 + n}_opt{i % 3}"
            if rule == "shares" and n == held_back:
                chosen = rng.sample(theorem_symbols, 3) + [rng.choice(others)]
            else:
                # Four symbols, as the held-back option has: at most one of them the theorem's.
                chosen = rng.sample(others, 3) + [rng.choice(theorem_symbols if rng.random() < 0.5 else others)]
                chosen = chosen if len(set(chosen)) == 4 else rng.sample(others, 4)
            if rule == "longest":
                chosen = others
            facts.append((name, _statement(rng, chosen, lengths[n - 1] if rule == "longest" else 4)))
            options.append(name)
        theorem = f"t{i}_prob{i % 8}"
        facts.append((theorem, _statement(rng, theorem_symbols, 5)))
        problems.append(problem(f"{prefix}-{i:04d}", theorem, options, held_back))
    return problems, Counts(facts, {}, left_out=set())
