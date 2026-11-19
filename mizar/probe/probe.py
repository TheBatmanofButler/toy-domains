"""Thinking-length probe (stage 3, not experiment data). Runs ON the pod, from this folder's copy of the code.

For 32 training problems (drawn at random with the run's seed by `choose_problems` from --train): one chat
request shaped like the code's question_request but WITHOUT
thinking_token_budget, max_tokens 64000, thinking on, token ids returned, the run's sampling settings and seed
request_seed(20261112, problem id, 1). 16 requests in flight, client timeout 2 hours. Every full raw reply is
saved as it arrives (replies/<id>.json, with the request and timings). Rows (thinking/answer tokens from the
token ids split at </think>, finish reason, option readable) go to rows.jsonl as each reply arrives.
`--table` instead rebuilds the CSV from the saved replies (used again in the workspace after bring-back).
No right-or-wrong is worked out anywhere here.
"""
import argparse, csv, json, os, random, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mizar_ladder.answers import read_option  # noqa: E402
from mizar_ladder.model_run import request_seed  # noqa: E402
from mizar_ladder.model_server import STOP_SENTENCES, THINK_END, question_request, read_reply  # noqa: E402
from mizar_ladder.problems import read_jsonl  # noqa: E402
from mizar_ladder.question import SYSTEM_TEXT, build_question  # noqa: E402
from mizar_ladder.thinking_end import split_token_count  # noqa: E402

URL = "http://127.0.0.1:8000"
MODEL = "Qwen3.8-27B"
RUN_SEED = 20261112
MAX_TOKENS = 64000
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0}
TIMEOUT = 7200
IN_FLIGHT = 16
PROBLEMS = 32


def log(*x):
    print(time.strftime("%H:%M:%SZ", time.gmtime()), *x, flush=True)


def post(path, payload, timeout):
    r = urllib.request.Request(URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read())


def choose_problems(train, seed=RUN_SEED):
    """32 training problems drawn at random with the seed, in the order of their numbers. Refuses anything that
    is not a training problem, and a training set of fewer than 32."""
    for p in train:
        if not str(p["id"]).startswith("train-"):
            raise ValueError(f"{p['id']}: the probe takes training problems only")
    if len(train) < PROBLEMS:
        raise ValueError(f"only {len(train)} training problems")
    drawn = set(random.Random(f"{seed}:thinking probe").sample(sorted(p["id"] for p in train), PROBLEMS))
    return sorted((p for p in train if p["id"] in drawn), key=lambda p: p["id"])


def make_request(problem):
    messages = [{"role": "system", "content": SYSTEM_TEXT},
                {"role": "user", "content": build_question(problem)}]
    seed = request_seed(RUN_SEED, problem["id"], 1)
    req = question_request(MODEL, messages, 0, 0, SAMPLING, seed)   # the code's shape...
    del req["thinking_token_budget"]                                # ...without the thinking budget
    req["max_tokens"] = MAX_TOKENS
    assert req["chat_template_kwargs"] == {"enable_thinking": True} and req["return_token_ids"] is True
    return req


def row(problem, saved, think_end_id):
    r = {"id": problem["id"]}
    if "reply" not in saved:
        r.update(status="failed" if "error" in saved else "not finished within the time")
        return r
    rep = read_reply(saved["reply"])
    th, an = split_token_count(rep["token_ids"], think_end_id)
    ids = rep["token_ids"] or []
    stop = STOP_SENTENCES["qwen"]
    fact_lines = [l for l in rep["answer"].splitlines() if l.strip().upper().startswith("FACT")]
    r.update(status="finished", thinking_tokens=th, answer_tokens=an, completion_tokens=rep["completion_tokens"],
             finish_reason=rep["finish_reason"], ended_on_limit=(rep["finish_reason"] == "length"),
             option_readable=read_option(rep["answer"]) is not None, thinking_closed=(think_end_id in ids),
             think_end_count=ids.count(think_end_id), fact_lines=len(fact_lines),
             stop_sentence_in_thinking=rep["thinking"].count(stop), stop_sentence_in_answer=rep["answer"].count(stop),
             seconds=saved.get("seconds"), prompt_tokens=saved["reply"].get("usage", {}).get("prompt_tokens"),
             answer_chars=len(rep["answer"]), thinking_chars=len(rep["thinking"]))
    return r


FIELDS = ["id", "status", "thinking_tokens", "answer_tokens", "completion_tokens", "finish_reason",
          "ended_on_limit", "option_readable", "thinking_closed", "think_end_count", "fact_lines",
          "stop_sentence_in_thinking", "stop_sentence_in_answer", "seconds", "prompt_tokens", "answer_chars",
          "thinking_chars"]


def write_table(problems, out, think_end_id):
    rows = []
    for c in problems:
        f = os.path.join(out, "replies", c["id"] + ".json")
        rows.append(row(c, json.load(open(f)) if os.path.exists(f) else {}, think_end_id))
    with open(os.path.join(out, "probe_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--train", required=True, help="train_problems.jsonl from stage 1")
    p.add_argument("--out", required=True)
    p.add_argument("--deadline", type=float, default=None, help="epoch seconds: stop waiting and exit then")
    p.add_argument("--table", action="store_true")
    p.add_argument("--think-end-id", type=int, default=None)
    a = p.parse_args(argv)
    problems = choose_problems(read_jsonl(a.train))
    os.makedirs(os.path.join(a.out, "replies"), exist_ok=True)
    if a.table:
        write_table(problems, a.out, a.think_end_id)
        sys.exit(0)

    tk = post("/tokenize", {"model": MODEL, "prompt": THINK_END, "add_special_tokens": False}, 60)
    assert len(tk["tokens"]) == 1, tk
    think_end_id = tk["tokens"][0]
    log("think_end id", think_end_id)
    json.dump({"think_end_tokens": tk["tokens"], "model": MODEL, "run_seed": RUN_SEED, "max_tokens": MAX_TOKENS,
               "sampling": SAMPLING, "timeout": TIMEOUT, "in_flight": IN_FLIGHT},
              open(os.path.join(a.out, "probe_settings.json"), "w"))
    lock = threading.Lock()
    rows_f = open(os.path.join(a.out, "rows.jsonl"), "a")

    def one(c):
        req = make_request(c)
        t0 = time.time()
        with lock:
            log("start", c["id"], "seed", req["seed"])
        saved = {"id": c["id"], "request": req, "started": t0}
        try:
            saved["reply"] = post("/v1/chat/completions", req, TIMEOUT)
        except Exception as e:
            saved["error"] = repr(e)
        saved["ended"] = time.time(); saved["seconds"] = round(saved["ended"] - t0, 3)
        path = os.path.join(a.out, "replies", c["id"] + ".json")
        with open(path + ".tmp", "w") as f:
            json.dump(saved, f); f.flush(); os.fsync(f.fileno())
        os.replace(path + ".tmp", path)
        r = row(c, saved, think_end_id)
        with lock:
            rows_f.write(json.dumps(r) + "\n"); rows_f.flush(); os.fsync(rows_f.fileno())
            log("done", c["id"], json.dumps({k: r.get(k) for k in ("status", "thinking_tokens", "answer_tokens",
                                                                     "finish_reason", "option_readable", "seconds")}))
        return r

    pool = ThreadPoolExecutor(max_workers=IN_FLIGHT)
    futures = [pool.submit(one, c) for c in problems]
    while True:
        done = sum(f.done() for f in futures)
        if done == len(futures):
            break
        if a.deadline and time.time() >= a.deadline:
            log(f"DEADLINE reached: {done} of {len(futures)} finished; the rest are not finished within the time")
            write_table(problems, a.out, think_end_id)
            os._exit(3)
        time.sleep(5)
    write_table(problems, a.out, think_end_id)
    log("ALL DONE", len(futures))


if __name__ == "__main__":
    main()
