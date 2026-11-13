"""Asks the model about each test state several times and saves every answer as it arrives.

Thinking is on, with an allowance of 8,000 tokens for thinking and, on top, a small allowance for the answer.
If the model runs out before a readable answer, its thinking is closed with a stop sentence and it carries on
into its answer in the same turn (model_server.continuation_request); the record is marked `forced`. Every
record keeps the exact question, thinking and answer, the token ids if the server returns them, the model
version and the settings. A request that keeps failing is recorded as failed, never dropped. A stopped run
can be started again: answers already saved are skipped.
"""
import json
import os
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

from cube_ladder.answers import read_turn
from cube_ladder.model_server import BadReply, RequestFailed, continuation_request, question_request, read_reply
from cube_ladder.question import SYSTEM_TEXT, build_question

THINKING_ALLOWANCE = 8000
ANSWER_ALLOWANCE = 200


def request_seed(run_seed, state_id, try_number):
    """A fixed sampling seed for each (state, try): a rerun sends exactly the same requests. The server may
    still answer differently (batching and hardware change the arithmetic), so answers are not reproducible."""
    return zlib.crc32(f"{run_seed}:{state_id}:{try_number}".encode()) % 2**31


def split_token_count(token_ids, think_end_id):
    """(thinking tokens, answer tokens) from the completion's token ids: the tokens before and after the
    end-of-thinking token, which itself counts as neither. If the thinking never ended, every token is
    thinking. (None, None) if the server gave no ids or the model has no single end-of-thinking token."""
    if token_ids is None or think_end_id is None:
        return None, None
    if think_end_id not in token_ids:
        return len(token_ids), 0
    end = token_ids.index(think_end_id)
    return end, len(token_ids) - end - 1


def ask(server, state, try_number, settings, model_version, run_seed, think_end_id):
    """One try at one state. Returns the record to save. `settings` holds "sampling" (sent with each
    request), "source" (where those values were read), "stop_sentence", "thinking_allowance" and
    "answer_allowance"; all are written into the record."""
    question = build_question(state["cube"])
    seed = request_seed(run_seed, state["id"], try_number)
    record = {"state_id": state["id"], "try": try_number, "distance": state["distance"], "question": question,
              "system_text": SYSTEM_TEXT, "thinking": None, "answer_text": None, "turn": None, "right": False,
              "forced": False, "cut_off_but_readable": False, "thinking_tokens": None, "answer_tokens": None,
              "generated_tokens": None, "forced_answer_tokens": 0, "model_version": model_version,
              "settings": settings, "request_seed": seed, "think_end_token_id": think_end_id,
              "failed": False, "error": None}
    started = time.time()
    messages = [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": question}]
    sampling = settings["sampling"]
    try:
        first = question_request(server.model_name, messages, settings["thinking_allowance"] + settings["answer_allowance"],
                                 sampling, seed)
        thinking, answer, finish, token_ids, generated, prompt_ids = read_reply(server.chat(first))
        thinking_tokens, answer_tokens = split_token_count(token_ids, think_end_id)
        ran_out = finish == "length"
        record.update(thinking=thinking, answer_text=answer, first_answer_text=answer, finish_reason=finish,
                      generated_tokens=generated, thinking_tokens=thinking_tokens, answer_tokens=answer_tokens,
                      prompt_token_ids=prompt_ids, completion_token_ids=token_ids,
                      cut_off_but_readable=ran_out and read_turn(answer) is not None)
        if ran_out and read_turn(answer) is None:
            request, assistant_text = continuation_request(server.model_name, messages, thinking,
                                                           settings["stop_sentence"], settings["answer_allowance"],
                                                           sampling, seed)
            more_thinking, more_answer, _, more_ids, more_tokens, _ = read_reply(server.chat(request))
            # The reasoning parser may label the continuation as thinking; the answer is whichever came back.
            record.update(forced=True, answer_text=more_answer or more_thinking,
                          continuation_answer_field="content" if more_answer else "reasoning",
                          continuation_text=assistant_text, forced_answer_tokens=more_tokens,
                          continuation_token_ids=more_ids)
    except (RequestFailed, BadReply) as error:
        record.update(failed=True, error=repr(error))
    record["turn"] = None if record["failed"] else read_turn(record["answer_text"])
    record["right"] = record["turn"] in state["right_turns"]
    record["tokens_used"] = (record["generated_tokens"] or 0) + record["forced_answer_tokens"]
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


def end_of_thinking_token(server):
    """The id of the token that ends the thinking, if '</think>' is a single token; else None."""
    ids = server.token_ids("</think>")
    return ids[0] if len(ids) == 1 else None


def run(states, server, out_path, tries, settings, model_version, run_seed, limit=None, workers=1,
        retry_failed=False, log=print):
    """Ask every state `tries` times, in the order states x tries, appending each record to `out_path` as
    soon as it arrives; with `limit`, ask at most that many. With `retry_failed`, records of failed requests
    are removed first and asked again."""
    saved = read_saved(out_path)
    if retry_failed:
        saved = [r for r in saved if not r["failed"]]
        with open(out_path, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in saved)
    done = {(r["state_id"], r["try"]) for r in saved}
    todo = [(s, t) for s in states for t in range(1, tries + 1) if (s["id"], t) not in done]
    todo = todo if limit is None else todo[:limit]
    log(f"{len(done)} answers already saved, {len(todo)} to ask")
    if not todo:
        return []
    think_end_id = end_of_thinking_token(server)
    lock = threading.Lock()
    with open(out_path, "a") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        def ask_and_save(job):
            record = ask(server, job[0], job[1], settings, model_version, run_seed, think_end_id)
            with lock:
                out.write(json.dumps(record) + "\n")
                out.flush()
                os.fsync(out.fileno())
            return record
        records = list(pool.map(ask_and_save, todo))
    log(f"asked {len(records)}: {sum(r['forced'] for r in records)} forced, {sum(r['failed'] for r in records)} failed")
    return records
