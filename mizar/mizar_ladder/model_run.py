"""Asks the model about each test problem several times and saves every answer as it arrives.

Thinking is on, with an allowance of 8,000 tokens for thinking and, on top, 1,000 for the answer.
One request per answer: the server enforces the thinking allowance itself, closing the thinking with the stop
sentence when it runs out, and the model answers in the same reply; such a record is marked `forced` (see
thinking_end.py for what that takes). Every record keeps the exact question, thinking and answer, the token
ids if the server returns them, the model version, the settings and the server that answered. A request that
keeps failing is recorded as failed, never dropped. A stopped run can be started again, with more or fewer
servers: answers already saved are skipped.

Order of asking: the first try of every problem before the second try of any, the problems in an order set by the
run's seed, so the first answers (the ones the run checks itself on) are different problems.
"""
import json
import os
import random
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

from mizar_ladder.answers import read_option
from mizar_ladder.model_server import (THINK_END, BadReply, RequestFailed, end_of_thinking_text, question_request,
                                      read_reply)
from mizar_ladder.question import SYSTEM_TEXT, build_question
from mizar_ladder.thinking_end import how_thinking_ended

THINKING_ALLOWANCE = 8000
ANSWER_ALLOWANCE = 1000


def request_seed(run_seed, problem_id, try_number):
    """A fixed sampling seed for each (problem, try): a rerun sends exactly the same requests. The server may
    still answer differently (batching and hardware change the arithmetic), so answers are not reproducible."""
    return zlib.crc32(f"{run_seed}:{problem_id}:{try_number}".encode()) % 2**31


def order_of_asking(problems, tries, run_seed):
    """Every (problem, try) in the order they are asked. Try 1 of every problem comes first, then try 2, and so
    on. Within a try the problems are in a shuffle set by the run's seed, the same for every try; problems are
    sorted by id before the shuffle so the order does not depend on the order of the file."""
    one_try = sorted(problems, key=lambda p: p["id"])
    random.Random(f"{run_seed}:order").shuffle(one_try)
    return [(problem, t) for t in range(1, tries + 1) for problem in one_try]


def ask(server, problem, try_number, settings, model_version, run_seed, think_end_id, end_text_ids):
    """One try at one problem, in one request. Returns the record to save. `settings` holds "sampling" (sent
    with each request), "source" (where those values were read), "stop_sentence", "thinking_allowance" and
    "answer_allowance"; all are written into the record. `end_text_ids` is the end-of-thinking text in the
    model's tokens (or None), used to see whether the server closed the thinking."""
    question = build_question(problem)
    seed = request_seed(run_seed, problem["id"], try_number)
    record = {"problem_id": problem["id"], "try": try_number, "question": question,
              "system_text": SYSTEM_TEXT, "thinking": None, "answer_text": None, "option": None, "right": False,
              "forced": False, "stop_sentence_found_in": [], "thinking_tokens_before_end_text": None,
              "at_allowance": None, "end_text_inside_budget": None, "cut_off": False,
              "cut_off_but_readable": False, "thinking_tokens": None, "answer_tokens": None,
              "generated_tokens": None, "model_version": model_version, "settings": settings, "request_seed": seed,
              "think_end_token_id": think_end_id, "end_text_token_ids": end_text_ids, "server": server.base_url,
              "failed": False, "error": None}
    started = time.time()
    messages = [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": question}]
    try:
        request = question_request(server.model_name, messages, settings["thinking_allowance"],
                                   settings["answer_allowance"], settings["sampling"], seed)
        reply = read_reply(server.chat(request))
        cut_off = reply["finish_reason"] == "length"     # any other reason ("stop", "abort", ...) is not the limit
        record.update(thinking=reply["thinking"], answer_text=reply["answer"], finish_reason=reply["finish_reason"],
                      generated_tokens=reply["completion_tokens"], prompt_token_ids=reply["prompt_token_ids"],
                      completion_token_ids=reply["token_ids"], completion_text=reply["text"],
                      cut_off=cut_off, cut_off_but_readable=cut_off and read_option(reply["answer"]) is not None,
                      **how_thinking_ended(reply, settings["stop_sentence"], think_end_id, end_text_ids,
                                           settings["thinking_allowance"]))
    except (RequestFailed, BadReply) as error:
        record.update(failed=True, error=repr(error))
    record["option"] = None if record["failed"] else read_option(record["answer_text"])
    record["right"] = record["option"] == problem["held_back"]
    record["tokens_used"] = record["generated_tokens"] or 0     # one reply: everything the model wrote
    record["seconds"] = round(time.time() - started, 3)
    record["finished_at"] = time.time()
    return record


def read_saved(path):
    """Records already saved. A torn last line (the run was stopped mid-write) is cut off the file."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        data = f.read()
    if data and not data.endswith(b"\n"):
        data = data[:data.rfind(b"\n") + 1]
        with open(path, "wb") as f:
            f.write(data)
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


def drop_failed(path):
    """Remove the records of failed requests from the file, so they are asked again; returns those kept. The
    kept records go to a new file beside it, which then replaces the old one in one step: a run killed during
    the rewrite leaves the old file whole."""
    kept = [r for r in read_saved(path) if not r["failed"]]
    new = f"{path}.rewrite"
    with open(new, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in kept)
        f.flush()
        os.fsync(f.fileno())
    os.replace(new, path)
    return kept


def from_any_server(servers, lookup):
    """`lookup(server)` from the first server that answers. Every server runs the same model, so any will do;
    trying the others too means one server down at the start does not stop the run."""
    for server in servers[:-1]:
        try:
            return lookup(server)
        except RequestFailed:
            pass
    return lookup(servers[-1])


def thinking_end_tokens(servers, stop_sentence):
    """(the id of the end-of-thinking token, or None; the end-of-thinking text for `stop_sentence` in the
    model's tokens, or None if there are none), both from one server. The id is None unless the marker is a
    single token and the end text's tokens end with it, as they must if the marker is one token everywhere:
    otherwise thinking tokens cannot be counted."""
    def lookup(server):
        return server.token_ids(THINK_END), server.token_ids(end_of_thinking_text(stop_sentence))
    marker, end_text = from_any_server(servers, lookup)
    single = len(marker) == 1 and end_text[-1:] == marker
    return (marker[0] if single else None), (end_text or None)


def run(problems, servers, out_path, tries, settings, model_version, run_seed, limit=None, workers=1,
        retry_failed=False, log=print):
    """Ask every problem `tries` times, in the order of `order_of_asking`, spread evenly over `servers` (a list),
    with `workers` requests in flight at each; every record is appended to the one file `out_path` as soon as
    it arrives. With `limit`, ask at most that many. With `retry_failed`, records of failed requests are
    removed first and asked again."""
    saved = drop_failed(out_path) if retry_failed else read_saved(out_path)
    done = {(r["problem_id"], r["try"]) for r in saved}
    todo = [(p, t) for p, t in order_of_asking(problems, tries, run_seed) if (p["id"], t) not in done]
    todo = todo if limit is None else todo[:limit]
    log(f"{len(done)} answers already saved, {len(todo)} to ask")
    if not todo:
        return []
    think_end_id, end_text_ids = thinking_end_tokens(servers, settings["stop_sentence"])
    lock = threading.Lock()

    def ask_and_save(server, job):
        record = ask(server, job[0], job[1], settings, model_version, run_seed, think_end_id, end_text_ids)
        with lock:
            out.write(json.dumps(record) + "\n")
            out.flush()
            os.fsync(out.fileno())
        return record
    # Each server has its own pool, so a server that keeps failing slows only its own share. What is left to
    # ask is dealt out in turn, so the servers get equal shares however many there are on this start.
    # An error in our own code stops the run: what has not started is cancelled, and the file stays open
    # until what has started is saved.
    pools = [ThreadPoolExecutor(max_workers=workers) for _ in servers]
    with open(out_path, "a") as out:
        try:
            futures = [pools[n % len(servers)].submit(ask_and_save, servers[n % len(servers)], job)
                       for n, job in enumerate(todo)]
            records = [future.result() for future in futures]
        finally:
            for pool in pools:
                pool.shutdown(cancel_futures=True)
    log(f"asked {len(records)}: {sum(r['forced'] for r in records)} forced, {sum(r['failed'] for r in records)} failed")
    return records
