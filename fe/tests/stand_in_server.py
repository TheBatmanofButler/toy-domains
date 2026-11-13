"""A stand-in for the model server, for tests: a real local HTTP server that answers by script.

The test gives a function `respond(path, request)` returning (status, reply). Every request is kept in
`requests`, so a test can check exactly what was sent. A chat request without `thinking_token_budget` is
refused (status 400) whatever `respond` would say, as a server would have nothing to enforce. Also here:
a respond function answering by script (the replies are in stand_in_replies.py), a set of problems whose right
moves are known, the settings the model-run tests use, and a fixture that starts stand-in servers and closes
them after the test."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import record
from small_problems import small_problems

from fe_ladder.identity_text import write_identity
from fe_ladder.model_server import STOP_SENTENCES
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


def goal_in(request):
    """The goal shown in the question of a chat request."""
    question = request["messages"][1]["content"]
    return question.split("Goal: prove the identity ")[1].split("\n")[0]


def move_text(move):
    return f"MOVE: ({move[0]}) {move[1]}"


def right_move_of(problem):
    """The first move of the problem's first right option."""
    return tuple(problem["options"][problem["right_moves"][0]]["moves"][0])


def wrong_move_of(problem):
    """The first move of the problem's first option that is not right."""
    return tuple(next(o["moves"][0] for n, o in enumerate(problem["options"]) if n not in problem["right_moves"]))


def scripted(kinds, problem_of):
    """A respond function. `kinds[goal]` says how to answer the problem with that goal: "right", "wrong" or
    "unreadable" (short thinking that ended by itself), or one of stand_in_replies.REPLIES, each giving the
    right move: "out_of_thinking" (forced at the allowance), "cut_off_readable" (cut off inside an answer that
    already has the right move), "not_enforced" (cut off with no end of thinking at all, and no move), and the
    rest named there. `problem_of[goal]` is the problem, whose right and wrong moves are known."""
    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        goal = goal_in(request)
        right, wrong = right_move_of(problem_of[goal]), wrong_move_of(problem_of[goal])
        kind = kinds[goal]
        if kind in REPLIES:
            return 200, REPLIES[kind](move_text(right))
        content = {"right": move_text(right), "wrong": move_text(wrong), "unreadable": "I cannot tell."}[kind]
        return 200, chat_reply(content, answer_tokens=10 + request["seed"] % 7)
    return respond


def _small_records(how_many=24):
    """Different small problems of depth 1 to 3, each with at least one option that is not right."""
    found, goals = [], set()
    for n, (equation, goal) in enumerate(small_problems(200, seed=12)):
        r = record(write_identity(equation), write_identity(goal), f"small-{n}", most_moves=3)
        if r["depth"] and len(r["right_moves"]) < len(r["options"]) and r["goal"] not in goals:
            goals.add(r["goal"])
            found.append(r)
        if len(found) == how_many:
            return found
    raise AssertionError("too few small problems")


SMALL = _small_records()


def make_problems(kinds, depths=(2,)):
    """One problem per kind, with the respond function that answers each by its kind. Each is a small problem
    whose right moves are known; its depth label is taken in turn from `depths` (the label only decides the
    order of asking here)."""
    problems, kind_of, problem_of = [], {}, {}
    for n, kind in enumerate(kinds):
        depth = depths[n % len(depths)]
        problem = dict(SMALL[n], id=f"test-{depth}-{n + 1:04d}", depth=depth)
        problems.append(problem)
        kind_of[problem["goal"]] = kind
        problem_of[problem["goal"]] = problem
    return problems, scripted(kind_of, problem_of)


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
