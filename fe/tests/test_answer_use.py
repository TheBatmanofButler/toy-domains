"""Tests of scoring.py's figures on how the model's answers were used: shares of failed, unreadable, not
available, forced and cut-off answers, the thinking tokens the model wrote itself, and the most problems the
tokens could hold."""
import pytest
from made_up import NOT_AVAILABLE, OPTIONS, move_text

from fe_ladder import scoring


def answer(text, failed=False, forced=False, thinking=1000, used=1100, cut_off_readable=False):
    """A forced answer has the server's end text (20 tokens) in its thinking tokens, beside the `thinking`
    before it."""
    return {"problem_id": "p", "failed": failed, "answer_text": text, "forced": forced,
            "thinking_tokens": thinking and thinking + 20 * forced, "thinking_tokens_before_end_text": thinking,
            "tokens_used": used, "cut_off_but_readable": cut_off_readable}


def test_answer_use_counts_failed_answers_apart():
    answers = [answer(None, failed=True, thinking=None, used=0),
               answer("no idea", forced=True, thinking=8000, used=8100),
               answer(move_text(6), thinking=2000, used=2100, cut_off_readable=True),
               answer(move_text(0), thinking=3000, used=3100)]
    assert scoring.answer_use(answers) == {"answers": 4, "failed_share": 0.25, "unreadable_share": 0.25,
                                           "forced_share": 0.25, "cut_off_but_readable_share": 0.25,
                                           "thinking_tokens_mean": pytest.approx(13000 / 3),
                                           "tokens_used_mean": pytest.approx(13300 / 3)}
    use = scoring.answer_use(answers[:1])
    assert use["thinking_tokens_mean"] is None and use["tokens_used_mean"] is None
    # One answer without exact thinking tokens makes the exact mean unknown; tokens used are still counted.
    assert scoring.answer_use([answer(move_text(6)), answer(move_text(0), thinking=None)])["thinking_tokens_mean"] is None


def test_a_readable_move_that_is_not_available_is_counted_apart_from_unreadable_ones():
    problems = {"p": {"id": "p", "options": OPTIONS, "right_moves": [0]}}
    answers = [answer(NOT_AVAILABLE), answer("no idea"), answer(move_text(0)), answer(move_text(5))]
    use = scoring.answer_use(answers, problems)
    assert use["not_available_share"] == 0.25 and use["unreadable_share"] == 0.25
    assert "not_available_share" not in scoring.answer_use(answers)


def test_the_thinking_figure_is_the_models_own_thinking():
    # A forced answer counts the 8,000 before the server's end text, not its 8,020; an unforced one all of its
    # thinking, even with a sentence of its own at the end. A record without the count before the end text
    # (saved before it was kept) gives the count it has.
    assert scoring.own_thinking_tokens(answer(move_text(6), forced=True, thinking=8000)) == 8000
    unforced = dict(answer(move_text(6), thinking=3020), thinking_tokens_before_end_text=3000)
    assert scoring.own_thinking_tokens(unforced) == 3020
    old = {"forced": True, "thinking_tokens": 8020}
    assert scoring.own_thinking_tokens(old) == 8020


def test_budget_figures():
    assert scoring.most_identities_written(tokens_used=3000, tokens_per_identity=60) == 50
