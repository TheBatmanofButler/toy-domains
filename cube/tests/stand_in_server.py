"""A stand-in for the model server, for tests: a real local HTTP server that answers by script.

The test gives a function `respond(path, request)` returning (status, reply). Every request is kept in
`requests`, so a test can check exactly what was sent. A chat request without `thinking_token_budget` is
refused (status 400) whatever `respond` would say, as a server would have nothing to enforce. Also here:
a respond function answering by script (the replies are in stand_in_replies.py), a set of states whose right
turns are known, the settings the model-run tests use, and a fixture that starts stand-in servers and closes
them after the test."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cube_ladder.cube import SOLVED, TURNS, apply_turns
from cube_ladder.model_server import STOP_SENTENCES
from cube_ladder.question import colours
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


def cube_colours_in(request):
    """The sticker string (colour letters) shown in the question of a chat request."""
    question = request["messages"][1]["content"]
    return question.split("read row by row as in the net):\n")[1].split("\n")[0]


def scripted(kinds, right_turn_of):
    """A respond function. `kinds[colours]` says how to answer the cube with those colours: "right", "wrong" or
    "unreadable" (short thinking that ended by itself), or one of stand_in_replies.REPLIES, each giving the
    right turn: "out_of_thinking" (forced at the allowance), "cut_off_readable" (cut off inside an answer that
    already has the right turn), "not_enforced" (cut off with no end of thinking at all, and no turn), and the
    rest named there. `right_turn_of[colours]` names one right and one wrong turn."""
    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        colours = cube_colours_in(request)
        right, wrong = right_turn_of[colours]
        kind = kinds[colours]
        if kind in REPLIES:
            return 200, REPLIES[kind](f"MOVE: {right}")
        content = {"right": f"MOVE: {right}", "wrong": f"MOVE: {wrong}", "unreadable": "I cannot tell."}[kind]
        return 200, chat_reply(content, answer_tokens=10 + request["seed"] % 7)
    return respond


def make_states(kinds, distances=(2,)):
    """One state per kind, with the respond function that answers each by its kind. Each state is one turn from
    solved, so its right turn is known; its distance label is taken in turn from `distances` (the label only
    decides the order of asking here)."""
    states, kind_of, turns_of = [], {}, {}
    for n, kind in enumerate(kinds):
        turn = TURNS[n]
        cube = apply_turns(SOLVED, [turn])
        right = turn[0] + {"": "'", "'": "", "2": "2"}[turn[1:]]
        distance = distances[n % len(distances)]
        states.append({"id": f"test-{distance:02d}-{n + 1:04d}", "cube": cube, "distance": distance,
                       "right_turns": [right]})
        kind_of[colours(cube)] = kind
        turns_of[colours(cube)] = (right, "B2" if right != "B2" else "U")
    return states, scripted(kind_of, turns_of)


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
