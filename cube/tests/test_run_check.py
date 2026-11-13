"""Tests of run_check.py: each of the four checks holds and fails on made-up answers, with the figures by hand.
The check on the server's thinking budget is tested in test_budget_check.py, on the same answers."""
import pytest

from cube_ladder.run_check import check, projected_run, readable_share


def answer(n, text="MOVE: R", forced=False, thinking="I think.", failed=False, tokens=100):
    """Answer number n starts at 36 n seconds and takes 36 s, one after another, so 100 answers take 100 x 36 s
    from the first start to the last finish: 100 per hour.
    Unforced answers think 100 tokens; forced ones were closed at the allowance (see `as_forced`)."""
    return as_forced({"state_id": f"test-02-{n:04d}", "try": 1, "question": "q", "thinking": thinking,
                      "answer_text": text, "failed": failed, "generated_tokens": tokens, "tokens_used": tokens,
                      "cut_off_but_readable": False, "finished_at": 36.0 * (n + 1), "seconds": 36.0,
                      "settings": {"thinking_allowance": 8000},
                      "completion_token_ids": [1], "think_end_token_id": 9, "end_text_token_ids": [5] * 19 + [9]},
                     forced)


def as_forced(a, forced=True):
    """`a` forced as the server forces an answer (its end text of 20 ids after 8,000 thinking tokens: 8,019
    thinking tokens), or not forced (100 thinking tokens, ended by itself)."""
    if forced:
        return dict(a, forced=True, thinking_tokens=8019, thinking_tokens_before_end_text=8000,
                    stop_sentence_found_in=["reasoning", "token_ids"], at_allowance=True, end_text_inside_budget=False)
    return dict(a, forced=False, thinking_tokens=100, thinking_tokens_before_end_text=100, stop_sentence_found_in=[],
                at_allowance=False, end_text_inside_budget=None)


def good_answers():
    # 100 answers: 20 forced (18 readable: 0.90), 80 unforced (76 readable: 0.95). Unreadable 6 of 100.
    answers = [answer(n, forced=n < 20, text="MOVE: R" if (n >= 2 if n < 20 else n >= 24) else "hmm")
               for n in range(100)]
    return answers


def run(answers, **options):
    settings = dict(answers_needed=8500, price_per_hour=2.0, cost_ceiling=300.0)
    settings.update(options)
    return check(answers, **settings)


def test_good_answers_pass_with_figures_by_hand():
    result = run(good_answers())
    assert result["passed"] and result["problems"] == []
    assert result["forced_readable_share"] == pytest.approx(0.90) and result["unforced_readable_share"] == pytest.approx(0.95)
    assert result["unreadable_share"] == pytest.approx(0.06) and result["share_with_thinking"] == 1
    assert result["forced_comparison"] == "tested"
    assert result["forced_answers_compared"] == 20 and result["unforced_answers_compared"] == 80
    assert result["budget_check"] == "as assumed" and result["end_text_outside_budget_count"] == 20
    assert result["end_text_inside_budget_count"] == 0 and result["thinking_allowances"] == [8000]
    assert result["budget_misfits"] == [] and result["budget_misfit_count"] == 0
    # 100 answers in 100 x 36 s = 100 per hour; 8,500 answers take 85 hours, at $2 an hour $170.
    assert result["answers_per_hour"] == pytest.approx(100)
    assert result["projected_hours"] == pytest.approx(85) and result["projected_cost"] == pytest.approx(170)


def test_an_incomplete_or_failed_record_fails():
    answers = good_answers()
    answers[3]["answer_text"] = None
    answers[5]["failed"] = True
    result = run(answers)
    assert not result["passed"] and "test-02-0003 try 1" in result["problems"][0] and "test-02-0005" in result["problems"][0]


def test_thinking_empty_on_most_answers_fails():
    # Thinking must be there on most answers: more than half. Exactly half is not enough.
    answers = [dict(a, thinking="") if n < 50 else a for n, a in enumerate(good_answers())]
    result = run(answers)
    assert not result["passed"] and "thinking is empty on most answers" in result["problems"][0]
    answers = [dict(a, thinking="") if n < 49 else a for n, a in enumerate(good_answers())]
    assert run(answers)["passed"]


def test_forced_answers_much_less_readable_fail_and_the_margin_is_an_option():
    # 20 forced, 15 readable: 0.75, against 0.95 unforced: 0.20 apart.
    answers = [dict(a, answer_text="hmm") if n in range(2, 7) else a for n, a in enumerate(good_answers())]
    assert readable_share([a for a in answers if a["forced"]]) == pytest.approx(13 / 20)
    result = run(answers)
    assert not result["passed"] and "forced answers readable 0.65, unforced 0.95" in result["problems"][0]
    assert run(answers, readable_margin=0.35)["passed"]


def test_no_forced_answers_leaves_nothing_to_compare():
    answers = [as_forced(a, False) for a in good_answers()]
    result = run(answers)
    assert result["passed"] and result["forced_readable_share"] is None
    assert result["forced_comparison"] == "not tested" and result["forced_answers_compared"] == 0
    assert readable_share([]) is None


def forced_first(forced_count, readable_count):
    """good_answers() with the first `forced_count` answers forced, the first `readable_count` of them readable."""
    return [dict(as_forced(a, n < forced_count),
                 answer_text=("MOVE: R" if n < readable_count else "hmm") if n < forced_count else a["answer_text"])
            for n, a in enumerate(good_answers())]


def test_too_few_forced_or_unforced_answers_are_not_tested_and_the_run_carries_on():
    # 9 forced answers, 5 readable (0.56 against about 0.93): far apart, but too few to compare, and at least
    # half are readable, so it passes. (Fewer than half readable fails: see the next test.)
    answers = forced_first(9, 5)
    result = run(answers, unreadable_limit=0.5)
    assert result["passed"] and result["forced_comparison"] == "not tested"
    assert result["forced_answers_compared"] == 9 and result["unforced_answers_compared"] == 91
    assert result["forced_readable_share"] == pytest.approx(5 / 9) and result["fewest_to_compare"] == 10
    # 10 forced answers, none readable: 10 of each, so it is compared as before, and fails.
    answers = forced_first(9, 0)
    answers[9] = dict(as_forced(answers[9]), answer_text="hmm")
    result = run(answers, unreadable_limit=0.5)
    assert not result["passed"] and result["forced_comparison"] == "tested"
    assert result["problems"] == ["forced answers readable 0.00, unforced 0.96: more than 0.15 apart"]
    # The same holds the other way round: 9 unforced answers.
    flipped = [as_forced(a, n >= 9) for n, a in enumerate(good_answers())]
    result = run(flipped)
    assert result["forced_comparison"] == "not tested" and result["unforced_answers_compared"] == 9


def test_3_to_9_forced_answers_fewer_than_half_readable_fail_though_not_tested():
    # 9 forced, 4 readable: fails, and the comparison is still reported as not tested.
    result = run(forced_first(9, 4), unreadable_limit=0.5)
    assert not result["passed"] and result["forced_comparison"] == "not tested"
    assert result["problems"] == ["only 4 of 9 forced answers readable, fewer than half (too few forced answers "
                                  "to compare with the unforced ones, but too few readable to go on)"]
    assert result["fewest_forced_to_judge"] == 3
    # 9 forced, 5 readable: passes (the test above). 4 forced, 2 readable: exactly half, passes.
    assert run(forced_first(4, 2), unreadable_limit=0.5)["passed"]
    # 3 forced, 1 readable: fails.
    result = run(forced_first(3, 1), unreadable_limit=0.5)
    assert not result["passed"] and "only 1 of 3 forced answers readable" in result["problems"][0]
    # 2 forced, none readable: too few to judge, passes.
    result = run(forced_first(2, 0), unreadable_limit=0.5)
    assert result["passed"] and result["forced_comparison"] == "not tested"
    # The lower bound is an option: with it at 2, the same answers fail.
    assert not run(forced_first(2, 0), unreadable_limit=0.5, fewest_forced_to_judge=2)["passed"]


def test_too_many_unreadable_answers_fail():
    answers = [dict(a, answer_text="hmm") if 20 <= n < 36 else a for n, a in enumerate(good_answers())]
    result = run(answers)   # unreadable 2 forced + 16 unforced = 18 of 100
    assert not result["passed"] and "0.18 of answers unreadable" in result["problems"][-1]


def test_projected_cost_above_the_ceiling_fails():
    result = run(good_answers(), price_per_hour=4.0)   # 85 hours x $4 = $340
    assert not result["passed"] and "projected cost $340 is above $300" in result["problems"][0]


def test_projection():
    # The speed itself is tested in test_run_speed.py.
    assert projected_run(answers_per_hour=500, answers_needed=9000, price_per_hour=10) == {"hours": 18, "cost": 180}
