"""Tests of how the run's check measures speed (run_check.answers_per_hour): the number of answers over the time
from the first request starting (`finished_at` less `seconds`) to the last answer finishing. Figures by hand."""
import pytest
from test_run_check import good_answers, run

from mizar_ladder.run_check import answers_per_hour, projected_run
from mizar_ladder.scoring import ScoringError


def timed(start, seconds, n=0):
    """An answer's record as far as speed goes: it started at `start` and took `seconds`."""
    return {"problem_id": f"test-{n:04d}", "try": 1, "finished_at": start + seconds, "seconds": seconds}


def sent_together():
    """The first 100 answers as a real server gave them: all sent together, answer n starting at
    0.001 (99 - n) s (all within 0.1 s of each other) and taking 189.6 + 2.0 n / 99 s (189.6 to 191.6 s).
    Answer 99 starts first, at 0, and finishes last, at 191.6 s; answer 0 finishes first, at 189.699 s."""
    return [timed(0.001 * (99 - n), 189.6 + 2.0 * n / 99, n) for n in range(100)]


def test_answers_sent_together_are_measured_from_the_first_start():
    answers = sent_together()
    assert min(a["seconds"] for a in answers) == pytest.approx(189.6)
    assert max(a["seconds"] for a in answers) == pytest.approx(191.6)
    # 100 answers in 191.6 s: 100 x 3,600 / 191.6 = 1,878.91 an hour. (From the first finish to the last, 99
    # answers in 1.901 s, it would read 187,480 an hour.)
    speed = answers_per_hour(answers)
    assert speed == pytest.approx(1878.914, abs=0.001)
    # 8,500 answers: 8,500 / 1,878.914 = 8,500 x 191.6 / 360,000 = 4.5239 hours; at $7.99 an hour,
    # 4.5239 x 7.99 = $36.15.
    projected = projected_run(speed, 8500, 7.99)
    assert projected["hours"] == pytest.approx(4.52389, abs=1e-5)
    assert projected["cost"] == pytest.approx(36.1459, abs=1e-4)


def test_the_check_uses_the_answers_it_checks_and_their_start():
    answers = [dict(a, finished_at=t["finished_at"], seconds=t["seconds"])
               for a, t in zip(good_answers(), sent_together())]
    result = run(answers, price_per_hour=7.99)
    assert result["passed"] and result["answers_per_hour"] == pytest.approx(1878.914, abs=0.001)
    assert result["projected_cost"] == pytest.approx(36.1459, abs=1e-4)
    # A ceiling of $30 is now below the projected cost, so the cost check fails.
    result = run(answers, price_per_hour=7.99, cost_ceiling=30.0)
    assert not result["passed"] and result["problems"] == ["projected cost $36 is above $30"]


def test_answers_one_after_another():
    # 5 answers of 9 s each, back to back from 0: 5 answers in 45 s = 400 an hour, in any order.
    answers = [timed(9 * n, 9, n) for n in (2, 0, 4, 1, 3)]
    assert answers_per_hour(answers) == pytest.approx(400)


def test_two_answers():
    # One starts at 0 and takes 30 s; the other starts at 10 and takes 50 s, finishing at 60: 2 in 60 s.
    assert answers_per_hour([timed(0, 30), timed(10, 50, 1)]) == pytest.approx(120)


def test_a_single_answer_is_one_answer_over_its_own_duration():
    # One answer that took 90 s: 3,600 / 90 = 40 an hour.
    assert answers_per_hour([timed(1000, 90)]) == pytest.approx(40)


def test_a_pause_between_two_starts_makes_the_run_look_slower_never_faster():
    # Two answers of 36 s back to back (2 in 72 s: 100 an hour), then the run is stopped and started again an
    # hour after the first start, and a third answer takes 36 s: 3 in 3,636 s = 2.970 an hour.
    before = [timed(0, 36), timed(36, 36, 1)]
    assert answers_per_hour(before) == pytest.approx(100)
    assert answers_per_hour(before + [timed(3600, 36, 2)]) == pytest.approx(3 * 3600 / 3636)
    # Without the pause the same three answers read 3 in 108 s = 100 an hour.
    assert answers_per_hour(before + [timed(72, 36, 2)]) == pytest.approx(100)


def test_answers_saved_without_seconds_give_a_plain_error():
    old = {"problem_id": "test-0001", "try": 2, "finished_at": 50.0}
    with pytest.raises(ScoringError, match=r"1 answers were saved without how long they took .*test-0001 try 2"):
        answers_per_hour([timed(0, 30), old])
    answers = good_answers()
    del answers[7]["seconds"]
    with pytest.raises(ScoringError, match="speed cannot be measured"):
        run(answers)


def test_no_answers_or_no_time_cannot_be_measured():
    with pytest.raises(ScoringError, match="no answers"):
        answers_per_hour([])
    with pytest.raises(ScoringError, match="took no time"):
        answers_per_hour([timed(5, 0), timed(5, 0, 1)])
