"""Tests of question.py: the saved text for one real problem, the plan's wording, and nothing in the text that
names a fact or an article or marks the held-back option."""
import json
import re

from conftest import FIXTURES

from mizar_ladder.question import NOTATION, RULE, build_question

# Every article name the fixed problem's facts come from, and the article part of any coded symbol left as it is.
ARTICLE_NAME = re.compile(r"\b(tarski|xboole_0|xboole_1|zfmisc_1|boole|enumset1)\b")


def fixed_problem():
    return json.loads((FIXTURES / "fixed_problem.json").read_text())


def test_text_for_a_fixed_problem_equals_the_saved_copy():
    assert build_question(fixed_problem()) == (FIXTURES / "question_for_fixed_problem.txt").read_text()


def test_the_last_paragraph_is_worded_as_planned():
    # Copied from mizar_plan.md, section "The model".
    assert RULE == ("Exactly one of these facts is cited in the author's proof of the theorem, together with the "
                    "given facts. Give its number. Answer with `FACT: <number>`.")
    text = build_question(fixed_problem())
    assert text.startswith(NOTATION + "\n\n") and text.endswith("\n\n" + RULE)


def test_the_layout_numbers_given_facts_and_options():
    problem = fixed_problem()
    lines = build_question(problem).splitlines()
    given = [line for line in lines if re.match(r"G\d+\. ", line)]
    options = [line for line in lines if re.match(r"\d+\. ", line)]
    assert [line.split(".")[0] for line in given] == [f"G{n}" for n in range(1, len(problem["given"]) + 1)]
    assert [int(line.split(".")[0]) for line in options] == list(range(1, 31))
    assert options[problem["held_back"] - 1] == f"{problem['held_back']}. " + problem["options"][problem["held_back"] - 1]["statement"]


def test_no_fact_name_no_article_name_and_nothing_marks_the_held_back_option():
    problem = fixed_problem()
    text = build_question(problem)
    names = [problem["theorem"]] + [g["name"] for g in problem["given"]] + [o["name"] for o in problem["options"]]
    assert not [name for name in names if name in text]
    assert not ARTICLE_NAME.search(text) and problem["article"] not in text
    # Every option is written the same way: its line is its number and its statement, nothing more.
    for n, option in enumerate(problem["options"], 1):
        assert f"\n{n}. {option['statement']}\n" in text + "\n"
    # The held-back number is not in the text beyond its own option line, and the text is the same whichever
    # option is held back.
    assert build_question(dict(problem, held_back=1)) == text


def test_an_article_name_only_inside_a_symbol_with_no_mizar_name(made_up):
    # The made-up test problem of t3_xboole_0 shows the constants c<n>_basic_0 in its options: coded symbols
    # with no Mizar name, kept as they are. Outside them no article's name is in the text.
    from mizar_ladder.problems import Builder
    builder = Builder(made_up, 7)
    problem = builder.problem(builder.classify("t3_xboole_0"), "test-0001")
    text = build_question(problem)
    names = made_up.mizar_names()
    unnamed = set(re.findall(r"\b[a-z][A-Za-z0-9_]*_[A-Za-z0-9_]+\b", text)) - set(names)
    assert "c10_basic_0" in unnamed and len(unnamed) >= 25        # one constant per theorem of basic_0 shown
    outside = re.sub(r"\b(" + "|".join(map(re.escape, unnamed)) + r")\b", " ", text)
    for article_name in made_up.articles():
        assert article_name not in outside
    assert "basic_0" in text
    for name in [problem["theorem"]] + [g["name"] for g in problem["given"]] + [o["name"] for o in problem["options"]]:
        assert name not in text
