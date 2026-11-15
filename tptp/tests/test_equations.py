"""Tests for equations.py and renaming.py: reading and writing, size, the keys, and agreement with the earlier
pilot's code on 1,000 equations from its saved problems."""
import random

import pytest

from conftest import pilot_code, read_jsonl_gz
from tptp_count.equations import (EquationError, is_instance, key, key_up_to_variables, read_equation, rename_symbols,
                                  size, substitute, symbol_renaming, symbols, universal_form, variables, write_equation)

E = read_equation
GROUP = ["mult(mult(X,Y),Z)=mult(X,mult(Y,Z))", "mult(e,X)=X", "mult(inv(X),X)=e"]


@pytest.mark.parametrize("text", ["f(X,g(Y))=X", "a=b", "mult(e,X)=X", "'a b'(X)=c", "f(f(f(X)))=f(X)", "X=Y",
                                  "s2_x2(v(X),s0_nil4)=v(X)", "f(1,X)=X"])
def test_reading_then_writing_gives_the_text_back(text):
    assert write_equation(E(text)) == text


def test_spaces_are_allowed_when_reading():
    assert E(" f( X , g(Y) ) =  X ") == E("f(X,g(Y))=X")


@pytest.mark.parametrize("text", ["f(X)", "f(X)!=X", "f(X=X", "f(X))=X", "$true=X", "f(X)=X junk", "=X", "f(,X)=X",
                                  "f(X;Y)=X"])
def test_what_is_not_an_equation_is_refused(text):
    with pytest.raises(EquationError):
        E(text)


def test_size_and_variables():
    assert size(E("f(X,g(Y))=X")) == 5
    assert size(E("a=b")) == 2
    assert variables(E("f(Y,g(X))=h(Z,Y)")) == ["Y", "X", "Z"]
    assert variables(E("a=b")) == []


def test_is_instance_on_hand_cases():
    assert is_instance(E("f(g(a),g(a))=g(a)"), E("f(X,X)=X"))
    assert not is_instance(E("f(g(a),b)=g(a)"), E("f(X,X)=X"))
    assert is_instance(E("X=f(X,X)"), E("f(Y,Y)=Y"))          # read either way round
    assert is_instance(E("f(Z,Z)=Z"), E("f(X,X)=X"))          # a variable filled with a variable
    assert is_instance(E("f(X,X)=X"), E("f(X,Y)=X"))          # Y filled with X
    assert not is_instance(E("f(X,Y)=X"), E("f(X,X)=X"))      # the more general is not an instance
    assert is_instance(E("f(a,a)=a"), E("f(X,Y)=X"))
    assert not is_instance(E("g(a)=a"), E("f(X)=X"))
    assert not is_instance(E("f(a,b)=b"), E("f(X,Y)=X"))


def test_an_instance_needs_the_same_value_for_a_repeated_variable():
    assert not is_instance(E("f(a,b)=a"), E("f(X,X)=X"))
    assert is_instance(E("f(a,b)=a"), E("f(X,Y)=X"))


def test_key_up_to_variables_ignores_variable_names_and_side_order_only():
    assert key_up_to_variables(E("f(X,Y)=g(Y)")) == key_up_to_variables(E("g(B)=f(A,B)"))
    assert key_up_to_variables(E("f(X,Y)=g(Y)")) != key_up_to_variables(E("f(X,Y)=g(X)"))
    assert key_up_to_variables(E("f(X)=X")) != key_up_to_variables(E("g(X)=X"))   # symbols are not renamed


def test_key_of_renamed_axiom_sets():
    renamed = ["times(inv2(Y),Y)=one", "times(A,times(B,C))=times(times(A,B),C)", "times(one,X)=X"]
    assert key([E(t) for t in GROUP]) == key([E(t) for t in renamed])
    right_identity = ["mult(mult(X,Y),Z)=mult(X,mult(Y,Z))", "mult(X,e)=X", "mult(inv(X),X)=e"]
    assert key([E(t) for t in GROUP]) != key([E(t) for t in right_identity])


def test_key_with_a_swap_of_two_symbols_of_the_same_kind():
    assert key([E("f(a)=b")]) == key([E("f(b)=a")])                       # swapping a and b is a renaming
    assert key([E("f(a)=b"), E("g(a)=a")]) != key([E("f(b)=a"), E("g(a)=a")])   # here it is not
    assert key([E("f(X,g(X))=h(X)"), E("h(X)=g(X)")]) == key([E("f(X,h(X))=g(X)"), E("g(X)=h(X)")])


def test_key_does_not_rename_across_arities():
    assert key([E("f(a)=a")]) != key([E("f(a,a)=a")])
    assert key([E("f(X)=a")]) != key([E("a=b")])


def test_key_reads_a_list_as_a_set():
    assert key([E("f(X)=X"), E("g(X)=X")]) == key([E("g(Y)=Y"), E("f(X)=X"), E("X=f(X)")])


def test_key_with_a_goal_ties_the_goal_to_the_same_renaming():
    axioms = [E("p(a)=a"), E("q(b)=b")]
    assert key(axioms, E("p(c)=c")) == key(axioms, E("q(c)=c"))   # swap p, q and a, b
    axioms = [E("p(a)=a"), E("q(a)=b")]
    assert key(axioms, E("p(c)=c")) != key(axioms, E("q(c)=c"))
    assert key([E("f(X)=X")], E("a=b")) != key([E("f(X)=X"), E("a=b")])


def test_symbol_renaming_turns_one_set_into_the_other():
    source = [E(t) for t in GROUP]
    target = [E("times(inv2(Y),Y)=one"), E("times(A,times(B,C))=times(times(A,B),C)"), E("times(one,X)=X")]
    names = symbol_renaming(source, target)
    assert names == {"mult": "times", "e": "one", "inv": "inv2"}
    assert {key_up_to_variables(rename_symbols(e, names)) for e in source} == {key_up_to_variables(e) for e in target}
    assert symbol_renaming(source, [E("f(X)=X")]) is None


def test_symmetric_sets_are_quick_and_exact():
    names = "abcdhijkmn"
    pairs = [E(f"g({x},{y})=o") for x in names for y in names if x != y]
    shuffled = [E(f"g({names[(i * 3) % 10]},{names[(j * 3) % 10]})=o") for i in range(10) for j in range(10) if i != j]
    assert key(pairs) == key(shuffled)
    cycle = [E(f"g({x},{y})=o") for x, y in zip(names, names[1:] + names[0])]
    two_cycles = [E(f"g({x},{y})=o") for x, y in zip(names, "bcdhaijkmn"[:5] + "jkmni")]
    assert key(cycle) != key(two_cycles)


def test_universal_form_turns_fresh_constants_into_variables():
    axioms = [E("mult(e,X)=X")]
    assert key_up_to_variables(universal_form(E("mult(a,mult(b,e))=mult(e,a)"), axioms)) == \
        key_up_to_variables(E("mult(X,mult(Y,e))=mult(e,X)"))
    # a variable in a denied goal (rare in TPTP) stays a variable
    assert write_equation(universal_form(E("mult(a,Z)=e"), axioms)) == "mult(X0,Z)=e"


def test_a_symbol_used_with_two_arities_stops_loudly():
    from tptp_count.renaming import RenamingError
    with pytest.raises(RenamingError):
        key([E("f(a)=a"), E("f(a,a)=a")])


def _variable_variant(equation, rng):
    """The same equation with its variables renamed and, half the time, its sides swapped."""
    mapping = {v: f"V{rng.randrange(10**6)}" for v in variables(equation)}
    renamed = (substitute(equation[0], mapping), substitute(equation[1], mapping))
    return renamed if rng.random() < 0.5 else (renamed[1], renamed[0])


def _renamed_copy(equations, rng):
    """The same set with symbols and variables renamed, shuffled, and some sides swapped."""
    names = sorted({s for e in equations for s in symbols(e)})
    new_names = {s: f"q{i}_{s[:2]}" for i, s in enumerate(rng.sample(names, len(names)))}
    copy = [_variable_variant(rename_symbols(e, new_names), rng) for e in equations]
    rng.shuffle(copy)
    return copy


def test_key_on_renamed_copies_of_the_pilots_axiom_sets():
    rng = random.Random(7)
    sets = {tuple(call["axioms"]) for call in read_jsonl_gz("pilot_calls.jsonl.gz")}
    assert len(sets) >= 20
    for texts in sorted(sets)[:30]:
        equations = [E(t) for t in texts]
        assert key(equations) == key(_renamed_copy(equations, rng))
        unique = {key_up_to_variables(e): e for e in equations}
        if len(unique) > 1:
            assert key(list(unique.values())[1:]) != key(equations)


@pytest.fixture(scope="module")
def pilot_equations():
    return read_jsonl_gz("pilot_equations.jsonl.gz")


def test_agreement_with_the_pilot_on_1000_equations(pilot_equations):
    terms = pilot_code()
    assert len(pilot_equations) == 1000
    rng = random.Random(11)
    ours, theirs = {}, {}
    for row in pilot_equations:
        equation, other = E(row["equation"]), E(row["other"])
        assert size(equation) == row["size"]
        assert variables(equation) == row["variables"]
        assert is_instance(equation, other) == row["instance_of_other"]
        assert terms.canon_eq_str(terms.parse_eq(row["equation"])) == row["pilot_key"]
        for candidate in (equation, _variable_variant(equation, rng)):
            pilot_key = terms.canon_eq_str(terms.parse_eq(write_equation(candidate)))
            ours.setdefault(key_up_to_variables(candidate), set()).add(pilot_key)
            theirs.setdefault(pilot_key, set()).add(key_up_to_variables(candidate))
    # the two keys split the equations and their variants the same way
    assert all(len(found) == 1 for found in ours.values())
    assert all(len(found) == 1 for found in theirs.values())
    assert len(ours) < 2000


def test_set_key_agrees_with_the_pilot_where_the_pilots_is_exact(pilot_equations):
    exact = [row for row in pilot_equations if row["pilot_set_key_exact"]]
    assert len(exact) > 900
    ours = {}
    for row in exact:
        ours.setdefault(key([E(row["equation"])]), set()).add(row["pilot_set_key"])
    pilots = {}
    for row in exact:
        pilots.setdefault(row["pilot_set_key"], set()).add(key([E(row["equation"])]))
    assert all(len(found) == 1 for found in ours.values())
    assert all(len(found) == 1 for found in pilots.values())
    assert len(ours) < len(exact)   # some equations are renamings of others, so the check is not empty


def _edges(pairs):
    return [E(f"p({x},{y})=p({y},{x})") for x, y in pairs]


def test_a_tie_where_a_later_tied_symbol_must_be_tried():
    """A ring of six constants beside two rings of three: every constant has the same colour after refinement
    (each is in two equations of the same shape), but one in the ring of six cannot stand in for one in a ring of
    three. In the first copy the first constant by name is in the ring of six, in the second it is in a ring of
    three, so the two copies get the same key only if the search tries more than the first tied symbol."""
    six, three, other_three = "abcdef", "ghi", "jkl"
    first = _edges(zip(six, six[1:] + six[0])) + _edges(zip(three, three[1:] + three[0])) \
        + _edges(zip(other_three, other_three[1:] + other_three[0]))
    rename = dict(zip("abcdefghijkl", "ghijklabcdef"))    # the ring of six now uses g..l, the rings of three a..f
    second = [rename_symbols(equation, rename) for equation in first]
    assert min(symbols(second[0])) != "a" and "a" in {s for e in second[6:9] for s in symbols(e)}
    assert key(first) == key(second)
    assert key(first) != key(_edges(zip("abcdef", "bcdefa")) + _edges(zip("ghijkl", "hijklg")))   # two rings of six
