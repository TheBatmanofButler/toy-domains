"""The stand-in server's tokenizer and its scripted chat replies, for tests.

The tokenizer gives each word its own id, made from the word, so different sentences give different ids and a
lookup for the wrong sentence is seen. A text ending with "</think>" gets the marker's id last; "</think>"
alone is that one id. The Qwen end-of-thinking text is 19 words and the marker: 20 ids, 19 before the marker.
Any other text is counted as its words + 10 and given ids 0, 1, 2, ... (the cube counts in the check).

Every reply's token ids are thinking ids (1), then the end text's ids or the marker alone, then answer ids (2).
"""
import zlib

from cube_ladder.model_server import STOP_SENTENCES, THINK_END as THINK_END_TEXT, end_of_thinking_text

THINK_END = 151668   # the stand-in's id for the token "</think>"
QWEN_SENTENCE = STOP_SENTENCES["qwen"]
NEUTRAL_SENTENCE = STOP_SENTENCES["neutral"]


def word_ids(text):
    return [1000 + zlib.crc32(word.encode()) % 100000 for word in text.split()]


def tokens_of(text):
    if text.endswith(THINK_END_TEXT):
        return word_ids(text[:-len(THINK_END_TEXT)]) + [THINK_END]
    return list(range(len(text.split()) + 10))


def tokenize(request):
    tokens = tokens_of(request["prompt"])
    return 200, {"count": len(tokens), "tokens": tokens}


END_TEXT_IDS = tokens_of(end_of_thinking_text(QWEN_SENTENCE))             # 20 ids
NEUTRAL_END_TEXT_IDS = tokens_of(end_of_thinking_text(NEUTRAL_SENTENCE))  # 21 words: 22 ids


def chat_reply(content, reasoning="Let me think.", finish_reason="stop", thinking_tokens=90, answer_tokens=10,
               closed=True, end_text=False):
    """A chat reply whose token ids are `thinking_tokens` ids, then the end text's ids if `end_text` (True for
    the Qwen end text, or a list of ids) or else the marker alone if `closed`, then `answer_tokens` ids."""
    ending = (END_TEXT_IDS if end_text is True else end_text) if end_text else [THINK_END] if closed else []
    ids = [1] * thinking_tokens + ending + [2] * answer_tokens
    return {"choices": [{"message": {"role": "assistant", "content": content, "reasoning_content": reasoning},
                         "finish_reason": finish_reason, "token_ids": ids}],
            "usage": {"prompt_tokens": 50, "completion_tokens": len(ids)}, "prompt_token_ids": list(range(50))}


def forced_reply(content, before=8000, answer_tokens=4, sentence=QWEN_SENTENCE, finish_reason="stop"):
    """Thinking closed by the end text after `before` tokens: the reasoning ends with the stop sentence. At
    the default, 8,000 thinking ids, the end text's 19 and the marker, then 4 answer ids: 8,019 thinking tokens,
    8,024 in all. `before` is also how a server closing early (6,000), a server counting its end text inside
    the budget (7,980), or a model writing the sentence itself after short thinking (same ids) is scripted."""
    ids = END_TEXT_IDS if sentence == QWEN_SENTENCE else tokens_of(end_of_thinking_text(sentence))
    return chat_reply(content, reasoning="Hmm " * 50 + "\n\n" + sentence + "\n", thinking_tokens=before,
                      answer_tokens=answer_tokens, end_text=ids, finish_reason=finish_reason)


def sentence_mid_thinking(content):
    """The model writes the stop sentence after 1,000 thinking tokens and goes on thinking for 2,000 more:
    1,000 + 19 + 2,000 = 3,019 thinking tokens, then the marker and 10 answer ids."""
    reasoning = "Hmm " * 20 + "\n\n" + QWEN_SENTENCE + "\nBut wait, let me check the corners again."
    reply = chat_reply(content, reasoning=reasoning, thinking_tokens=0)
    reply["choices"][0]["token_ids"] = [1] * 1000 + END_TEXT_IDS[:-1] + [1] * 2000 + [THINK_END] + [2] * 10
    reply["usage"]["completion_tokens"] = 3030
    return reply


def ends_by_itself(content, thinking_tokens):
    """Thinking that ends by itself (the marker alone) after `thinking_tokens`, then 10 answer ids."""
    return chat_reply(content, thinking_tokens=thinking_tokens)


def cut_off_in_answer(content):
    """Thinking that ended by itself after 7,000 tokens, then an answer cut off at the total limit: 7,000
    thinking tokens, the end-of-thinking token and 1,999 answer tokens, 9,000 in all."""
    return chat_reply(content + "\nand to check that once more, the cube", finish_reason="length",
                      thinking_tokens=7000, answer_tokens=1999)


def not_enforced():
    """A server not enforcing the budget: 9,000 tokens of thinking, never closed, cut off at the total limit."""
    return chat_reply("", reasoning="Hmm " * 50, finish_reason="length", thinking_tokens=9000, answer_tokens=0,
                      closed=False)


# What each scripted kind gives, from the right turn's answer text. "unreadable", "right" and "wrong" are
# plain short thinking and are made in stand_in_server.scripted.
REPLIES = {
    "out_of_thinking": forced_reply,                                         # forced at 8,000
    "forced_inside_budget": lambda c: forced_reply(c, before=8000 - 20),    # end text inside the budget
    "writes_stop_sentence": lambda c: forced_reply(c, before=3000),         # the model's own, after 3,000
    "closed_early": lambda c: forced_reply(c, before=6000),                 # a server closing at 6,000
    "sentence_mid_thinking": sentence_mid_thinking,
    "ends_5_under": lambda c: ends_by_itself(c, 7995),
    "ends_50_under": lambda c: ends_by_itself(c, 7950),
    "other_finish_reason": lambda c: chat_reply(c, finish_reason="abort"),
    "cut_off_readable": cut_off_in_answer,
    "not_enforced": lambda c: not_enforced(),
}
