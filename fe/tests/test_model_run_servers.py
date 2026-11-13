"""Tests of model_run.py's order of asking and of a run spread over several stand-in servers."""
import json
import threading
from collections import Counter

from stand_in_server import SETTINGS, StandInServer, make_problems, stand_in  # noqa: F401

from fe_ladder import model_run
from fe_ladder.model_server import ModelServer


def made_up_problems(per_depth=300):
    """`per_depth` problems at each of the 4 depths 2 to 5 (only id and depth matter to the order)."""
    return [{"id": f"test-{d}-{n:04d}", "depth": d} for d in range(2, 6) for n in range(per_depth)]


def test_the_first_100_are_different_problems_spread_over_the_depths():
    order = model_run.order_of_asking(made_up_problems(), 5, run_seed=7)
    assert len(order) == 4 * 300 * 5 and len({(s["id"], t) for s, t in order}) == len(order)
    first = order[:100]
    assert len({s["id"] for s, _ in first}) == 100 and {t for _, t in first} == {1}
    # 100 = 25 rounds of 4: each depth 25 times.
    by_depth = Counter(s["depth"] for s, _ in first)
    assert by_depth == {d: 25 for d in range(2, 6)}
    assert [s["depth"] for s, _ in order[:8]] == [2, 3, 4, 5, 2, 3, 4, 5]
    # Every problem's first try comes before any second try.
    assert [t for _, t in order] == sorted(t for _, t in order)


def test_the_seed_sets_the_order_inside_each_depth():
    problems = made_up_problems()

    def at_depth(order, d):
        return [s["id"] for s, t in order if s["depth"] == d and t == 1]
    one, again = model_run.order_of_asking(problems, 5, 7), model_run.order_of_asking(problems[::-1], 5, 7)
    other = model_run.order_of_asking(problems, 5, 8)
    assert [(s["id"], t) for s, t in one] == [(s["id"], t) for s, t in again]   # nor does the file's order matter
    assert at_depth(one, 2) != at_depth(other, 2) and sorted(at_depth(one, 2)) == sorted(at_depth(other, 2))
    assert [s["depth"] for s, _ in one] == [s["depth"] for s, _ in other]   # only the order inside changes
    # The same order inside a depth for every try.
    assert at_depth(one, 5) == [s["id"] for s, t in one if s["depth"] == 5 and t == 3]


def test_depths_with_fewer_problems_drop_out_when_used_up():
    problems = [{"id": "a-1", "depth": 2}, {"id": "b-1", "depth": 3}, {"id": "b-2", "depth": 3}]
    order = model_run.order_of_asking(problems, 2, run_seed=1)
    assert [s["depth"] for s, _ in order] == [2, 3, 3, 2, 3, 3]
    assert model_run.order_of_asking([], 5, 1) == []


def run(problems, servers, path, workers=2, attempts=3, **options):
    clients = [ModelServer(s.base_url, "test-model", wait_seconds=0, attempts=attempts) for s in servers]
    return model_run.run(problems, clients, path, 5, SETTINGS, "test-model@abc123", run_seed=3, workers=workers,
                         log=lambda *_: None, **options)


def chats(server):
    return [request for path, request in server.requests if path == "/v1/chat/completions"]


def test_two_servers_each_get_half_and_every_record_names_its_server(stand_in, tmp_path):
    problems, respond = make_problems(["right", "wrong", "unreadable", "right"], depths=(2, 3))
    servers = [stand_in(respond), stand_in(respond)]
    run(problems, servers, tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert len(records) == 20 and len(chats(servers[0])) == len(chats(servers[1])) == 10
    assert Counter(r["server"] for r in records) == {servers[0].base_url: 10, servers[1].base_url: 10}
    # The record names the server that was really asked: its question was among that server's requests.
    for server in servers:
        asked = Counter((r["messages"][1]["content"], r["seed"]) for r in chats(server))
        assert asked == Counter((r["question"], r["request_seed"]) for r in records if r["server"] == server.base_url)
    # The token lookups (the end-of-thinking token and the end-of-thinking text) go to the first server only.
    assert [p for p, _ in servers[0].requests].count("/tokenize") == 2
    assert "/tokenize" not in [p for p, _ in servers[1].requests]


def test_restarting_with_a_different_number_of_servers_asks_nothing_twice(stand_in, tmp_path):
    problems, respond = make_problems(["right", "wrong", "out_of_thinking", "right"], depths=(2, 3))
    path = tmp_path / "answers.jsonl"
    one, two, three = stand_in(respond), [stand_in(respond) for _ in range(2)], [stand_in(respond) for _ in range(3)]
    assert len(run(problems, [one], path, limit=6)) == 6
    assert len(run(problems, two, path, limit=7)) == 7
    assert len(run(problems, three, path)) == 7
    assert run(problems, [one], path) == []
    records = model_run.read_saved(path)
    assert len({(r["problem_id"], r["try"]) for r in records}) == len(records) == 20
    # One request per (problem, try) over all six servers, forced answers included.
    asked = [r for s in [one, *two, *three] for r in chats(s)]
    assert len(asked) == 20 and sum(r["forced"] for r in records) == 5
    # What is left at each start is dealt out in turn: 6 to the one; 7 as 4 and 3; 7 as 3, 2 and 2.
    assert Counter(r["server"] for r in records) == Counter(
        [one.base_url] * 6 + [s.base_url for s in two] * 3 + [two[0].base_url] + [s.base_url for s in three] * 2
        + [three[0].base_url])


def test_restart_with_two_servers_holds_the_same_records_as_an_unbroken_run(stand_in, tmp_path):
    # Which server answers a (problem, try) can differ (what is left is dealt out afresh), and so can the order
    # of lines; everything else in the records is the same.
    problems, respond = make_problems(["right", "wrong", "unreadable", "out_of_thinking"], depths=(2, 3))
    servers = [stand_in(respond), stand_in(respond)]
    unbroken, stopped = tmp_path / "unbroken.jsonl", tmp_path / "stopped.jsonl"
    run(problems, servers, unbroken)
    run(problems, servers, stopped, limit=9)
    run(problems, servers, stopped)

    def records(path):
        return sorted(json.dumps({k: v for k, v in r.items() if k not in ("seconds", "finished_at", "server")},
                                 sort_keys=True) for r in model_run.read_saved(path))
    assert records(stopped) == records(unbroken) and len(records(stopped)) == 20


def test_one_dead_server_does_not_stop_the_other(stand_in, tmp_path):
    problems, respond = make_problems(["right", "wrong", "right", "wrong"], depths=(2, 3))
    alive, dead = stand_in(respond), StandInServer(respond)
    dead.close()                                  # nothing listens there: every request is refused
    run([*problems], [dead, alive], tmp_path / "answers.jsonl", attempts=2)
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    by_server = {url: [r for r in records if r["server"] == url] for url in (alive.base_url, dead.base_url)}
    assert len(records) == 20 and len(by_server[alive.base_url]) == len(by_server[dead.base_url]) == 10
    assert all(r["failed"] and "failed 2 times" in r["error"] for r in by_server[dead.base_url])
    assert not any(r["failed"] for r in by_server[alive.base_url]) and len(chats(alive)) == 10
    # The token lookup fell through to the server that answers, so token counts are still split.
    assert all(r["think_end_token_id"] is not None for r in records)
    # Asked again with --retry-failed, the failed ones are spread over the servers given this time.
    run(problems, [alive], tmp_path / "answers.jsonl", retry_failed=True)
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert len(records) == 20 and not any(r["failed"] for r in records) and len(chats(alive)) == 20


def test_workers_are_per_server_and_a_server_that_hangs_holds_only_its_own(stand_in, tmp_path):
    # The slow server holds every request until the fast one has answered all of its share. With a pool for
    # each server, it holds exactly --workers requests and the fast one goes on meanwhile; with one pool for
    # all, the slow server's requests take up the pool and nothing is released until the hold times out.
    problems, respond = make_problems(["right", "wrong", "right", "wrong"], depths=(2, 3))
    fast_done, lock = threading.Event(), threading.Lock()
    in_flight, most, timed_out, fast_answers = [0], [0], [], []

    def slow(path, request):
        if path == "/tokenize":
            return respond(path, request)
        with lock:
            in_flight[0] += 1
            most[0] = max(most[0], in_flight[0])
        timed_out.append(not fast_done.wait(timeout=3))
        with lock:
            in_flight[0] -= 1
        return respond(path, request)

    def fast(path, request):
        if path != "/tokenize":
            with lock:
                fast_answers.append(1)
                if len(fast_answers) == 10:
                    fast_done.set()
        return respond(path, request)
    run(problems, [stand_in(slow), stand_in(fast)], tmp_path / "answers.jsonl", workers=3)
    assert most[0] == 3 and not any(timed_out) and len(fast_answers) == 10
    assert len(model_run.read_saved(tmp_path / "answers.jsonl")) == 20
