"""Talking to the model server: the exact shape of every request, retries, and reading the replies.

The server speaks the OpenAI chat format, as vLLM does. There is one request per answer: the question, with
thinking on and the server's own thinking budget (vLLM's `thinking_token_budget`). When the thinking reaches
the budget, the server itself writes the end-of-thinking text it was started with (`--reasoning-config`,
built here by `reasoning_config`), which carries the stop sentence, and the model goes on to its answer in the
same reply. This path meets a real server for the first time in the run's first answers.
"""
import http.client
import json
import time
import urllib.error
import urllib.request

# The sentence that closes thinking cut short by the budget. The Qwen one is the sentence Qwen's makers give for
# cutting thinking short in the documentation of the earlier Qwen3 models; it is not stated for every version
# (the card of the version run here does not mention one). A model whose makers publish none gets the neutral one.
STOP_SENTENCES = {
    "qwen": "Considering the limited time by the user, I have to give the solution based on the thinking directly now.",
    "neutral": "I have run out of time to think, so I will now give my answer based on the thinking so far.",
}
THINK_START = "<think>"
THINK_END = "</think>"


def end_of_thinking_text(stop_sentence):
    """What the server writes when the thinking budget runs out: the layout of Qwen's documentation, ending at
    the end-of-thinking marker (the model writes the blank line and its answer after it)."""
    return "\n\n" + stop_sentence + "\n" + THINK_END


def reasoning_config(stop_sentence):
    """The JSON for the server's `--reasoning-config`, so the server writes exactly the text the run records."""
    return json.dumps({"reasoning_start_str": THINK_START, "reasoning_end_str": end_of_thinking_text(stop_sentence)})


# Failures of the request or of the reply, not of this code: only these are retried, then recorded. Anything
# else (a mistake in our own code) stops the run, because retrying it would only repeat the mistake.
REQUEST_ERRORS = (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError,
                  json.JSONDecodeError)


class RequestFailed(Exception):
    pass


class BadReply(Exception):
    """The server answered, but not in the expected shape."""


def question_request(model_name, messages, thinking_allowance, answer_allowance, sampling, seed):
    """The one request for an answer: the question with thinking on, the server's thinking budget set to the
    thinking allowance, and room for the answer on top. Whether the end-of-thinking text the server writes
    counts toward `max_tokens` is not documented; if it does, the answer has that many tokens less."""
    return {"model": model_name, "messages": messages, "thinking_token_budget": thinking_allowance,
            "max_tokens": thinking_allowance + answer_allowance, "seed": seed,
            "chat_template_kwargs": {"enable_thinking": True}, "return_token_ids": True, **sampling}


def read_reply(reply):
    """The parts of a chat reply this run keeps: thinking, answer, finish reason, completion token ids (or
    None), completion tokens, prompt token ids (or None), and the raw completion text if the server gives one
    (or None). Raises BadReply if the reply lacks what every chat reply must have."""
    try:
        choice = reply["choices"][0]
        message = choice["message"]
        completion_tokens = reply["usage"]["completion_tokens"]
    except (KeyError, IndexError, TypeError) as error:
        raise BadReply(f"reply without choices, message or usage: {error!r}") from error
    thinking = message.get("reasoning_content") or message.get("reasoning") or ""   # the name differs by version
    return {"thinking": thinking, "answer": message.get("content") or "", "finish_reason": choice.get("finish_reason"),
            "token_ids": choice.get("token_ids"), "completion_tokens": completion_tokens,
            "prompt_token_ids": reply.get("prompt_token_ids"), "text": choice.get("text")}


class ModelServer:
    """A chat server at `base_url` (without /v1). Each request is tried `attempts` times before giving up, and
    each try may take `timeout` seconds."""

    def __init__(self, base_url, model_name, api_key=None, attempts=3, wait_seconds=10.0, timeout=900.0):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.attempts = attempts
        self.wait_seconds = wait_seconds
        self.timeout = timeout

    def post(self, path, payload):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        errors = []
        for attempt in range(self.attempts):
            try:
                request = urllib.request.Request(self.base_url + path, data=json.dumps(payload).encode(), headers=headers)
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read())
            except REQUEST_ERRORS as error:
                errors.append(repr(error))
                if attempt + 1 < self.attempts:
                    time.sleep(self.wait_seconds)
        raise RequestFailed(f"{path} failed {self.attempts} times: {errors}")

    def chat(self, request):
        return self.post("/v1/chat/completions", request)

    def token_ids(self, text):
        """`text` in the model's own tokens (vLLM's /tokenize)."""
        reply = self.post("/tokenize", {"model": self.model_name, "prompt": text, "add_special_tokens": False})
        return reply.get("tokens") or []

    def count_tokens(self, text):
        reply = self.post("/tokenize", {"model": self.model_name, "prompt": text, "add_special_tokens": False})
        return reply["count"]
