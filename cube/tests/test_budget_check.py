"""Tests of run_check's check on the server's thinking budget, on the made-up answers of test_run_check.py: 20
forced at 8,000 (end text of 20 ids), 80 ending by themselves after 100 thinking tokens. Allowance 8,000,
tolerance 8, figures by hand."""
from test_run_check import good_answers, run


def with_answer(n, **fields):
    answers = good_answers()
    answers[n] = dict(answers[n], **fields)
    return answers


def misfits(answers):
    return run(answers)["budget_misfits"]


def test_thinking_past_the_allowance_with_no_end_text_does_not_fit():
    # 8,008 = allowance + tolerance does not fit; 8,007 does (thinking that ends by itself under that is healthy).
    result = run(with_answer(30, thinking_tokens=8008, thinking_tokens_before_end_text=8008))
    assert not result["passed"] and result["budget_check"] == "not as assumed"
    assert result["problems"] == ["the server's thinking budget is not behaving as assumed, or cannot be checked, on "
                                  "1 answers: ['test-02-0030 try 1: no end text, 8008 thinking tokens, allowance 8000']"]
    assert run(with_answer(30, thinking_tokens=8007, thinking_tokens_before_end_text=8007))["passed"]
    assert run(with_answer(30, thinking_tokens=7950, thinking_tokens_before_end_text=7950))["passed"]


def test_the_end_text_away_from_the_allowance_does_not_fit():
    # Forced answer 0 with its end text after 7,972 to 8,008 thinking tokens fits (7,972 is 8,000 less the
    # end text's 20 and the tolerance); 7,971 and 8,009 do not, nor does 6,000 (more than half the allowance).
    for before, fits in ((7971, False), (7972, True), (8008, True), (8009, False), (6000, False), (3000, False)):
        found = misfits(with_answer(0, thinking_tokens_before_end_text=before))
        assert found == ([] if fits else [f"test-02-0000 try 1: end text after {before} thinking tokens, "
                                          f"allowance 8000"]), before
    # The model writing the sentence itself at the end of short thinking: the same.
    answers = with_answer(50, stop_sentence_found_in=["reasoning", "token_ids"], thinking_tokens_before_end_text=81)
    assert misfits(answers) == ["test-02-0050 try 1: end text after 81 thinking tokens, allowance 8000"]


def test_each_answer_is_judged_by_the_allowance_it_was_asked_with():
    # Answers asked with 6,000: forced at 6,000 fits, though this start's allowance (the default) is 8,000.
    answers = [dict(a, settings={"thinking_allowance": 6000},
                    thinking_tokens_before_end_text=6000 if a["forced"] else 100) for a in good_answers()]
    result = run(answers)
    assert result["passed"] and result["thinking_allowances"] == [6000]
    # One of them thinking 7,000 with no end text is past its 6,000; 7,000 would be healthy under 8,000.
    answers[60] = dict(answers[60], thinking_tokens=7000, thinking_tokens_before_end_text=7000)
    assert misfits(answers) == ["test-02-0060 try 1: no end text, 7000 thinking tokens, allowance 6000"]
    answers[61] = dict(answers[61], settings={"thinking_allowance": 8000})
    assert run(answers)["thinking_allowances"] == [6000, 8000]


def test_thinking_tokens_that_cannot_be_counted_say_why():
    no_ids = with_answer(50, completion_token_ids=None, thinking_tokens=None, thinking_tokens_before_end_text=None)
    result = run(no_ids)
    assert not result["passed"] and result["budget_check"] == "not checked"
    assert result["budget_misfits"] == ["test-02-0050 try 1: thinking tokens cannot be counted (the server returned "
                                        "no token ids)"]
    no_marker = with_answer(50, think_end_token_id=None, thinking_tokens=None, thinking_tokens_before_end_text=None)
    assert misfits(no_marker) == ["test-02-0050 try 1: thinking tokens cannot be counted (the end-of-thinking marker "
                                  "is not a single token)"]
    # A failed answer has no token counts either: it fails as incomplete, not here.
    failed = with_answer(50, failed=True, completion_token_ids=None, thinking_tokens=None,
                         thinking_tokens_before_end_text=None)
    result = run(failed)
    assert result["budget_check"] == "as assumed" and "incomplete records" in result["problems"][0]


def test_at_most_10_are_named_and_all_are_counted():
    answers = [dict(a, thinking_tokens_before_end_text=10) if a["forced"] and n < 12 else a
               for n, a in enumerate(good_answers())]
    result = run(answers)
    assert result["budget_misfit_count"] == 12 and len(result["budget_misfits"]) == 10
    assert "on 12 answers" in result["problems"][0] and "test-02-0009 try 1: end text after 10" in result["problems"][0]
    assert "test-02-0010" not in result["problems"][0]


def test_answers_saved_without_the_new_fields_give_a_plain_message():
    answers = [{k: v for k, v in a.items() if k not in ("stop_sentence_found_in", "thinking_tokens_before_end_text",
                                                        "at_allowance", "end_text_inside_budget")}
               for a in good_answers()]
    result = run(answers)
    assert not result["passed"] and result["budget_check"] == "not checked"
    assert result["problems"] == ["budget not checked: the answers were saved without the fields this check reads "
                                  "(where the end text was found and the thinking tokens before it)"]
    assert result["end_text_inside_budget_count"] == 0 and result["end_text_outside_budget_count"] == 0
