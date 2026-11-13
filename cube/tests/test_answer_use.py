"""Tests of scoring.py's figures on how the model's answers were used: shares of failed, unreadable, forced and
cut-off answers, the thinking tokens the model wrote itself, and the most cubes the tokens could hold."""
import pytest

from cube_ladder import scoring


def answer(text, failed=False, forced=False, thinking=1000, used=1100, cut_off_readable=False):
    """A forced answer has the server's end text (20 tokens) in its thinking tokens, beside the `thinking`
    before it."""
    return {"failed": failed, "answer_text": text, "forced": forced,
            "thinking_tokens": thinking and thinking + 20 * forced, "thinking_tokens_before_end_text": thinking,
            "tokens_used": used, "cut_off_but_readable": cut_off_readable}


def test_answer_use_counts_failed_answers_apart():
    answers = [answer(None, failed=True, thinking=None, used=0),
               answer("no idea", forced=True, thinking=8000, used=8100),
               answer("MOVE: R", thinking=2000, used=2100, cut_off_readable=True),
               answer("MOVE: U", thinking=3000, used=3100)]
    assert scoring.answer_use(answers) == {"answers": 4, "failed_share": 0.25, "unreadable_share": 0.25,
                                           "forced_share": 0.25, "cut_off_but_readable_share": 0.25,
                                           "thinking_tokens_mean": pytest.approx(13000 / 3),
                                           "answers_without_thinking_count": 0,
                                           "tokens_used_mean": pytest.approx(13300 / 3)}
    # A failed answer has no tokens at all; it is a failure, not an answer without a count.
    use = scoring.answer_use(answers[:1])
    assert use["thinking_tokens_mean"] is None and use["tokens_used_mean"] is None
    assert use["answers_without_thinking_count"] == 0


def test_the_thinking_mean_is_over_the_answers_with_a_count():
    # Three answers at a distance. One lacks a count: the mean is over the other two, (1000 + 4000) / 2 = 2500,
    # and the one is counted; tokens used are over all three, (1100 + 4100 + 2100) / 3. The forced one counts
    # its 4,000 before the end text.
    one_lacking = [answer("MOVE: R", thinking=1000, used=1100), answer("MOVE: U", forced=True, thinking=4000, used=4100),
                   answer("MOVE: F", thinking=None, used=2100)]
    use = scoring.answer_use(one_lacking)
    assert use["thinking_tokens_mean"] == 2500 and use["answers_without_thinking_count"] == 1
    assert use["tokens_used_mean"] == pytest.approx(7300 / 3)
    # All three lacking: no mean, and 3 counted.
    all_lacking = [answer(text, thinking=None) for text in ("MOVE: R", "MOVE: U", "MOVE: F")]
    use = scoring.answer_use(all_lacking)
    assert use["thinking_tokens_mean"] is None and use["answers_without_thinking_count"] == 3
    # None lacking, as in the run: (1000 + 4000 + 2000) / 3, and 0.
    none_lacking = one_lacking[:2] + [answer("MOVE: F", thinking=2000, used=2100)]
    use = scoring.answer_use(none_lacking)
    assert use["thinking_tokens_mean"] == pytest.approx(7000 / 3) and use["answers_without_thinking_count"] == 0


def test_the_thinking_figure_is_the_models_own_thinking():
    # A forced answer counts the 8,000 before the server's end text, not its 8,020; an unforced one all of its
    # thinking, even with a sentence of its own at the end. A record without the count before the end text
    # (saved before it was kept) gives the count it has.
    assert scoring.own_thinking_tokens(answer("MOVE: R", forced=True, thinking=8000)) == 8000
    unforced = dict(answer("MOVE: R", thinking=3020), thinking_tokens_before_end_text=3000)
    assert scoring.own_thinking_tokens(unforced) == 3020
    old = {"forced": True, "thinking_tokens": 8020}
    assert scoring.own_thinking_tokens(old) == 8020


def test_budget_figures():
    assert scoring.most_cubes_written(tokens_used=3000, tokens_per_cube=60) == 50
