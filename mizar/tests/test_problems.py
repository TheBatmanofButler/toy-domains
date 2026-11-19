"""Tests of problems.py on the made-up library of four small articles (tests/reference/make_fixtures.py), worked
out by hand.

The library, in its order. Only xboole_0 and xboole_1 are the articles problems come from here; basic_0 and later_0 are only the
rest of the library, from which nothing is built. basic_0: d1, d2, a fact of another kind, t1 to t34 with l1 after t10 and l2
after t20: 36 theorems and lemmas. t20 says what t5 says with another variable, so where both would be neighbours
only t5, the first, is one. t1 cites d1 only and t2 cites d1 and d2 (not usable); every other t{n} cites t{n-1}
and d1, so its held-back fact is t{n-1}, whose neighbours are the theorems and lemmas before t{n} less t{n-1}
and, from t21 on, less t20 (t5's twin): n - 1 of them from t22 on (t1..t{n-1}, l1, l2, less t{n-1} and t20); t21
(held t20, whose twin t5 is left out) has 20. So t30 to t34 qualify (29 to 33) and t29 (28) does not. l1 cites t3
and d2: 9 neighbours. l2 cites t1 only.
xboole_0 (test): t1 cites d1_xboole_0 only (not usable); t2 cites t1_xboole_0 and d1_xboole_0: held t1_xboole_0,
no neighbour; t3 cites t10_basic_0, d1_xboole_0 and the other fact: held t10_basic_0, 34 neighbours (all 36 of
basic_0 less t10 and t20); t4 cites t5_basic_0 and t20_basic_0, which read the same, so neither can be held back
and t4 is not usable; t5 cites t11_basic_0 and d1_xboole_0: held t11_basic_0, 34 neighbours.
xboole_1 (test): t1 cites t3_xboole_0, t4_xboole_0, d1_xboole_0: held either, 3 neighbours (t1, t2 and t5 of xboole_0);
t2 cites t1_xboole_1, t34_basic_0, d2_basic_0: held t34_basic_0 with seed 7 (34 neighbours: qualifies) but
t1_xboole_1 with seed 1 (no neighbour: too few); t3 cites t1_basic_0 only; t4 cites t12_basic_0 and d2_basic_0,
t5 t13_basic_0 and d2_basic_0: held t12 and t13, 34 neighbours each.
later_0: t1 cites t5_basic_0 and d1_xboole_0: 34 neighbours (36 less t5 and its twin t20); t2 cites
one fact; t3 cites t3_xboole_0 and t1_xboole_1.
So with seed 7 five theorems qualify (t3_xboole_0, t5_xboole_0, t2_xboole_1, t4_xboole_1, t5_xboole_1): with a
test count of 2, two are drawn as test problems and the other three are the training problems.
"""
import random

import pytest

from mizar_ladder import problems
from mizar_ladder.problems import BuildError, Builder, build, check_bins, check_problem, check_sets
from mizar_ladder.statements import show

BASIC = ([f"t{n}_basic_0" for n in range(1, 11)] + ["l1_basic_0"] + [f"t{n}_basic_0" for n in range(11, 21)]
         + ["l2_basic_0"] + [f"t{n}_basic_0" for n in range(21, 35)])
ARTICLES = ("xboole_0", "xboole_1")
REAL_BINS = {"not usable": 615, "too few neighbours": 355, "qualifies": 1200}
QUALIFYING = ["t3_xboole_0", "t5_xboole_0", "t2_xboole_1", "t4_xboole_1", "t5_xboole_1"]
# theorem: (bin, held-back fact, number of neighbours), seed 7. With seed 1, t2_xboole_1 holds back t1_xboole_1,
# with no neighbour.
SEVEN = {"t1_xboole_0": ("not usable", None, None), "t2_xboole_0": ("too few neighbours", "t1_xboole_0", 0),
         "t3_xboole_0": ("qualifies", "t10_basic_0", 34), "t4_xboole_0": ("not usable", None, None),
         "t5_xboole_0": ("qualifies", "t11_basic_0", 34),
         "t1_xboole_1": ("too few neighbours", "t3_xboole_0", 3), "t2_xboole_1": ("qualifies", "t34_basic_0", 34),
         "t3_xboole_1": ("not usable", None, None), "t4_xboole_1": ("qualifies", "t12_basic_0", 34),
         "t5_xboole_1": ("qualifies", "t13_basic_0", 34)}


def built(library, seed=7, test_count=2):
    return build(library, seed, test_count, ARTICLES)


def test_the_bins_worked_by_hand(made_up):
    records, _, _ = built(made_up)
    assert [r["theorem"] for r in records] == list(SEVEN)
    found = {r["theorem"]: (r["bin"], r["held_back"], r["neighbour_count"]) for r in records}
    # t1_xboole_1's held-back fact is either of its two cited theorems; both have the same 3 neighbours.
    assert found.pop("t1_xboole_1")[::2] == ("too few neighbours", 3)
    assert found == {t: v for t, v in SEVEN.items() if t != "t1_xboole_1"}
    assert records[2]["cited"] == ["t10_basic_0", "d1_xboole_0", "reflexivity_r1_basic_0"]   # repeats dropped
    assert sum(r["test"] for r in records) == 2
    other, _, _ = built(made_up, seed=1, test_count=1)
    other = {r["theorem"]: (r["bin"], r["held_back"], r["neighbour_count"]) for r in other}
    assert other["t4_xboole_0"] == ("not usable", None, None)
    assert other["t2_xboole_1"] == ("too few neighbours", "t1_xboole_1", 0)


def test_neighbours_worked_by_hand(made_up):
    builder = Builder(made_up, 7)
    cited = made_up.cited
    assert builder.neighbours("t3_xboole_0", "t10_basic_0", cited("t3_xboole_0")) == [
        n for n in BASIC if n not in ("t10_basic_0", "t20_basic_0")]
    assert len(builder.neighbours("t30_basic_0", "t29_basic_0", cited("t30_basic_0"))) == 29
    assert len(builder.neighbours("t29_basic_0", "t28_basic_0", cited("t29_basic_0"))) == 28
    # For t20 itself: t1 to t19 and l1, less t19 (cited) and t5, which says what the theorem t20 says.
    assert len(builder.neighbours("t20_basic_0", "t19_basic_0", cited("t20_basic_0"))) == 18
    twenty = builder.neighbours("t21_basic_0", "t20_basic_0", cited("t21_basic_0"))
    assert twenty == [n for n in BASIC[:BASIC.index("t21_basic_0")] if n not in ("t5_basic_0", "t20_basic_0")]
    assert len(twenty) == 20
    later = builder.neighbours("t1_later_0", "t5_basic_0", cited("t1_later_0"))
    assert later == [n for n in BASIC if n not in ("t5_basic_0", "t20_basic_0")]
    assert builder.neighbours("t1_xboole_1", "t4_xboole_0", cited("t1_xboole_1")) == ["t1_xboole_0", "t2_xboole_0",
                                                                                         "t5_xboole_0"]


def test_the_training_set_worked_by_hand(made_up):
    # Every qualifying theorem of the articles that was not drawn, in the library's order, built as a test
    # problem is; nothing from basic_0 or later_0 (t30 to t34 and t1_later_0 would qualify).
    records, test, train = built(made_up)
    drawn = set(random.Random("7:test set").sample(QUALIFYING, 2))
    assert [p["theorem"] for p in train] == [t for t in QUALIFYING if t not in drawn]
    assert [p["id"] for p in train] == ["train-0001", "train-0002", "train-0003"]
    assert [r["theorem"] for r in records if r["bin"] == "qualifies" and not r["test"]] == [p["theorem"] for p in train]
    builder = Builder(made_up, 7)
    for n, p in enumerate(train, 1):
        assert p == builder.problem(builder.classify(p["theorem"]), f"train-{n:04d}")
        assert p["options"][p["held_back"] - 1]["name"] == SEVEN[p["theorem"]][1]
    # All five as test problems: no training problem is left.
    _, test, train = built(made_up, test_count=5)
    assert [p["theorem"] for p in test] == QUALIFYING and train == []


def test_the_test_problems_and_their_options(made_up):
    _, test, _ = built(made_up)
    drawn = set(random.Random("7:test set").sample(QUALIFYING, 2))
    assert [p["theorem"] for p in test] == [t for t in SEVEN if t in drawn]
    assert [p["id"] for p in test] == ["test-0001", "test-0002"]
    names = made_up.mizar_names()
    for problem in test:
        theorem = problem["theorem"]
        held_back = SEVEN[theorem][1]
        cited = made_up.cited(theorem)
        options = [o["name"] for o in problem["options"]]
        assert options[problem["held_back"] - 1] == held_back and len(set(options)) == 30
        assert set(options) - {held_back} <= set(Builder(made_up, 7).neighbours(theorem, held_back, cited))
        assert [g["name"] for g in problem["given"]] == [c for c in cited if c != held_back]
        assert problem["statement"] == show(made_up.statement(theorem), names)
        assert all(o["statement"] == show(made_up.statement(o["name"]), names) for o in problem["options"])
        assert problem["cited_count"] == len(cited) and problem["seed"] == 7
        assert problem["group"] == "sets, relations and functions" and problem["article"] == theorem.split("_", 1)[1]
        # The draw as documented: 29 neighbours, then the 30 in order, from one generator.
        rng = random.Random(f"7:{theorem}:options")
        expected = [held_back] + rng.sample(Builder(made_up, 7).neighbours(theorem, held_back, cited), 29)
        rng.shuffle(expected)
        assert options == expected


def test_a_shown_statement_by_hand(made_up):
    problem = Builder(made_up, 7).problem(Builder(made_up, 7).classify("t3_xboole_0"), "test-0001")
    assert problem["statement"] == "(! [A, B] : (A /\\ B) <= (A \\/ B))"
    assert problem["given"][0] == {"name": "d1_xboole_0", "statement": "(! [A] : (A={} <=> ~ (? [B] : in(B, A))))"}


def test_same_seed_same_files_and_another_seed_other_draws(made_up):
    assert built(made_up) == built(made_up)
    seven, eight = built(made_up)[1], built(made_up, seed=9)[1]
    by_theorem = {p["theorem"]: p for p in eight}
    shared = [p for p in seven if p["theorem"] in by_theorem]
    assert shared and all([o["name"] for o in p["options"]] != [o["name"] for o in by_theorem[p["theorem"]]["options"]]
                          for p in shared)


def test_files_are_written_and_read_back(made_up, tmp_path):
    records, test, _ = built(made_up)
    problems.write_jsonl(tmp_path / "test_problems.jsonl", test)
    assert problems.read_jsonl(tmp_path / "test_problems.jsonl") == test


# ---- every check that stops the build, made to fail once --------------------------------------------------------
def test_a_cited_fact_missing_from_its_problem_file_stops_the_build(made_up_copy):
    path = made_up_copy.path / "problems_small_consist" / "xboole_0" / "xboole_0__t3_xboole_0"
    path.write_text("".join(line for line in path.read_text().splitlines(keepends=True) if "t10_basic_0" not in line))
    with pytest.raises(BuildError, match="t3_xboole_0: cited fact t10_basic_0 is not in its problem file"):
        built(made_up_copy.load())


def test_a_cited_fact_stated_after_its_theorem_stops_the_build(made_up_copy):
    references = made_up_copy.path / "00mizrefs"
    references.write_text(references.read_text().replace("t2_xboole_0:t1_xboole_0", "t2_xboole_0:t1_later_0"))
    path = made_up_copy.path / "problems_small_consist" / "xboole_0" / "xboole_0__t2_xboole_0"
    path.write_text(path.read_text() + "fof(t1_later_0, axiom, (! [A] : r1_basic_0(A, k2_xboole_0(A, A)))).\n")
    with pytest.raises(BuildError, match="t2_xboole_0: cited fact t1_later_0 is stated after it"):
        built(made_up_copy.load())


@pytest.fixture
def one_problem(made_up):
    builder = Builder(made_up, 7)
    return builder.problem(builder.classify("t1_later_0"), "train-0001")


def broken(problem, n, name):
    options = [dict(o) for o in problem["options"]]
    options[n] = {"name": name, "statement": "?"}
    return dict(problem, options=options)


def test_each_check_on_one_problem_fails_once(made_up, one_problem):
    cited, held = made_up.cited("t1_later_0"), "t5_basic_0"
    check_problem(one_problem, made_up, cited, held)                  # as built, it passes
    wrong = 0 if one_problem["held_back"] != 1 else 1
    with pytest.raises(BuildError, match="option t3_later_0 is stated after the theorem"):
        check_problem(broken(one_problem, wrong, "t3_later_0"), made_up, cited, held)
    with pytest.raises(BuildError, match="wrong option d1_xboole_0 is cited by the author"):
        check_problem(broken(one_problem, wrong, "d1_xboole_0"), made_up, cited, held)
    with pytest.raises(BuildError, match="options t20_basic_0 and t5_basic_0 read the same"):
        check_problem(broken(one_problem, wrong, "t20_basic_0"), made_up, cited, held)
    with pytest.raises(BuildError, match="the held-back fact t5_basic_0 is among the given facts"):
        check_problem(dict(one_problem, given=[{"name": held, "statement": "?"}]), made_up, cited, held)
    with pytest.raises(BuildError, match="is not the held-back fact"):
        check_problem(dict(one_problem, held_back=wrong + 1), made_up, cited, held)
    with pytest.raises(BuildError, match="29 different options, not 30"):
        check_problem(dict(one_problem, options=one_problem["options"][:29]), made_up, cited, held)


def test_no_two_options_say_the_same_thing_and_none_repeats_a_given_fact_or_the_theorem(made_up, one_problem):
    cited, held = made_up.cited("t1_later_0"), "t5_basic_0"
    names = [o["name"] for o in one_problem["options"]]
    wrong = [n for n, name in enumerate(names) if name != held]
    # t20_basic_0 says what t5 says; as a second copy of another wrong option it is caught as a repeat too.
    twice = broken(one_problem, wrong[0], names[wrong[1]])
    with pytest.raises(BuildError, match="different options, not 30"):
        check_problem(twice, made_up, cited, held)
    same = broken(one_problem, wrong[0], "t20_basic_0")
    same = broken(same, wrong[1], "t20_basic_0")
    with pytest.raises(BuildError, match="different options"):
        check_problem(same, made_up, cited, held)
    given = dict(one_problem, given=[{"name": names[wrong[0]], "statement": "?"}])
    with pytest.raises(BuildError, match=f"option {names[wrong[0]]} reads the same as {names[wrong[0]]}"):
        check_problem(given, made_up, cited, held)


def test_two_options_with_one_statement_stop_the_build(made_up_copy):
    # t11_basic_0 rewritten to say what t12_basic_0 says: both are wrong options of t3_xboole_0's problem.
    path = made_up_copy.path / "statements"
    path.write_text(path.read_text().replace("fof(t11_basic_0, axiom, (! [A] : r1_basic_0(A, k1_basic_0(A, c11_basic_0)))).",
                                             "fof(t11_basic_0, axiom, (! [B] : r1_basic_0(B, k1_basic_0(B, c12_basic_0)))).", 1))
    builder = Builder(made_up_copy.load(), 7)
    neighbours = builder.neighbours("t3_xboole_0", "t10_basic_0", builder.library.cited("t3_xboole_0"))
    assert "t11_basic_0" in neighbours and "t12_basic_0" not in neighbours      # only the first of the two
    problem = builder.problem(builder.classify("t3_xboole_0"), "test-0001")
    names = [o["name"] for o in problem["options"]]
    n = next(i for i, name in enumerate(names) if name not in ("t10_basic_0", "t11_basic_0"))
    with pytest.raises(BuildError, match="options t12_basic_0 and t11_basic_0 read the same"):
        check_problem(broken(problem, n, "t12_basic_0"), builder.library, builder.library.cited("t3_xboole_0"),
                      "t10_basic_0")


def test_an_option_with_the_theorems_statement_stops_the_build(made_up_copy):
    # t11_basic_0 rewritten to say what t3_xboole_0 says: it is no neighbour for t3_xboole_0, and as an option
    # it stops the build.
    path = made_up_copy.path / "statements"
    path.write_text(path.read_text().replace("fof(t11_basic_0, axiom, (! [A] : r1_basic_0(A, k1_basic_0(A, c11_basic_0)))).",
                                             "fof(t11_basic_0, axiom, (! [C, D] : r1_basic_0(k3_xboole_0(C, D), k2_xboole_0(C, D)))).", 1))
    builder = Builder(made_up_copy.load(), 7)
    cited = builder.library.cited("t3_xboole_0")
    assert "t11_basic_0" not in builder.neighbours("t3_xboole_0", "t10_basic_0", cited)
    problem = builder.problem(builder.classify("t3_xboole_0"), "test-0001")
    n = next(i for i, o in enumerate(problem["options"]) if o["name"] != "t10_basic_0")
    with pytest.raises(BuildError, match="option t11_basic_0 reads the same as t3_xboole_0"):
        check_problem(broken(problem, n, "t11_basic_0"), builder.library, cited, "t10_basic_0")


def test_a_theorem_citing_itself_stops_the_build(made_up_copy):
    references = made_up_copy.path / "00mizrefs"
    references.write_text(references.read_text().replace("t2_xboole_0:t1_xboole_0", "t2_xboole_0:t2_xboole_0,t1_xboole_0"))
    with pytest.raises(BuildError, match="t2_xboole_0: it cites itself"):
        built(made_up_copy.load())


def test_the_checks_on_the_sets_fail_once(made_up):
    records, test, train = built(made_up)
    check_sets(test, train, 2, ARTICLES)
    # Too few and too many test problems both stop the build.
    with pytest.raises(BuildError, match="1 test problems, not exactly 2"):
        check_sets(test[:1], train[:], 2, ARTICLES)
    with pytest.raises(BuildError, match="3 test problems, not exactly 2"):
        check_sets(test + train[:1], train[1:], 2, ARTICLES)
    with pytest.raises(BuildError, match=f"theorems in both sets: \\['{test[0]['theorem']}'\\]"):
        check_sets(test, train + [dict(test[0], id="train-0099")], 2, ARTICLES)
    # A training problem from another article: either field shows it, the theorem's name or the article recorded.
    for field in ({"article": "later_0"}, {"theorem": "t1_later_0"}):
        with pytest.raises(BuildError, match="training problems whose theorem is not of the articles"):
            check_sets(test, train + [dict(train[0], id="train-0099", **field)], 2, ARTICLES)
    with pytest.raises(BuildError, match="5 qualifying theorems, fewer than 6"):
        built(made_up, test_count=6)


def test_a_theorem_in_no_bin_or_in_two_stops_the_build(made_up):
    records, _, _ = built(made_up)
    theorems = [r["theorem"] for r in records]
    check_bins(records, theorems)
    with pytest.raises(BuildError, match=r"in two bins \['t2_xboole_0'\]"):
        check_bins(records + [dict(records[1], bin="qualifies")], theorems)
    with pytest.raises(BuildError, match=r"in no bin \['t1_xboole_0'\]"):
        check_bins(records[1:], theorems)
    with pytest.raises(BuildError, match="unknown bin"):
        check_bins([dict(records[0], bin="maybe")] + records[1:], theorems)
    with pytest.raises(BuildError, match=r"not of the articles \['t9_xboole_0'\]"):
        check_bins(records + [dict(records[0], theorem="t9_xboole_0")], theorems)


@pytest.mark.slow
def test_the_real_build(real_library):
    """The build on the real files with the plan's seed. Guards against a change to the build rules going unseen:
    the bins must be the counts the current rules gave on these files, with 300 test problems and every other
    qualifying theorem (900) as training problems, all of the 33 articles. Also: in every test problem no two
    options with one statement, no option repeating a given fact or the theorem, and shown text whose brackets
    balance; and every fact line of the test problems' files as the statements file has it."""
    from mizar_ladder.library import PROBLEMS, parse_fof
    from mizar_ladder.statements import renamed, shown_key, structure_balanced
    records, test, train = build(real_library, 20261112)
    bins = {name: sum(r["bin"] == name for r in records) for name in problems.BINS}
    assert bins == REAL_BINS
    assert len(records) == 2170 and len(test) == 300 and len(train) == 900
    assert {p["theorem"] for p in test} | {p["theorem"] for p in train} == {r["theorem"] for r in records
                                                                            if r["bin"] == "qualifies"}
    names = real_library.mizar_names()
    found = []
    for p in test:
        others = [p["theorem"]] + [g["name"] for g in p["given"]]
        # Three ways of reading: the statement, the shown text with variables renamed, and the text exactly as
        # saved for the solver (white space aside).
        saved = {p["theorem"]: p["statement"], **{f["name"]: f["statement"] for f in p["given"] + p["options"]}}
        for key in (lambda n: tuple(renamed(real_library.statement(n))),
                    lambda n: shown_key(real_library.statement(n), names),
                    lambda n: "".join(saved[n].split())):
            options = [key(o["name"]) for o in p["options"]]
            if len(set(options)) != 30 or set(options) & {key(n) for n in others}:
                found.append(f"{p['id']}: two of its facts read the same")
        for name in [p["theorem"]] + [g["name"] for g in p["given"]] + [o["name"] for o in p["options"]]:
            if not structure_balanced(real_library.statement(name), names):
                found.append(f"{p['id']}: {name} shown with unbalanced brackets")
        folder = real_library.folder / PROBLEMS / p["article"]
        for line in open(folder / f"{p['article']}__{p['theorem']}"):
            if line.startswith("fof("):
                name, _, formula = parse_fof(line.strip())
                if formula != real_library.statement(name):
                    found.append(f"{p['id']}: {name} differs from the statements file")
    assert found == []


def two_symbols_one_name(copy, *pairs):
    """The copy's name table with each pair of constants given one Mizar name (as Mizar gives one name to
    several symbols); returns the library read again."""
    names = copy.path / "00constrnames"
    names.write_text(names.read_text() + "".join(f"{a} K{n}\n{b} K{n}\n" for n, (a, b) in enumerate(pairs)))
    return copy.load()


def cite_also(copy, theorem, fact):
    """`theorem` cites `fact` as well, and its problem file holds it."""
    references = copy.path / "00mizrefs"
    references.write_text(references.read_text().replace(f"{theorem}:", f"{theorem}:{fact},", 1))
    article_name = theorem.split("_", 1)[1]
    path = copy.path / "problems_small_consist" / article_name / f"{article_name}__{theorem}"
    statement = next(line for line in (copy.path / "statements").read_text().splitlines() if line.startswith(f"fof({fact},"))
    path.write_text(path.read_text() + statement + "\n")


def test_two_statements_shown_as_one_text_are_two_candidates_of_which_one_is_kept(made_up_copy):
    library = two_symbols_one_name(made_up_copy, ("c11_basic_0", "c12_basic_0"))
    builder = Builder(library, 7)
    assert library.statement("t11_basic_0") != library.statement("t12_basic_0")
    assert builder.keys("t11_basic_0") & builder.keys("t12_basic_0")              # the same shown text
    neighbours = builder.neighbours("t3_xboole_0", "t10_basic_0", library.cited("t3_xboole_0"))
    assert "t11_basic_0" in neighbours and "t12_basic_0" not in neighbours
    problem = builder.problem(builder.classify("t3_xboole_0"), "test-0001")
    n = next(i for i, o in enumerate(problem["options"]) if o["name"] not in ("t10_basic_0", "t11_basic_0"))
    with pytest.raises(BuildError, match="options t12_basic_0 and t11_basic_0 read the same"):
        check_problem(broken(problem, n, "t12_basic_0"), library, library.cited("t3_xboole_0"), "t10_basic_0")


def test_a_candidate_shown_as_a_given_fact_is_no_neighbour(made_up_copy):
    cite_also(made_up_copy, "t3_xboole_0", "t13_basic_0")
    library = two_symbols_one_name(made_up_copy, ("c13_basic_0", "c14_basic_0"))
    builder = Builder(library, 7)
    cited = library.cited("t3_xboole_0")
    assert cited[0] == "t13_basic_0"
    neighbours = builder.neighbours("t3_xboole_0", "t10_basic_0", cited)
    assert "t13_basic_0" not in neighbours and "t14_basic_0" not in neighbours
    record = builder.classify("t3_xboole_0")
    problem = builder.problem(record, "test-0001")
    n = next(i for i, o in enumerate(problem["options"]) if o["name"] != record["held_back"])
    expected = ("option t14_basic_0 reads the same as t13_basic_0" if record["held_back"] == "t10_basic_0"
                else "options t14_basic_0 and t13_basic_0 read the same")       # t13 given, or an option itself
    with pytest.raises(BuildError, match=expected):
        check_problem(broken(problem, n, "t14_basic_0"), library, cited, record["held_back"])


def test_a_cited_fact_shown_as_another_cited_fact_cannot_be_held_back(made_up_copy):
    # t3_xboole_0 cites t13_basic_0 and t10_basic_0, shown as one text: neither can be held back, and it is not
    # usable. Without the shared name both can be.
    cite_also(made_up_copy, "t3_xboole_0", "t13_basic_0")
    before = Builder(made_up_copy.load(), 7)
    assert before.can_be_held_back("t3_xboole_0", before.library.cited("t3_xboole_0")) == ["t13_basic_0", "t10_basic_0"]
    problem = before.problem(before.classify("t3_xboole_0"), "test-0001")
    library = two_symbols_one_name(made_up_copy, ("c10_basic_0", "c13_basic_0"))
    builder = Builder(library, 7)
    assert builder.can_be_held_back("t3_xboole_0", library.cited("t3_xboole_0")) == []
    assert builder.classify("t3_xboole_0")["bin"] == "not usable"
    # The check covers the held-back option too: shown as a given fact, it stops the build.
    held = problem["options"][problem["held_back"] - 1]["name"]
    with pytest.raises(BuildError, match=f"option {held} reads the same as"):
        check_problem(problem, library, library.cited("t3_xboole_0"), held)


def restate(copy, fact, statement):
    path = copy.path / "statements"
    lines = [f"fof({fact}, axiom, {statement})." if line.startswith(f"fof({fact},") else line
             for line in path.read_text().splitlines()]
    path.write_text("\n".join(lines) + "\n")
    for problem_file in (copy.path / "problems_small_consist").rglob("*"):
        if problem_file.is_file():
            text = problem_file.read_text().splitlines()
            problem_file.write_text("\n".join(f"fof({fact}, axiom, {statement})." if l.startswith(f"fof({fact}, axiom,")
                                              else l for l in text) + "\n")


def test_a_swap_of_two_variables_is_one_statement_as_candidates_and_against_a_given_fact(made_up_copy):
    # t11 and t12 rewritten to one fact with A and B swapped in the quantifier's list.
    restate(made_up_copy, "t11_basic_0", "(! [A, B] : r1_basic_0(A, k1_basic_0(B, c11_basic_0)))")
    restate(made_up_copy, "t12_basic_0", "(! [B, A] : r1_basic_0(A, k1_basic_0(B, c11_basic_0)))")
    library = made_up_copy.load()
    builder = Builder(library, 7)
    neighbours = builder.neighbours("t3_xboole_0", "t10_basic_0", library.cited("t3_xboole_0"))
    assert "t11_basic_0" in neighbours and "t12_basic_0" not in neighbours
    cite_also(made_up_copy, "t3_xboole_0", "t11_basic_0")
    library = made_up_copy.load()
    neighbours = Builder(library, 7).neighbours("t3_xboole_0", "t10_basic_0", library.cited("t3_xboole_0"))
    assert "t11_basic_0" not in neighbours and "t12_basic_0" not in neighbours


def test_a_pair_that_differs_in_more_than_names_stays_two(made_up_copy):
    restate(made_up_copy, "t11_basic_0", "(! [A, B] : r1_basic_0(A, k1_basic_0(B, c11_basic_0)))")
    restate(made_up_copy, "t12_basic_0", "(! [A, B] : r1_basic_0(B, k1_basic_0(B, c11_basic_0)))")
    library = made_up_copy.load()
    neighbours = Builder(library, 7).neighbours("t3_xboole_0", "t10_basic_0", library.cited("t3_xboole_0"))
    assert "t11_basic_0" in neighbours and "t12_basic_0" in neighbours


def test_a_cited_fact_that_reads_like_the_theorem_cannot_be_held_back(made_up_copy):
    # t13_basic_0 rewritten to t3_xboole_0's statement with its list in the other order, and cited by it.
    restate(made_up_copy, "t13_basic_0", "(! [B, A] : r1_basic_0(k3_xboole_0(A, B), k2_xboole_0(A, B)))")
    cite_also(made_up_copy, "t3_xboole_0", "t13_basic_0")
    library = made_up_copy.load()
    assert Builder(library, 7).can_be_held_back("t3_xboole_0", library.cited("t3_xboole_0")) == ["t10_basic_0"]
