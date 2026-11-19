"""Tests of renaming.py: hand-made statements through show_renamed and read_back; the code map; the words a
renamed question may hold; and the named-against-renamed figures on a hand-made case worked out by hand."""
import json

import pytest

from mizar_ladder import renaming, statements
from mizar_ladder.question import NOTATION, NOTATION_RENAMED, build_question

CODES = {"r1_tarski": "s00412", "k2_xboole_0": "s00007", "k1_xboole_0": "s00300", "v1_xboole_0": "s01000",
         "k1_numbers": "s00055"}


@pytest.mark.parametrize("statement, expected", [
    # A two-place predicate written between its arguments in the named text is written in front here.
    ("(! [A, B] : r1_tarski(A, B))", "(! [A, B] : s00412(A, B))"),
    # A symbol without arguments is its code alone.
    ("(! [A] : r1_tarski(k1_xboole_0, A))", "(! [A] : s00412(s00300, A))"),
    # Nested applications, `=`, the logic signs and a quantifier over several variables are kept.
    ("(! [A, B, C] : (v1_xboole_0(A) => k2_xboole_0(k2_xboole_0(A, B), C)=k2_xboole_0(B, k2_xboole_0(A, C))))",
     "(! [A, B, C] : (s01000(A) => s00007(s00007(A, B), C)=s00007(B, s00007(A, C))))"),
    # Numerals are kept as they are.
    ("(? [A] : (r1_tarski(1, A) & ~ (A = k1_numbers(2))))", "(? [A] : (s00412(1, A) & ~ (A = s00055(2))))"),
])
def test_statements_renamed_and_read_back(statement, expected):
    assert renaming.show_renamed(statement, CODES) == expected
    assert renaming.read_back(expected, CODES) == statement
    assert statements.canonical(renaming.read_back(expected, CODES)) == statements.canonical(statement)


def test_a_symbol_without_a_code_and_an_unknown_code_stop_loudly():
    with pytest.raises(renaming.RenamingError, match="without a code"):
        renaming.show_renamed("(! [A] : r2_hidden(A, A))", CODES)
    with pytest.raises(renaming.RenamingError, match="unknown code: s99999"):
        renaming.read_back("s99999(A)", CODES)


def test_the_code_map_is_fixed_for_a_seed_and_changes_with_it():
    symbols = ["r1_tarski", "k2_xboole_0", "k1_xboole_0", "v1_xboole_0", "k1_xboole_0"]
    seven = renaming.code_map(symbols, 7)
    assert seven == {"k2_xboole_0": "s00001", "r1_tarski": "s00002", "k1_xboole_0": "s00003", "v1_xboole_0": "s00004"}
    assert renaming.code_map(list(reversed(symbols)), 7) == seven              # not the order given
    assert renaming.code_map(symbols, 8) != seven
    assert all(len(code) == 6 and code[0] == "s" and code[1:].isdigit() for code in seven.values())


def test_two_symbols_with_one_mizar_name_get_two_codes():
    # Mizar names both "c="; each symbol still gets its own code.
    names = {"r1_tarski": "c=", "r1_xboole_0": "c="}
    codes = renaming.code_map(list(names), 1)
    assert len(set(codes.values())) == 2
    shown = [statements.show(f"{s}(A, B)", names) for s in names]
    assert shown[0] == shown[1] and renaming.show_renamed("r1_tarski(A, B)", codes) != renaming.show_renamed(
        "r1_xboole_0(A, B)", codes)


def test_too_many_symbols_are_refused(monkeypatch):
    monkeypatch.setattr(renaming, "LIMIT", 3)
    with pytest.raises(renaming.RenamingError, match="4 symbols, more than five digits can code"):
        renaming.code_map(["a", "b", "c", "d"], 7)


def test_a_code_that_is_already_a_name_or_word_is_refused():
    with pytest.raises(renaming.RenamingError, match="already names"):
        renaming.code_map(["a", "b"], 7, forbidden={"s00001", "x"})


def test_the_words_of_a_renamed_question():
    problem = {"statement": "(! [A] : s00412(A, s00300))", "renamed": True,
               "given": [{"statement": "s01000(B)"}, {"statement": "(? [C] : s00412(C, 1))"}],
               "options": [{"statement": f"s00007(A{n})"} for n in range(30)]}
    question = build_question(problem)
    assert question.startswith(NOTATION_RENAMED) and NOTATION_RENAMED != NOTATION
    assert NOTATION_RENAMED.endswith("with each symbol of the Mizar Mathematical Library replaced by a meaningless "
                                     "code, the same code wherever the symbol appears.")
    assert build_question(dict(problem, renamed=False)).startswith(NOTATION)
    variables = ["A", "B", "C"] + [f"A{n}" for n in range(30)]
    assert renaming.stray_words(question, CODES, variables, 2) == []
    assert renaming.stray_words(question.replace("s01000", "v1_xboole_0"), CODES, variables, 2) == ["v1_xboole_0"]
    assert renaming.stray_words(question, CODES, [v for v in variables if v != "C"], 2) == ["C"]
    assert renaming.stray_words(question, CODES, variables, 1) == ["G2"]


def test_the_map_file():
    found = json.loads(renaming.map_file({"b": "s00002", "a": "s00001"}, 7))
    assert found == {"seed": 7, "codes": {"a": "s00001", "b": "s00002"}}


# ---- named against renamed, worked by hand ----------------------------------------------------------------------
# Two problems in one row of each kind (2 to 3 cited, sets). Tries right, named: p1 T T T F F (.6), p2 T T F F F
# (.4); renamed: p1 T F F F T (.4), p2 none (0).
# Named: mean .5; per-problem values .6 and .4, sample standard deviation sqrt((.1^2 + .1^2) / 1) = .1414, standard
# error .1414 / sqrt(2) = .1. Renamed: mean .2; values .4 and 0, deviation sqrt((.2^2 + .2^2) / 1) = .2828, standard
# error .2. Drop: .6 - .4 = .2 on p1 and .4 - 0 = .4 on p2, mean .3; deviation sqrt((.1^2 + .1^2) / 1) = .1414,
# standard error .1. Paired tries (10): p1 (T,T) (T,F) (T,F) (F,F) (F,T), p2 (T,F) (T,F) (F,F) (F,F) (F,F): both 1,
# named only 4, renamed only 1, neither 4. Renamed try 2 of p1 is forced, with 1,200 thinking tokens of its own; every other
# renamed answer thinks 300 tokens and every named one 100: forced 0 and .1, thinking 100 and (9 x 300 + 1200) / 10
# = 390. The program "p" puts .5 on p1's right option and nothing on p2's: renamed minus p is -.1 and 0, mean
# -.05, standard error .05.
PROBLEMS = [{"id": f"p{n}", "held_back": 1, "cited_count": 2, "group": "sets, relations and functions"}
            for n in (1, 2)]
SETTINGS = {"thinking_allowance": 8000, "sampling": {"temperature": 0.6}}


def answers(rights, renamed):
    found = []
    for problem_id, row in rights.items():
        for t, right in enumerate(row, 1):
            forced = renamed and (problem_id, t) == ("p1", 2)
            found.append({"problem_id": problem_id, "try": t, "failed": False, "forced": forced,
                          "answer_text": f"FACT: {1 if right else 2}", "cut_off_but_readable": False,
                          "thinking_tokens": 8019 if forced else 300 if renamed else 100,
                          "thinking_tokens_before_end_text": 1200 if forced else None, "tokens_used": 500,
                          "model_version": "m@1",
                          "settings": dict(SETTINGS, renamed=True) if renamed else dict(SETTINGS)})
    return found


NAMED = answers({"p1": [1, 1, 1, 0, 0], "p2": [1, 1, 0, 0, 0]}, False)
RENAMED = answers({"p1": [1, 0, 0, 0, 1], "p2": [0, 0, 0, 0, 0]}, True)
PICKS = [{"problem_id": "p1", "program": "p", "weights": [0.5] + [0.5 / 29] * 29, "score": 0.5},
         {"problem_id": "p2", "program": "p", "weights": [0.0] + [1 / 29] * 29, "score": 0.0}]


def test_named_against_renamed_worked_by_hand():
    table = renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, RENAMED)
    assert list(table) == ["all problems", "2 to 3 cited", "sets, relations and functions"]
    for row in table.values():
        assert row["problems"] == 2 and row["tries_paired"] == 10
        assert row["model_named"] == pytest.approx(0.5) and row["model_named_standard_error"] == pytest.approx(0.1)
        assert row["model_renamed"] == pytest.approx(0.2) and row["model_renamed_standard_error"] == pytest.approx(0.2)
        assert row["drop"] == {"mean": pytest.approx(0.3), "standard_error": pytest.approx(0.1)}
        assert (row["both_right"], row["named_only"], row["renamed_only"], row["neither"]) == (0.1, 0.4, 0.1, 0.4)
        assert (row["forced_share_named"], row["forced_share_renamed"]) == (0, pytest.approx(0.1))
        assert (row["thinking_tokens_named"], row["thinking_tokens_renamed"]) == (100, pytest.approx(390))
        assert row["renamed_minus_program"] == {"p": {"mean": pytest.approx(-0.05),
                                                      "standard_error": pytest.approx(0.05)}}


@pytest.mark.parametrize("change, message", [
    (lambda named, renamed: renamed.pop(),
     "not for the named answers' problems and tries: missing \\[\\('p2', 5\\)\\]"),
    (lambda named, renamed: renamed.append(dict(renamed[0])), "not for the named answers' problems and tries"),
    (lambda named, renamed: renamed[3]["settings"].update(thinking_allowance=6000),
     "not asked under the same settings"),
    (lambda named, renamed: renamed[3].update(model_version="m@2"), "not asked under the same settings"),
    (lambda named, renamed: renamed[0]["settings"].pop("renamed"), "not marked renamed"),
    (lambda named, renamed: named[0]["settings"].update(renamed=True), "named answers hold renamed ones"),
])
def test_the_refusals(change, message):
    named, renamed = json.loads(json.dumps(NAMED)), json.loads(json.dumps(RENAMED))
    change(named, renamed)
    with pytest.raises(renaming.RenamingError, match=message):
        renaming.named_against_renamed(PROBLEMS, PICKS, named, renamed)


def test_two_allowances_worked_by_hand():
    # The same answers as above, read as the renamed run at the named allowance (NAMED's tries) and at another
    # (RENAMED's): .5 and .2 with standard errors .1 and .2; difference (other minus named allowance) -.2 on p1
    # and -.4 on p2: mean -.3, standard error .1; shares .1, .4, .1, .4; forced 0 and .1; thinking 100 and 390.
    table = renaming.two_allowances(PROBLEMS, NAMED, RENAMED)
    for row in table.values():
        assert (row["problems"], row["tries_paired"]) == (2, 10)
        assert row["at_named_allowance"] == pytest.approx(0.5)
        assert row["at_named_allowance_standard_error"] == pytest.approx(0.1)
        assert row["at_other_allowance"] == pytest.approx(0.2)
        assert row["at_other_allowance_standard_error"] == pytest.approx(0.2)
        assert row["difference"] == {"mean": pytest.approx(-0.3), "standard_error": pytest.approx(0.1)}
        assert (row["both_right"], row["named_allowance_only"], row["other_allowance_only"], row["neither"]) == (
            0.1, 0.4, 0.1, 0.4)
        assert (row["forced_share_named_allowance"], row["forced_share_other_allowance"]) == (0, pytest.approx(0.1))
        assert (row["thinking_tokens_named_allowance"], row["thinking_tokens_other_allowance"]) == (
            100, pytest.approx(390))


def test_another_allowance_may_differ_in_thinking_allowance_only():
    other = [dict(a, settings=dict(a["settings"], thinking_allowance=12000)) for a in RENAMED]
    with pytest.raises(renaming.RenamingError, match="apart from `renamed`\\): 2 different settings"):
        renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, other)
    table = renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, other, allowance=12000)
    assert table == renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, RENAMED)
    with pytest.raises(renaming.RenamingError, match="a thinking allowance of 9000 were asked with \\[12000\\]"):
        renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, other, allowance=9000)
    sampled = [dict(a, settings=dict(a["settings"], sampling={"temperature": 1.0})) for a in other]
    with pytest.raises(renaming.RenamingError, match="apart from `renamed` and `thinking_allowance`"):
        renaming.named_against_renamed(PROBLEMS, PICKS, NAMED, sampled, allowance=12000)
