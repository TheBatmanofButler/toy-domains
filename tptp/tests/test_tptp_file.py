"""Tests for tptp_file.py on five real TPTP files (tests/fixtures/tptp/, in the library's own layout) and on
hand-made text, including the quantifier-list fault of an earlier reader."""
import pytest

from conftest import FIXTURES, pilot_code
from tptp_count.equations import read_equation, write_equation
from tptp_count.tptp_file import (Statement, TptpError, axioms_and_goal, is_theorem, read_file, read_statements,
                                  relation, usable)

LIBRARY = FIXTURES / "tptp"


def test_usable_with_no_includes():
    file = read_file("Problems/GRP/GRP001-4.p", LIBRARY)
    assert (file.area, file.status, usable(file)) == ("GRP", "Unsatisfiable", True)
    axioms, goal = axioms_and_goal(file)
    assert [write_equation(a) for a in axioms] == ["multiply(multiply(X,Y),Z)=multiply(X,multiply(Y,Z))",
                                                   "multiply(identity,X)=X", "multiply(X,X)=identity",
                                                   "multiply(a,b)=c"]   # hypotheses are given as true too
    assert write_equation(goal) == "multiply(b,a)=c"


def test_usable_with_an_included_axiom_file():
    file = read_file("Problems/GRP/GRP001-2.p", LIBRARY)
    assert usable(file) is True
    axioms, goal = axioms_and_goal(file)
    # the three axioms of Axioms/GRP004-0.ax come first, where the include line stands
    assert [s.name for s in file.statements] == ["left_identity", "left_inverse", "associativity", "right_identity",
                                                 "right_inverse", "squareness", "a_times_b_is_c",
                                                 "prove_b_times_a_is_c"]
    assert write_equation(axioms[0]) == "multiply(identity,X)=X"
    assert write_equation(goal) == "multiply(b,a)=c"


def test_a_statement_that_is_not_a_single_equation():
    file = read_file("Problems/GRP/GRP001-5.p", LIBRARY)
    assert usable(file) == "statement left_identity is not a single equation"
    assert len(file.statements) == 1     # reading stopped there


def test_a_goal_made_of_two_statements():
    file = read_file("Problems/GRP/GRP664-10.p", LIBRARY)
    assert usable(file) == "goal is made of 2 statements"


def test_a_status_that_is_not_a_theorem():
    file = read_file("Problems/GRP/GRP112-10.p", LIBRARY)
    assert usable(file) is True
    assert file.status == "Satisfiable"
    assert not is_theorem(file.status)
    assert is_theorem("Unsatisfiable")
    # only the word TPTP uses for a file in denied form whose goal follows; Theorem is the word for files that
    # state their goal as a conjecture, which are not used
    assert not any(is_theorem(s) for s in ("Theorem", "ContradictoryAxioms", "CounterSatisfiable", "Satisfiable",
                                           "Unknown", "Open", ""))


def _file(text, tmp_path, name="Problems/TST/TST001-1.p"):
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(text)
    return read_file(name, tmp_path)


def test_a_quantifier_list_is_not_cut_at_its_comma(tmp_path):
    text = "fof(commutes,axiom, ! [X,Y] : f(X,Y) = f(Y,X) ).\nfof(goal,negated_conjecture, f(a,b) != f(b,a) ).\n"
    file = _file(text, tmp_path)
    assert usable(file) is True
    assert write_equation(axioms_and_goal(file)[0][0]) == "f(X,Y)=f(Y,X)"
    # the earlier reader (kept in tests/reference/) cut the formula at the comma inside [X,Y]
    pilot_code()
    from fol import tptp as earlier
    (tmp_path / "earlier.p").write_text(text)
    assert earlier.read_formulas(str(tmp_path / "earlier.p"), str(tmp_path))[0][3] == "! [X"


def test_the_fixed_earlier_reader_agrees(tmp_path):
    text = "fof(commutes,axiom, ! [X,Y] : f(X,Y) = f(Y,X) ).\n"
    (tmp_path / "x.p").write_text(text)
    pilot_code()
    from pt.stage0 import read_formulas_fixed
    assert read_formulas_fixed(str(tmp_path / "x.p"), str(tmp_path))[0][3] == "! [X,Y] : f(X,Y) = f(Y,X)"


@pytest.mark.parametrize("formula, language, expected", [
    ("( mult(X,e) = X )", "cnf", ("=", "mult(X,e)=X")),
    ("mult(a,b) != c", "cnf", ("!=", "mult(a,b)=c")),
    ("~ ( a = b )", "cnf", ("!=", "a=b")),
    ("( ~ p(X) | q(X) )", "cnf", None),
    ("p(X)", "cnf", None),
    ("! [X] : ( ! [Y] : f(X,Y) = X )", "fof", ("=", "f(X,Y)=X")),
    ("? [X] : f(X) = X", "fof", None),
    ("! [X] : ( f(X) = X & g(X) = X )", "fof", None),
    ("f(X) = X", "tff", None),
    ("$true = a", "cnf", None),
])
def test_relation(formula, language, expected):
    found = relation(Statement(language, "s", "axiom", formula))
    assert (found if found is None else (found[0], write_equation(found[1]))) == expected


@pytest.mark.parametrize("text, reason", [
    ("cnf(a,axiom,f(X)=X).\n", "no goal"),
    ("cnf(a,axiom,f(X)=X).\ncnf(g,conjecture,f(a)=a).\n", "goal is not a denied equation"),
    ("cnf(a,axiom,f(X)=X).\ncnf(g,negated_conjecture,f(a)=a).\n", "goal is not a denied equation"),
    ("cnf(a,axiom,f(X)!=X).\ncnf(g,negated_conjecture,f(a)!=a).\n", "statement a is an inequality"),
    ("cnf(a,type,f(X)=X).\ncnf(g,negated_conjecture,f(a)!=a).\n", "statement a has role type"),
    ("cnf(a,axiom,f(X)=X).\ncnf(g,negated_conjecture,(f(a)!=a|b!=a)).\n", "goal is not a single equation"),
    ("tff(a,axiom,f(X)=X).\n", "statement a is not a single equation"),
    ("cnf('" + "x" * 50 + "',axiom,p).\n", "statement '" + "x" * 36 + "... is not a single equation"),
])
def test_reasons_a_file_is_not_usable(text, reason, tmp_path):
    assert usable(_file(text, tmp_path)) == reason


def test_includes_with_a_selection_and_comments(tmp_path):
    (tmp_path / "Axioms").mkdir()
    (tmp_path / "Axioms" / "A.ax").write_text("cnf(one,axiom,f(X)=X).\ncnf(two,axiom,g(X)=X).\n/* a comment */\n")
    text = ("% Status   : Unsatisfiable\ninclude('Axioms/A.ax',[two]).\n"
            "cnf(g, negated_conjecture, % a comment with ) and '\n g(a) != a, inference(x,[status(thm)],[])).\n")
    file = _file(text, tmp_path)
    assert [s.name for s in file.statements] == ["two", "g"]
    assert usable(file) is True and file.status == "Unsatisfiable"


@pytest.mark.parametrize("text", ["cnf(a,axiom,f(X)=X)", "cnf(a,axiom,f(X)=X.", "cnf(a,axiom).",
                                  "cnf(a,axiom,f(X)=X). junk", "/* open", "include('Axioms/none.ax')."])
def test_broken_files_stop_loudly(text, tmp_path):
    with pytest.raises(TptpError):
        _file(text, tmp_path)


def test_a_file_including_itself_stops_loudly(tmp_path):
    (tmp_path / "Axioms").mkdir()
    (tmp_path / "Axioms" / "loop.ax").write_text("include('Axioms/loop.ax').\n")
    with pytest.raises(TptpError):
        _file("include('Axioms/loop.ax').\n", tmp_path)


def test_read_statements_keeps_quoted_commas_inside_one_part():
    found = list(read_statements("cnf('a,b',axiom,f(X)=X,file('x,y.p',z))."))
    assert found == [("cnf", ["'a,b'", "axiom", "f(X)=X", "file('x,y.p',z)"])]
    assert read_equation("f(X)=X") == read_equation(found[0][1][2])
