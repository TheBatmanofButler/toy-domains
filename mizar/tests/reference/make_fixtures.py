"""Makes the saved test material under tests/fixtures/. Run once by hand; the tests only read what it wrote.

    python3 -I tests/reference/make_fixtures.py --library FOLDER

1. `made_up_library/`: a library of four small articles in the real files' formats, worked out by hand in
   tests/test_problems.py. It needs nothing real.
2. `real_pieces/`: small pieces of each real file, cut so that they still form a library the code can read: the
   problem files of t1_xboole_1 to t5_xboole_1 and t83_xboole_1, every fact named in them (their lines of `statements` and `seq`, in
   the real order), their lines of `00mizrefs`, every line of `00constrnames` for a symbol in those statements,
   and the first 60 lines of `xboole_1.miz`.
3. `shown_statements.json`: ten real statements with the text `show` must give for each. The expected texts are
   written below by hand, from the statements and the name table, not by running `show`.
4. `fixed_problem.json` and `question_for_fixed_problem.txt`: one real problem (t70_zfmisc_1, seed 20261112)
   and the question built for it, saved after it was read by eye.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "fixtures"
sys.path.insert(0, str(HERE.parent.parent))

# ---- 1. The made-up library -------------------------------------------------------------------------------------
# basic_0 (an article outside the articles problems come from): two definitions, one fact of another kind, t1 to t34 with l1
# after t10 and l2 after t20. t20 says what t5 says with another variable name. xboole_0 and xboole_1 are the test
# articles, from which test and training problems are both built; later_0 is another article stated after them.


def basic_statement(n):
    if n == 20:
        return "(! [B] : r1_basic_0(B, k1_basic_0(B, c5_basic_0)))"
    return f"(! [A] : r1_basic_0(A, k1_basic_0(A, c{n}_basic_0)))"


def made_up_facts():
    """[(name, statement, cited facts or None if it has no problem file)] in the library's order."""
    facts = [("d1_basic_0", "(! [A] : (v1_basic_0(A) <=> r1_basic_0(A, k1_basic_0(A, A))))", None),
             ("d2_basic_0", "(! [A, B] : (r1_basic_0(A, B) <=> ~ (r1_basic_0(B, A))))", None),
             ("reflexivity_r1_basic_0", "(! [A] : r1_basic_0(A, A))", None)]
    for n in range(1, 35):
        cited = {1: ["d1_basic_0"], 2: ["d1_basic_0", "d2_basic_0"]}.get(n, [f"t{n - 1}_basic_0", "d1_basic_0"])
        facts.append((f"t{n}_basic_0", basic_statement(n), cited))
        if n == 10:
            facts.append(("l1_basic_0", "(! [A] : (v1_basic_0(A) => r1_basic_0(A, A)))", ["t3_basic_0", "d2_basic_0"]))
        if n == 20:
            facts.append(("l2_basic_0", "(! [A, B] : (r1_basic_0(A, B) | r1_basic_0(B, A)))", ["t1_basic_0"]))
    facts += [
        ("d1_xboole_0", "(! [A] : (A=k1_xboole_0 <=> ~ (? [B] : r2_hidden(B, A))))", None),
        ("t1_xboole_0", "(! [A] : k2_xboole_0(A, k1_xboole_0)=A)", ["d1_xboole_0"]),
        ("t2_xboole_0", "(! [A] : k3_xboole_0(A, k1_xboole_0)=k1_xboole_0)", ["t1_xboole_0", "d1_xboole_0"]),
        ("t3_xboole_0", "(! [A, B] : r1_basic_0(k3_xboole_0(A, B), k2_xboole_0(A, B)))",
         ["t10_basic_0", "d1_xboole_0", "reflexivity_r1_basic_0"]),
        ("t4_xboole_0", "(! [A] : (r1_xboole_0(A, k1_xboole_0) & k1_xboole_0=o_0_0_xboole_0))",
         ["t5_basic_0", "t20_basic_0"]),
        # Three more theorems of the two articles that qualify, so that the training set (their other qualifying
        # theorems) holds problems of both articles.
        ("t5_xboole_0", "(! [A] : r1_basic_0(A, c41_xboole_0))", ["t11_basic_0", "d1_xboole_0"]),
        ("t1_xboole_1", "(! [A, B] : k2_xboole_0(A, B)=k2_xboole_0(B, A))", ["t3_xboole_0", "t4_xboole_0", "d1_xboole_0"]),
        ("t2_xboole_1", "(! [A] : r1_basic_0(k1_xboole_0, A))", ["t1_xboole_1", "t34_basic_0", "d2_basic_0"]),
        ("t3_xboole_1", "(! [A] : (v1_basic_0(A) => v1_basic_0(k2_xboole_0(A, A))))", ["t1_basic_0"]),
        ("t4_xboole_1", "(! [A] : r1_basic_0(c42_xboole_1, A))", ["t12_basic_0", "d2_basic_0"]),
        ("t5_xboole_1", "(! [A, B] : r1_basic_0(A, c43_xboole_1))", ["t13_basic_0", "d2_basic_0"]),
        ("t1_later_0", "(! [A] : r1_basic_0(A, k2_xboole_0(A, A)))", ["t5_basic_0", "d1_xboole_0"]),
        ("t2_later_0", "(! [A] : k3_xboole_0(A, A)=A)", ["t1_xboole_1"]),
        ("t3_later_0", "(! [A, B] : k3_xboole_0(A, B)=k3_xboole_0(B, A))", ["t3_xboole_0", "t1_xboole_1"]),
    ]
    return facts


MADE_UP_NAMES = ["k1_basic_0 +", "r1_basic_0 <=", "v1_basic_0 small", "k1_xboole_0 {}", "k2_xboole_0 \\/",
                 "k2_xboole_0 union", "k3_xboole_0 /\\", "r1_xboole_0 misses", "r2_hidden in"]


def write_made_up_library(folder):
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "problems_small_consist").mkdir(parents=True)
    facts = made_up_facts()
    (folder / "seq").write_text("".join(f"{name}\n" for name, _, _ in facts))
    # The real statements file is not in the library's order; this one is sorted by name to keep that so.
    (folder / "statements").write_text("".join(f"fof({name}, axiom, {statement}).\n"
                                               for name, statement, _ in sorted(facts)))
    (folder / "00constrnames").write_text("".join(line + "\n" for line in MADE_UP_NAMES))
    (folder / "xboole_1.miz").write_text(":: a made-up article\n")
    statement = {name: s for name, s, _ in facts}
    references = []
    for name, own, cited in facts:
        if cited is None:
            continue
        # A cited fact written twice, as the real file has it: it is one cited fact.
        references.append(f"{name}:{','.join(cited + cited[:1])}\n")
        art = name.split("_", 1)[1]
        (folder / "problems_small_consist" / art).mkdir(exist_ok=True)
        background = sorted(set(cited) | {"reflexivity_r1_basic_0"})
        lines = [f"% Mizar problem: {name},{art},1,1 \n", f"fof({name}, conjecture, {own}).\n"]
        lines += [f"fof({fact}, axiom, {statement[fact]}).\n" for fact in background]
        (folder / "problems_small_consist" / art / f"{art}__{name}").write_text("".join(lines))
    (folder / "00mizrefs").write_text("".join(references))


# ---- 2. Pieces of the real files --------------------------------------------------------------------------------
PIECE_THEOREMS = ["t1_xboole_1", "t2_xboole_1", "t3_xboole_1", "t4_xboole_1", "t5_xboole_1", "t83_xboole_1"]


def write_real_pieces(library, folder):
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "problems_small_consist" / "xboole_1").mkdir(parents=True)
    wanted = set(PIECE_THEOREMS)
    for theorem in PIECE_THEOREMS:
        source = library / "problems_small_consist" / "xboole_1" / f"xboole_1__{theorem}"
        text = source.read_text()
        (folder / "problems_small_consist" / "xboole_1" / source.name).write_text(text)
        wanted |= set(re.findall(r"^fof\(([^,]+),", text, re.MULTILINE))
    lines = [line for line in open(library / "statements") if re.match(r"fof\(([^,]+),", line).group(1) in wanted]
    (folder / "statements").write_text("".join(lines))
    (folder / "seq").write_text("".join(line for line in open(library / "seq") if line.strip() in wanted))
    (folder / "00mizrefs").write_text("".join(line for line in open(library / "00mizrefs")
                                              if line.split(":", 1)[0] in PIECE_THEOREMS))
    used = set(re.findall(r"\b[a-z][A-Za-z0-9_]*", "".join(lines)))
    (folder / "00constrnames").write_text("".join(line for line in open(library / "00constrnames")
                                                  if line.split()[0] in used))
    (folder / "xboole_1.miz").write_text("".join(open(library / "xboole_1.miz").readlines()[:60]))


# ---- 3. Ten real statements and the text `show` must give, written by hand -----------------------------------
SHOWN = {
    "t3_xboole_1": "(! [A] :  (A c= {} => A={}) )",
    "t4_xboole_1": "(! [A] :  (! [B] :  (! [C] : ((A \\/ B) \\/ C)=(A \\/ (B \\/ C))) ) )",
    "d3_tarski": "(! [A] :  (! [B] :  (A c= B <=>  (! [C] :  (in(C, A) => in(C, B)) ) ) ) )",
    "t1_funct_1": "(! [A] :  (! [B] :  (! [C] :  ( (Relation-like(C) & Function-like(C))  =>  "
                  "(in([..](A, B), C) <=>  (in(A, proj1(C)) & B=(C . A)) ) ) ) ) )",
    "d2_xboole_0": "{}=o_0_0_xboole_0",
    "t65_xboole_1": "(! [A] : misses(A, {}))",
    "t79_xboole_1": "(! [A] :  (! [B] : misses((A \\ B), B)) )",
    "t127_zfmisc_1": "(! [A] :  (! [B] :  ~ (in(A, [:..:](A, B))) ) )",
    "t158_relat_1": "(! [A] :  (! [B] : proj1([:..:](A, B)) c= A) )",
    "d1_lattices": "(! [A] :  ( ( ~ (empty(A))  & \\/-SemiLattStr(A))  =>  (! [B] :  (Element(B, carrier(A)) =>  "
                   "(! [C] :  (Element(C, carrier(A)) => \"\\/\"(A, B, C)=.(carrier(A), L_join(A), B, C)) ) ) ) ) )",
}


def write_shown_statements(library, path):
    statements = {}
    for line in open(library / "statements"):
        name = re.match(r"fof\(([^,]+),", line).group(1)
        if name in SHOWN:
            statements[name] = re.fullmatch(r"fof\([^,]+, axiom,(.*)\)\.\s*", line).group(1).strip()
    path.write_text(json.dumps([{"name": n, "statement": statements[n], "shown": SHOWN[n]} for n in SHOWN], indent=1))


# ---- 4. One real problem and its question ----------------------------------------------------------------------
def write_fixed_problem(library, checksums):
    from mizar_ladder.library import Library
    from mizar_ladder.problems import Builder
    from mizar_ladder.question import build_question
    builder = Builder(Library(library, checksums), 20261112)
    problem = builder.problem(builder.classify("t70_zfmisc_1"), "test-fixed")
    (FIXTURES / "fixed_problem.json").write_text(json.dumps(problem, indent=1))
    (FIXTURES / "question_for_fixed_problem.txt").write_text(build_question(problem))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, help="the folder holding the real library's files")
    library = Path(parser.parse_args().library)
    checksums = {name: digest for digest, name in (line.split()[:2] for line in open(library / "CHECKSUMS"))
                 if not name.endswith(".tar.gz")}
    write_made_up_library(FIXTURES / "made_up_library")
    write_real_pieces(library, FIXTURES / "real_pieces")
    write_shown_statements(library, FIXTURES / "shown_statements.json")
    write_fixed_problem(library, checksums)


if __name__ == "__main__":
    main()
