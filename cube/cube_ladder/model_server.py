"""Talking to the model server: the exact shape of every request, retries, and reading the replies.

The server speaks the OpenAI chat format, as vLLM does. Two requests are used: the question with thinking on,
and, when the thinking allowance runs out, a continuation of the same assistant turn whose thinking has been
closed with a stop sentence. The continuation's shape rests on vLLM's `continue_final_message` and on the
model's chat template; it has not met a real server yet and must be confirmed in the run's first answers.
"""
import http.client
import json
import time
import urllib.error
import urllib.request

# The sentence that closes cut-off thinking. Qwen's makers insert this one when a thinking budget runs out
# (to be confirmed in this model version's documentation); a model with no published way gets the neutral one.
STOP_SENTENCES = {
    "qwen": "Considering the limited time by the user, I have to give the solution based on the thinking directly now.",
    "neutral": "I have run out of time to think, so I will now give my answer based on the thinking so far.",
}

# Failures of the request or of the reply, not of this code: only these are retried, then recorded. Anything
# else (a mistake in our own code) stops the run, because retrying it would only repeat the mistake.
REQUEST_ERRORS = (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError,
                  json.JSONDecodeError)


class RequestFailed(Exception):
    pass


class BadReply(Exception):
    """The server answered, but not in the expected shape."""


def question_request(model_name, messages, max_tokens, sampling, seed):
    """The first request: the question, with thinking on."""
    return {"model": model_name, "messages": messages, "max_tokens": max_tokens, "seed": seed,
            "chat_template_kwargs": {"enable_thinking": True}, "return_token_ids": True, **sampling}


def continuation_request(model_name, messages, thinking, stop_sentence, max_tokens, sampling, seed):
    """The request that closes cut-off thinking and lets the model carry on into its answer, in the same
    assistant turn (no new message from the user). Returns (request, the assistant text it continues).

    The last message is the assistant's own turn so far: its thinking inside <think> ... </think>, with the
    stop sentence added at the end. `continue_final_message` (with `add_generation_prompt` off) tells vLLM to
    render the chat template and then cut the prompt at the end of that text instead of closing the turn, so
    the model's next tokens continue it. The template is expected to keep the thinking of this last turn
    (Qwen's template keeps it for turns after the last user message) and the prompt then ends with
    "</think>"; the model writes the blank line and its answer. Unverified without the real server: that
    this vLLM version accepts these two fields; that the template renders the turn so the text is found
    (vLLM compares it with surrounding spaces stripped); and in which reply field the answer comes back
    (the reasoning parser may label it as thinking, so the caller reads either)."""
    assistant_text = "<think>\n" + thinking.strip() + "\n\n" + stop_sentence + "\n</think>\n\n"
    request = {"model": model_name, "messages": messages + [{"role": "assistant", "content": assistant_text}],
               "add_generation_prompt": False, "continue_final_message": True, "max_tokens": max_tokens,
               "seed": seed, "chat_template_kwargs": {"enable_thinking": True}, "return_token_ids": True, **sampling}
    return request, assistant_text


def read_reply(reply):
    """(thinking, answer, finish reason, completion token ids or None, completion tokens, prompt token ids or
    None) from a chat reply. Raises BadReply if the reply lacks what every chat reply must have."""
    try:
        choice = reply["choices"][0]
        message = choice["message"]
        completion_tokens = reply["usage"]["completion_tokens"]
    except (KeyError, IndexError, TypeError) as error:
        raise BadReply(f"reply without choices, message or usage: {error!r}") from error
    thinking = message.get("reasoning_content") or message.get("reasoning") or ""   # the name differs by version
    return (thinking, message.get("content") or "", choice.get("finish_reason"), choice.get("token_ids"),
            completion_tokens, reply.get("prompt_token_ids"))


class ModelServer:
    """A chat server at `base_url` (without /v1). Each request is tried `attempts` times before giving up."""

    def __init__(self, base_url, model_name, api_key=None, attempts=3, wait_seconds=10.0, timeout=1800.0):
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
