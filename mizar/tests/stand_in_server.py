"""A stand-in for the model server, for tests: a real local HTTP server that answers by script.

The test gives a function `respond(path, request)` returning (status, reply). Every request is kept in
`requests`, so a test can check exactly what was sent. A chat request without `thinking_token_budget` is
refused (status 400) whatever `respond` would say, as a server would have nothing to enforce. Also here:
a respond function answering by script (the replies are in stand_in_replies.py), a set of problems whose right
options are known, the settings the model-run tests use, and a fixture that starts stand-in servers and closes
them after the test."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mizar_ladder.model_server import STOP_SENTENCES
from stand_in_replies import REPLIES, chat_reply, tokenize

SETTINGS = {"sampling": {"temperature": 0.6, "top_p": 0.95}, "source": "the model's documentation (test value)",
            "stop_sentence": STOP_SENTENCES["qwen"], "thinking_allowance": 8000, "answer_allowance": 1000}


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
                if self.path == "/v1/chat/completions" and "thinking_token_budget" not in request:
                    status, reply = 400, {"error": "no thinking_token_budget"}
                else:
                    status, reply = stand_in.respond(self.path, request)
                body = json.dumps(reply).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass     # the client stopped waiting (a test of a server that hangs past the timeout)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def theorem_in(request):
    """The theorem's statement shown in the question of a chat request."""
    question = request["messages"][1]["content"]
    return question.split("Theorem:\n")[1].split("\n")[0]


def scripted(kinds, right_option_of):
    """A respond function. `kinds[statement]` says how to answer the problem whose theorem has that statement:
    "right", "wrong" or "unreadable" (short thinking that ended by itself), or one of stand_in_replies.REPLIES,
    each giving the right option: "out_of_thinking" (forced at the allowance), "cut_off_readable" (cut off
    inside an answer that already has the right option), "not_enforced" (cut off with no end of thinking at
    all, and no option), and the rest named there. `right_option_of[statement]` names one right and one wrong
    option."""
    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        statement = theorem_in(request)
        right, wrong = right_option_of[statement]
        kind = kinds[statement]
        if kind in REPLIES:
            return 200, REPLIES[kind](f"FACT: {right}")
        content = {"right": f"FACT: {right}", "wrong": f"FACT: {wrong}", "unreadable": "I cannot tell."}[kind]
        return 200, chat_reply(content, answer_tokens=10 + request["seed"] % 7)
    return respond


def made_up_problem(n, held_back):
    """A test problem whose theorem's statement names its number, with two given facts and 30 options."""
    return {"id": f"test-{n:04d}", "theorem": f"t{n}_made_up", "article": "made_up",
            "statement": f"(! [A] : r{n}_made_up(A))",
            "given": [{"name": "t900_made_up", "statement": "(! [A] : r900_made_up(A))"},
                      {"name": "t901_made_up", "statement": "(! [A] : r901_made_up(A))"}],
            "options": [{"name": f"t{1000 + k}_made_up", "statement": f"(! [A] : k{k}_made_up(A)=A)"}
                        for k in range(1, 31)],
            "held_back": held_back, "cited_count": 3, "group": "topology", "seed": 1}


def make_problems(kinds):
    """One problem per kind, with the respond function that answers each by its kind. Problem n holds back
    option n (counting round from 1 to 30), so its right option is known; the wrong one is the next."""
    problems, kind_of, options_of = [], {}, {}
    for n, kind in enumerate(kinds, 1):
        held_back = (n - 1) % 30 + 1
        problem = made_up_problem(n, held_back)
        problems.append(problem)
        kind_of[problem["statement"]] = kind
        options_of[problem["statement"]] = (held_back, held_back % 30 + 1)
    return problems, scripted(kind_of, options_of)


@pytest.fixture
def stand_in():
    """`stand_in(respond)` starts a stand-in server; all are closed after the test."""
    servers = []

    def start(respond):
        servers.append(StandInServer(respond))
        return servers[-1]
    yield start
    for server in servers:
        server.close()
