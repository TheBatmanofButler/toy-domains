"""How a reply's thinking ended: where the server's end-of-thinking text shows, how many thinking tokens came
before it, and whether that was at the thinking allowance.

The server closes the thinking itself when it reaches the budget, by writing the end-of-thinking text it was
started with. A model can also write the stop sentence on its own, and a server can close the thinking
somewhere other than the allowance. So an answer counts as forced only when the end text is there and it came
at the allowance: the end text alone, or the count alone, is not enough.
"""
import re

from mizar_ladder.model_server import THINK_END

# How far, either side, the thinking before the end text may be from the allowance and still count as at it.
# The server and this code may count the opening marker and the boundary token differently, by a token or two;
# 8 leaves room for that and no more, so thinking that ends by itself tens of tokens short is not taken for
# thinking the server closed.
ALLOWANCE_TOLERANCE = 8


def split_token_count(token_ids, think_end_id):
    """(thinking tokens, answer tokens) from the completion's token ids: the tokens before and after the
    end-of-thinking token, which itself counts as neither. The thinking tokens include any end text the server
    wrote. If the thinking never ended, every token is thinking. (None, None) if the server gave no ids or the
    model has no single end-of-thinking token."""
    if token_ids is None or think_end_id is None:
        return None, None
    if think_end_id not in token_ids:
        return len(token_ids), 0
    end = token_ids.index(think_end_id)
    return end, len(token_ids) - end - 1


def run_start(ids, run):
    """Where the list `run` first appears, in order and unbroken, in `ids` (it may end with the last id); None
    if it does not appear."""
    if run:
        for i in range(len(ids) - len(run) + 1):
            if ids[i:i + len(run)] == run:
                return i
    return None


def stop_sentence_found_in(reply, stop_sentence, end_text_ids):
    """Where in a reply (from model_server.read_reply) the end-of-thinking text shows: "reasoning" if the
    thinking, trailing white space removed, ends with the stop sentence; "text" if the raw completion text has
    the sentence just before the end-of-thinking marker; "token_ids" if the completion's ids hold the end
    text's ids unbroken. It is not documented whether the reasoning field keeps the sentence the server wrote,
    and vLLM's chat reply carries no raw text, so the token ids are the surest of the three (assuming the
    server writes the same ids as /tokenize gives for that text). A sentence in the middle of the thinking
    shows nowhere: the thinking went on after it."""
    places = []
    if reply["thinking"].rstrip().endswith(stop_sentence):
        places.append("reasoning")
    if reply["text"] and re.search(re.escape(stop_sentence) + r"\s*" + re.escape(THINK_END), reply["text"]):
        places.append("text")
    if reply["token_ids"] is not None and run_start(reply["token_ids"], end_text_ids or []) is not None:
        places.append("token_ids")
    return places


def tokens_before_end_text(token_ids, places, thinking_tokens, end_text_ids):
    """Thinking tokens before the end text: where the ids show it, the ids before its run; where only the
    reasoning or the raw text shows it, the thinking tokens less the end text's length; where it does not
    show, all the thinking tokens. None when thinking tokens cannot be counted."""
    if thinking_tokens is None:
        return None
    if "token_ids" in places:
        return run_start(token_ids, end_text_ids)
    if places:
        return thinking_tokens - len(end_text_ids)
    return thinking_tokens


def fits_allowance(tokens_before, allowance, end_text_length):
    """(at_allowance, end_text_inside_budget). At the allowance: within ALLOWANCE_TOLERANCE of it, either side
    (the end text counted outside the budget), or, when there is an end text, short of it by up to the end
    text's length plus the tolerance (the server making room for its end text inside the budget: whether it
    does is not documented). `end_text_length` is 0 when no end text was found. (None, None) if the count is
    unknown; the second is None too when the thinking is not at the allowance."""
    if tokens_before is None:
        return None, None
    if abs(tokens_before - allowance) <= ALLOWANCE_TOLERANCE:
        return True, False
    if end_text_length and allowance - end_text_length - ALLOWANCE_TOLERANCE <= tokens_before < allowance:
        return True, True
    return False, None


def how_thinking_ended(reply, stop_sentence, think_end_id, end_text_ids, allowance):
    """The record's fields on how the thinking ended, for a reply from model_server.read_reply asked with
    thinking allowance `allowance`. `forced` needs the end text found and at the allowance; if the thinking
    tokens cannot be counted, the end text found is all there is to go on (and the run's check says the counts
    are missing)."""
    thinking_tokens, answer_tokens = split_token_count(reply["token_ids"], think_end_id)
    places = stop_sentence_found_in(reply, stop_sentence, end_text_ids)
    before = tokens_before_end_text(reply["token_ids"], places, thinking_tokens, end_text_ids)
    at_allowance, inside = fits_allowance(before, allowance, len(end_text_ids or []) if places else 0)
    forced = bool(places) and (at_allowance is not False)
    return {"thinking_tokens": thinking_tokens, "answer_tokens": answer_tokens, "stop_sentence_found_in": places,
            "thinking_tokens_before_end_text": before, "at_allowance": at_allowance,
            "end_text_inside_budget": inside if forced else None, "forced": forced}
