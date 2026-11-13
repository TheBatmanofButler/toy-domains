"""A stand-in for the model server, for tests: a real local HTTP server that answers by script.

The test gives a function `respond(path, request)` returning (status, reply). Every request is kept in
`requests`, so a test can check exactly what was sent."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class StandInServer:
    def __init__(self, respond):
        self.respond = respond
        self.requests = []
        self.headers = []
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stand_in.requests.append((self.path, request))
                stand_in.headers.append(dict(self.headers))
                status, reply = stand_in.respond(self.path, request)
                body = json.dumps(reply).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


THINK_END = 151668   # the stand-in's id for the token "</think>"


def tokenize(request):
    if request["prompt"] == "</think>":
        return 200, {"count": 1, "tokens": [THINK_END]}
    return 200, {"count": len(request["prompt"].split()) + 10, "tokens": list(range(len(request["prompt"].split()) + 10))}


def cube_colours_in(request):
    """The sticker string (colour letters) shown in the question of a chat request."""
    question = request["messages"][1]["content"]
    return question.split("read row by row as in the net):\n")[1].split("\n")[0]


def is_continuation(request):
    return request.get("continue_final_message") is True


def chat_reply(content, reasoning="Let me think.", finish_reason="stop", thinking_tokens=90, answer_tokens=10,
               closed=True):
    """A chat reply whose token ids are `thinking_tokens` ids, the end-of-thinking id if `closed`, then
    `answer_tokens` ids."""
    ids = [1] * thinking_tokens + ([THINK_END] if closed else []) + [2] * answer_tokens
    return {"choices": [{"message": {"role": "assistant", "content": content, "reasoning_content": reasoning},
                         "finish_reason": finish_reason, "token_ids": ids}],
            "usage": {"prompt_tokens": 50, "completion_tokens": len(ids)}, "prompt_token_ids": list(range(50))}


def ran_out(content=""):
    """A reply cut off by the allowance: 8,200 tokens of unfinished thinking (or thinking, then `content`)."""
    if content:
        return chat_reply(content, reasoning="Hmm " * 50, finish_reason="length", thinking_tokens=8150,
                          answer_tokens=49)
    return chat_reply("", reasoning="Hmm " * 50, finish_reason="length", thinking_tokens=8200, answer_tokens=0,
                      closed=False)


def scripted(kinds, right_turn_of):
    """A respond function. `kinds[colours]` says how to answer the cube with those colours: "right", "wrong",
    "unreadable", "out_of_thinking" (runs out, then gives a right turn when continued), or "cut_off_readable"
    (runs out after already writing a right turn). `right_turn_of[colours]` names one right and one wrong turn."""
    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        colours = cube_colours_in(request)
        right, wrong = right_turn_of[colours]
        kind = kinds[colours]
        if kind == "out_of_thinking":
            if is_continuation(request):
                return 200, chat_reply(f"MOVE: {right}", reasoning=None, thinking_tokens=0, answer_tokens=4,
                                       closed=False)
            return 200, ran_out()
        if kind == "cut_off_readable":
            return 200, ran_out(f"MOVE: {right}")
        content = {"right": f"MOVE: {right}", "wrong": f"MOVE: {wrong}", "unreadable": "I cannot tell."}[kind]
        return 200, chat_reply(content, answer_tokens=10 + request["seed"] % 7)
    return respond
