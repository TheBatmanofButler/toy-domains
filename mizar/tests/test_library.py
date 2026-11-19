"""Tests of library.py: reading small saved pieces of each real file, names read by rule, and the checksum check.
The slow tests read the real files: every cited fact is in its theorem's problem file and stated earlier, and the
counts of facts, theorems and articles are those written here (counted once from the files, 2026-11-14)."""
import pytest
from conftest import PIECES, ROOT, checksums_of

from mizar_ladder.library import (ARTICLES, GROUPS, Library, LibraryError, article, group, kind, parse_fof,
                                  readme_checksums)


@pytest.fixture(scope="module")
def pieces():
    return Library(PIECES, checksums_of(PIECES))


def test_kind_and_article_on_hand_made_names():
    assert kind("t12_xboole_1") == "theorem" and article("t12_xboole_1") == "xboole_1"
    assert kind("l3_waybel_0") == "lemma" and article("l3_waybel_0") == "waybel_0"
    assert kind("d10_xboole_0") == "definition" and article("d10_xboole_0") == "xboole_0"
    assert kind("t1_tarski") == "theorem" and article("t1_tarski") == "tarski"
    # Names of other kinds, including ones that start with t, l or d but not with a number after it.
    for name in ("dt_k1_tarski", "rc1_xboole_0", "fc1_xboole_0", "reflexivity_r1_tarski", "l1_", "t_xboole_1",
                 "abstractness_v1_pre_topc", "tx_xboole_1"):
        assert kind(name) == "other", name
    assert article("t1_") == "" and article("existence_m1_subset_1") == "m1_subset_1"
    with pytest.raises(LibraryError, match="no article"):
        article("t1")


def test_the_33_articles_and_their_groups():
    assert len(ARTICLES) == len(set(ARTICLES)) == 33
    assert sorted(a for articles in GROUPS.values() for a in articles) == sorted(ARTICLES)
    assert [len(articles) for articles in GROUPS.values()] == [15, 11, 7]
    assert group("tops_1") == "topology" and group("yellow19") == "orderings and lattices"
    assert group("xboole_1") == "sets, relations and functions" and group("card_1") is None


def test_pieces_of_the_real_files(pieces):
    facts = pieces.facts()
    names = [name for name, _ in facts]
    # Every fact the six problem files name, in the real library's order (tarski before xboole_0 before xboole_1).
    assert names[:2] == ["reflexivity_r1_tarski", "d3_tarski"] and len(names) == 38
    assert names.index("d10_xboole_0") == 17 and names.index("t3_xboole_1") == 34
    assert pieces.statement("t3_xboole_1") == "(! [A] :  (r1_tarski(A, k1_xboole_0) => A=k1_xboole_0) )"
    assert pieces.position("t2_xboole_1") < pieces.position("t3_xboole_1")
    assert pieces.theorems() == ["t1_xboole_1", "t2_xboole_1", "t3_xboole_1", "t4_xboole_1", "t5_xboole_1",
                                 "t83_xboole_1"]
    assert pieces.theorems({"tarski"}) == [] and pieces.articles() == ["xboole_1"]
    statement, in_file = pieces.problem_file("t3_xboole_1")
    assert statement == pieces.statement("t3_xboole_1")
    assert in_file[:3] == ["antisymmetry_r2_hidden", "d10_xboole_0", "d2_xboole_0"] and len(in_file) == 13
    assert in_file[-1] == "t8_boole" and "t3_xboole_1" not in in_file


def test_cited_facts_keep_the_order_of_first_mention_without_repeats(pieces):
    # The real line is "t1_xboole_1:d3_tarski,d3_tarski,d3_tarski".
    assert pieces.cited("t1_xboole_1") == ["d3_tarski"]
    assert pieces.cited("t3_xboole_1") == ["t2_xboole_1", "d10_xboole_0"]
    assert pieces.references()["t2_xboole_1"] == ["d3_tarski"]
    with pytest.raises(LibraryError, match="no line"):
        pieces.cited("t1_tarski")


def test_mizar_names_take_the_first_one_listed(pieces):
    names = pieces.mizar_names()
    assert names["r1_xboole_0"] == "misses"       # listed as misses, then meets
    assert names["k3_xboole_0"] == "/\\" and names["r1_tarski"] == "c=" and names["k1_xboole_0"] == "{}"
    assert "o_0_0_xboole_0" not in names


def test_a_wrong_checksum_stops_the_run(tmp_path):
    checksums = checksums_of(PIECES)
    checksums["seq"] = "0" * 64
    with pytest.raises(LibraryError, match="seq: sha256 .* README.md says 0000"):
        Library(PIECES, checksums)
    with pytest.raises(LibraryError, match="no checksums"):
        Library(PIECES, {})


def test_the_checksums_are_read_from_readme():
    found = readme_checksums(ROOT / "README.md")
    assert sorted(found) == ["00constrnames", "00mizrefs", "seq", "statements", "xboole_1.miz"]
    assert found["statements"] == "ad845ce9a6a8ec2a846cbc24d594bc441b2f9530fb4319a657d7c9b272b8eec5"
    # Without checksums given, the library checks against README.md, which the pieces do not match.
    with pytest.raises(LibraryError, match="README.md says"):
        Library(PIECES)


def test_lines_that_are_not_fof_or_a_stray_problem_file_stop_it(tmp_path, made_up_copy):
    with pytest.raises(LibraryError, match="not a fof line"):
        parse_fof("cnf(a, axiom, p).")
    assert parse_fof("fof(a_b, axiom,  p(A) ).") == ("a_b", "axiom", "p(A)")
    stray = made_up_copy.path / "problems_small_consist" / "basic_0" / "basic_0__t99_basic_0"
    stray.write_text("")
    with pytest.raises(LibraryError, match="unexpected problem file"):
        made_up_copy.load()


def test_a_problem_file_without_its_conjecture_stops_it(made_up_copy):
    path = made_up_copy.path / "problems_small_consist" / "xboole_0" / "xboole_0__t2_xboole_0"
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(line for line in lines if "conjecture" not in line))
    with pytest.raises(LibraryError, match="no conjecture"):
        made_up_copy.load().problem_file("t2_xboole_0")
    path.write_text("".join(lines) + lines[1])
    with pytest.raises(LibraryError, match="expected t2_xboole_0 once"):
        made_up_copy.load().problem_file("t2_xboole_0")


def test_statements_and_order_must_name_the_same_facts(made_up_copy):
    seq = made_up_copy.path / "seq"
    seq.write_text(seq.read_text() + "t99_basic_0\n")
    with pytest.raises(LibraryError, match="do not name the same facts"):
        made_up_copy.load()
    seq.write_text(seq.read_text() + "t99_basic_0\n")
    with pytest.raises(LibraryError, match="listed twice"):
        made_up_copy.load()


@pytest.mark.slow
def test_the_real_files_counts_and_every_cited_fact(real_library):
    assert len(real_library.facts()) == 146700
    assert len(real_library.theorems()) == 57897 and len(real_library.articles()) == 1148
    assert len(real_library.theorems(set(ARTICLES))) == 2170
    assert set(ARTICLES) <= set(real_library.articles())
    problems = []
    for theorem in real_library.theorems():
        statement, in_file = real_library.problem_file(theorem)
        if statement != real_library.statement(theorem):
            problems.append(f"{theorem}: its problem file states it otherwise")
        in_file = set(in_file)
        for fact in real_library.cited(theorem):
            if fact not in in_file:
                problems.append(f"{theorem}: cited {fact} is not in its problem file")
            elif real_library.position(fact) >= real_library.position(theorem):
                problems.append(f"{theorem}: cited {fact} is stated after it")
    assert problems == []
