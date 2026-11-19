"""Tests of statements.py: `show` on ten real statements, each saved with the text written by hand from the name
table (tests/reference/make_fixtures.py); `symbols` and `length` on hand cases; `same_statement` on pairs."""
import json
import re

import pytest
from conftest import FIXTURES

from mizar_ladder.statements import (balanced, is_operator, length, same_statement, show, shown_key,
                                     structure_balanced, symbols)

# The names the ten real statements need, as the real 00constrnames gives them first.
REAL_NAMES = {"r1_tarski": "c=", "k1_xboole_0": "{}", "k2_xboole_0": "\\/", "r2_hidden": "in",
              "v1_relat_1": "Relation-like", "v1_funct_1": "Function-like", "k4_tarski": "[..]",
              "k9_xtuple_0": "proj1", "k1_funct_1": ".", "r1_xboole_0": "misses", "k4_xboole_0": "\\",
              "k2_zfmisc_1": "[:..:]", "v2_struct_0": "empty", "l2_lattices": "\\/-SemiLattStr",
              "m1_subset_1": "Element", "u1_struct_0": "carrier", "k1_lattices": "\"\\/\"", "k5_binop_1": ".",
              "u2_lattices": "L_join"}


def saved():
    return json.loads((FIXTURES / "shown_statements.json").read_text())


def test_there_are_ten_and_one_has_a_symbol_without_a_name():
    statements = saved()
    assert len(statements) == 10
    assert any("o_0_0_xboole_0" in s["statement"] and "o_0_0_xboole_0" in s["shown"] for s in statements)
    assert "o_0_0_xboole_0" not in REAL_NAMES


@pytest.mark.parametrize("saved_statement", saved(), ids=lambda s: s["name"])
def test_show_on_real_statements(saved_statement):
    assert show(saved_statement["statement"], REAL_NAMES) == saved_statement["shown"]


def test_show_on_hand_cases():
    names = {"k1_a": "+", "r1_a": "<=", "k2_a": "f", "r1_b": "misses", "v4_relat_1": "-defined", "k3_a": "*"}
    assert show("r1_a(k1_a(A, B), C)", names) == "(A + B) <= C"
    assert show("k2_a(A, B)=k1_a(A, k1_a(B, C))", names) == "f(A, B)=(A + (B + C))"
    assert show("r1_b(A,  B)", names) == "misses(A,  B)"                 # a word stays in front, spacing kept
    assert show("v4_relat_1(R, X)", names) == "-defined(R, X)"            # "-" alone does not make it symbolic
    assert show("k3_a(A, B, C)", names) == "*(A, B, C)"                   # three places: in front
    assert show("k3_a(A)", names) == "*(A)" and show("k9_z(A, B)", names) == "k9_z(A, B)"   # no name: as it is
    assert show(" ~ (r1_a(A, B)) & $true ", names) == " ~ (A <= B) & $true "
    assert show("Ak1_a(B)", names) == "Ak1_a(B)"                           # part of a variable's name is not a symbol
    for broken in ("k1_a(A, B", "(A", "r1_a(A,"):
        with pytest.raises(ValueError, match="unbalanced"):
            show(broken, names)
    with pytest.raises(ValueError, match="unbalanced"):
        show("A) & B", names)


def test_names_with_brackets_or_two_dots_go_in_front():
    # The real names of k1_filter_0 (<....)), k4_tarski ([..]), k2_zfmisc_1 ([:..:]), k2_tarski ({..}),
    # r3_lattices ([=) and k1_lattices ("\/", three places).
    names = {"k1_filter_0": "<....)", "k4_tarski": "[..]", "k2_zfmisc_1": "[:..:]", "k2_tarski": "{..}",
             "r3_lattices": "[=", "k1_lattices": '"\\/"', "k3_xboole_0": "/\\"}
    assert show("k1_filter_0(A, B)=C", names) == "<....)(A, B)=C"
    assert show("r2_hidden(k4_tarski(A, B), C)", names) == "r2_hidden([..](A, B), C)"
    assert show("k2_zfmisc_1(A, k3_xboole_0(B, C))", names) == "[:..:](A, (B /\\ C))"
    assert show("k2_tarski(A, B)=k2_tarski(B, A)", names) == "{..}(A, B)={..}(B, A)"
    assert show("r3_lattices(A, B, C)", names) == "[=(A, B, C)"
    assert show("k1_lattices(A, B, C)=B", names) == '"\\/"(A, B, C)=B'
    operators = ("/\\", "c=", ".", "\\+\\")
    others = ("in", "-defined", "[..]", "{..}", "[:..:]", "<....)", "[=", "..", "a(b")
    assert all(is_operator(n) for n in operators) and not any(is_operator(n) for n in others)


def test_brackets_balance():
    assert balanced("(a [b] {c})") and balanced("") and not balanced("(]") and not balanced("((") and not balanced(")(")
    # A name's own bracket is part of the name: the text's structure still balances.
    assert structure_balanced("r3_lattices(A, B, C)", {"r3_lattices": "[="})
    assert not balanced(show("r3_lattices(A, B, C)", {"r3_lattices": "[="}))


def test_symbols_and_length():
    statement = "(! [A, B] : (r1_tarski(A, k2_xboole_0(A, B)) & ~ (v1_xboole_0(k2_xboole_0(B, A))) & $true))"
    assert symbols(statement) == ["r1_tarski", "k2_xboole_0", "v1_xboole_0"]
    # 4 symbols (r1_tarski, k2_xboole_0 twice, v1_xboole_0) and 7 variables (A and B in the list, then 5 more).
    assert length(statement) == 11
    assert symbols("A=B") == [] and length("A=B") == 2 and length("$true") == 0


def test_same_statement():
    assert same_statement("(! [A] : r1_tarski(A, A))", "(! [B] : r1_tarski(B, B))")
    assert same_statement("(! [A, B] : k1_a(A, B)=B)", "(! [C, A] :  k1_a(C,A)=A)")    # white space ignored
    assert not same_statement("(! [A, B] : k1_a(A, B)=B)", "(! [A, B] : k1_a(B, A)=B)")
    assert not same_statement("(! [A] : r1_tarski(A, A))", "(! [A] : r2_tarski(A, A))")
    assert not same_statement("(! [A, B] : r1_a(A, B))", "(! [A] : r1_a(A, A))")


def test_a_shown_text_whose_brackets_would_not_balance_stops(monkeypatch):
    # Not reachable from a statement that balances; the guard is checked by making the check fail.
    from mizar_ladder import statements
    monkeypatch.setattr(statements, "structure_balanced", lambda statement, names: False)
    with pytest.raises(ValueError, match="unbalanced brackets"):
        statements.show("p(A)", {})


def test_a_swap_in_a_quantifiers_list_is_the_same_statement():
    # As t51_zfmisc_1 and l143_zfmisc_1: one fact with B and C swapped in the list.
    one = "(! [A, B, C] : (r1_a(A, k1_a(B, C)) => r1_a(A, B)))"
    swapped = "(! [A, C, B] : (r1_a(A, k1_a(C, B)) => r1_a(A, C)))"
    assert same_statement(one, swapped)
    assert same_statement("(! [B, A] : r1_a(A, B))", "(! [A, B] : r1_a(A, B))")
    # The library writes "for A, B, C" as quantifiers nested one in another: as t51_zfmisc_1 and l143_zfmisc_1,
    # where B and C are swapped, the run counts as one list.
    t51 = "(! [A] :  (! [B] :  (! [C] :  ~ ( ( ~ (r2_hidden(A, B))  &  ~ (r1_xboole_0(k2_tarski(A, C), B)) ) ) ) ) )"
    l143 = "(! [A] :  (! [B] :  (! [C] :  ~ ( ( ~ (r2_hidden(A, C))  &  ~ (r1_xboole_0(k2_tarski(A, B), C)) ) ) ) ) )"
    assert same_statement(t51, l143)
    # More than names: another argument, quantifiers of two kinds exchanged, or a nesting that is not direct.
    assert not same_statement(one, "(! [A, B, C] : (r1_a(A, k1_a(B, C)) => r1_a(A, C)))")
    assert not same_statement("(! [A] : (? [B] : r1_a(A, B)))", "(! [A] : (? [B] : r1_a(B, A)))")
    assert not same_statement("(! [A] : ((! [B] : r1_a(A, B)) & p(A)))", "(! [A] : ((! [B] : r1_a(B, A)) & p(A)))")
    names = {"r1_a": "<", "k1_a": "+"}
    assert shown_key(one, names) == shown_key(swapped, names) == "(![V0,V1,V2]:(V0<(V1+V2)=>V0<V1))"


def test_the_shown_key_renames_variables_before_showing():
    # Two Mizar names with capital letters: renaming capitalised words after showing would make these two one key.
    names = {"k1_a": "Element", "k2_a": "TopStruct"}
    one, other = shown_key("(! [A] : k1_a(A)=A)", names), shown_key("(! [A] : k2_a(A)=A)", names)
    assert one == "(![V0]:Element(V0)=V0)" and other == "(![V0]:TopStruct(V0)=V0)" and one != other
    after = [re.sub(r"\b[A-Z][A-Za-z0-9_]*\b", "V", show(s, names)) for s in ("k1_a(A)", "k2_a(A)")]
    assert after[0] == after[1]          # the wrong way, shown here so the test means something
