"""Tests of thinking_end.py on hand-made replies: where the end text shows, the thinking tokens before it, and
whether that is at the allowance, with every boundary worked by hand (allowance 8,000, tolerance 8)."""
from mizar_ladder.model_server import STOP_SENTENCES
from mizar_ladder.thinking_end import (ALLOWANCE_TOLERANCE, fits_allowance, how_thinking_ended, run_start,
                                      split_token_count, stop_sentence_found_in, tokens_before_end_text)

SENTENCE = STOP_SENTENCES["qwen"]
END = 9                       # the marker's id here
END_TEXT = [7, 8, END]        # a made-up end text of 3 ids


def reply(thinking="Hmm.", ids=None, text=None):
    return {"thinking": thinking, "token_ids": ids, "text": text}


def test_the_tolerance_either_side_of_the_allowance():
    assert ALLOWANCE_TOLERANCE == 8
    # No end text: 7,992 to 8,008 are at the allowance; 7,991 and 8,009 are not.
    assert fits_allowance(8000, 8000, 0) == (True, False)
    assert fits_allowance(7992, 8000, 0) == (True, False) and fits_allowance(8008, 8000, 0) == (True, False)
    assert fits_allowance(7991, 8000, 0) == (False, None) and fits_allowance(8009, 8000, 0) == (False, None)
    assert fits_allowance(None, 8000, 0) == (None, None)


def test_an_end_text_inside_the_budget_is_allowed_for_on_the_low_side_only():
    # An end text of 20 tokens: short by up to 20 + 8 is at the allowance with the end text inside the
    # budget (7,972 to 7,991); 7,971 is not. The high side does not widen.
    assert fits_allowance(7980, 8000, 20) == (True, True)
    assert fits_allowance(7972, 8000, 20) == (True, True) and fits_allowance(7991, 8000, 20) == (True, True)
    assert fits_allowance(7992, 8000, 20) == (True, False)
    assert fits_allowance(7971, 8000, 20) == (False, None) and fits_allowance(8009, 8000, 20) == (False, None)


def test_a_run_is_found_wherever_it_is_including_at_the_very_end():
    assert run_start([1, 7, 8, END, 2], END_TEXT) == 1
    assert run_start([1, 1, 7, 8, END], END_TEXT) == 2            # the last ids of the list
    assert run_start([7, 8, END], END_TEXT) == 0                  # the whole list
    assert run_start([1, 7, 8, 1, END], END_TEXT) is None         # broken
    assert run_start([1, 2], []) is None and run_start([8, END], END_TEXT) is None


def test_where_the_end_text_shows():
    ids = [1] * 5 + END_TEXT + [2]
    assert stop_sentence_found_in(reply("Hmm.\n\n" + SENTENCE + "\n  ", ids), SENTENCE, END_TEXT) == ["reasoning",
                                                                                                       "token_ids"]
    # The sentence in the middle of the thinking, and its ids not followed by the marker: nowhere.
    middle = reply("Hmm.\n\n" + SENTENCE + "\nBut wait.", [1, 7, 8, 1, END, 2])
    assert stop_sentence_found_in(middle, SENTENCE, END_TEXT) == []
    # Only the raw text, with the sentence just before the marker.
    raw = reply("Hmm.", [1, END, 2], text="<think>Hmm.\n\n" + SENTENCE + "\n</think>\n\nFACT: 1")
    assert stop_sentence_found_in(raw, SENTENCE, END_TEXT) == ["text"]
    assert stop_sentence_found_in(reply("Hmm.", None, text=SENTENCE + " and on"), SENTENCE, None) == []
    # No ids from the server, or no end-text ids: only the reasoning can show it.
    assert stop_sentence_found_in(reply(SENTENCE, None), SENTENCE, END_TEXT) == ["reasoning"]
    assert stop_sentence_found_in(reply("Hmm.", ids), SENTENCE, None) == []


def test_thinking_tokens_before_the_end_text():
    ids = [1] * 5 + END_TEXT + [2]
    assert tokens_before_end_text(ids, ["reasoning", "token_ids"], 7, END_TEXT) == 5        # ids before the run
    assert tokens_before_end_text(ids, ["reasoning"], 7, END_TEXT) == 4                     # 7 less 3
    assert tokens_before_end_text(ids, [], 7, END_TEXT) == 7                                # all of them
    assert tokens_before_end_text(None, ["reasoning"], None, END_TEXT) is None
    assert split_token_count([1, 1, END, 2], END) == (2, 1) and split_token_count([1, 1], END) == (2, 0)
    assert split_token_count([1], None) == (None, None)


def test_forced_needs_the_end_text_at_the_allowance():
    at = reply("Hmm.\n\n" + SENTENCE + "\n", [1] * 8000 + END_TEXT + [2] * 4)
    assert how_thinking_ended(at, SENTENCE, END, END_TEXT, 8000) == {
        "thinking_tokens": 8002, "answer_tokens": 4, "stop_sentence_found_in": ["reasoning", "token_ids"],
        "thinking_tokens_before_end_text": 8000, "at_allowance": True, "end_text_inside_budget": False,
        "forced": True}
    short = reply(SENTENCE, [1] * 3000 + END_TEXT + [2] * 4)        # the model's own sentence, well short
    ended = how_thinking_ended(short, SENTENCE, END, END_TEXT, 8000)
    assert not ended["forced"] and ended["at_allowance"] is False and ended["end_text_inside_budget"] is None
    # Thinking ending by itself 5 under the allowance is at it, but nothing closed it: not forced.
    ended = how_thinking_ended(reply("Hmm.", [1] * 7995 + [END, 2]), SENTENCE, END, END_TEXT, 8000)
    assert ended["at_allowance"] and not ended["forced"] and ended["end_text_inside_budget"] is None
    # Thinking tokens that cannot be counted: the end text found is all there is (the check says so).
    ended = how_thinking_ended(reply(SENTENCE, None), SENTENCE, END, END_TEXT, 8000)
    assert ended["forced"] and ended["at_allowance"] is None and ended["thinking_tokens_before_end_text"] is None
    assert ended["end_text_inside_budget"] is None
    ended = how_thinking_ended(reply(SENTENCE, [1, END]), SENTENCE, None, None, 8000)
    assert ended["forced"] and ended["stop_sentence_found_in"] == ["reasoning"] and ended["thinking_tokens"] is None
