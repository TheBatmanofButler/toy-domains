"""Tests of run_check.py: each of the four checks holds and fails on made-up answers, with the figures by hand."""
import pytest

from cube_ladder.run_check import answers_per_hour, check, projected_run, readable_share
from cube_ladder.scoring import ScoringError


def answer(n, text="MOVE: R", forced=False, thinking="I think.", failed=False, tokens=100):
    """Answer number n finishes at 36 n seconds, so 100 answers take 99 x 36 s: 100 per hour after the first."""
    return {"state_id": f"test-02-{n:04d}", "try": 1, "question": "q", "thinking": thinking, "answer_text": text,
            "forced": forced, "failed": failed, "generated_tokens": tokens, "thinking_tokens": tokens,
            "tokens_used": tokens, "cut_off_but_readable": False, "finished_at": 36.0 * n}


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
    # 99 answers in 99 x 36 s = 100 per hour; 8,500 answers take 85 hours, at $2 an hour $170.
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
    answers = [dict(a, forced=False) for a in good_answers()]
    result = run(answers)
    assert result["passed"] and result["forced_readable_share"] is None
    assert readable_share([]) is None


def test_too_many_unreadable_answers_fail():
    answers = [dict(a, answer_text="hmm") if 20 <= n < 36 else a for n, a in enumerate(good_answers())]
    result = run(answers)   # unreadable 2 forced + 16 unforced = 18 of 100
    assert not result["passed"] and "0.18 of answers unreadable" in result["problems"][-1]


def test_projected_cost_above_the_ceiling_fails():
    result = run(good_answers(), price_per_hour=4.0)   # 85 hours x $4 = $340
    assert not result["passed"] and "projected cost $340 is above $300" in result["problems"][0]


def test_speed_and_projection():
    assert projected_run(answers_per_hour=500, answers_needed=9000, price_per_hour=10) == {"hours": 18, "cost": 180}
    # 5 answers finishing at 0, 9, 18, 27 and 36 seconds: 4 answers in 36 s = 400 per hour.
    assert answers_per_hour([18, 0, 9, 36, 27]) == pytest.approx(400)
    with pytest.raises(ScoringError):
        answers_per_hour([5.0, 5.0])
