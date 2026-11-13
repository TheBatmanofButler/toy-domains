"""Stage 3: the model run, every test state --tries times, with its check on itself after the first answers.

Writes model_answers.jsonl to --data, saving each answer as it arrives; the same command carries on where it
stopped. After the first --check-after answers (100) the run pauses and checks itself (cube_ladder/run_check.py)
and writes model_run_check.json, with the tokens one cube takes to write out. Speed is those answers over the
time from the first request starting to the last answer finishing. If a check fails it stops; after
a decision to go on anyway, run again with --carry-on. Too few forced or unforced answers to compare is reported
as not tested, but 3 to 9 forced answers with fewer than half readable fails the check. With --retry-failed,
failed requests are asked again; failed ones among the first answers are asked again before the check.

The check is made once. When model_run_check.json says it passed, or that the run was carried on after it with
--carry-on, a later start neither makes it again nor rewrites the file: the speed it measured belongs to the
servers and the price of that time. A check that failed and was not overridden is made again on the next start.

The model server enforces the thinking allowance itself and must be started with the end-of-thinking text the
run records: `--print-reasoning-config` prints the JSON for the server's --reasoning-config, for the chosen
--stop-sentence, and exits (no other argument is needed).

--base-url may be given once per model server: the questions are spread evenly over them, --workers requests
in flight at each, and every record names its server. Starting again with more or fewer servers carries on
from what is saved, which is how servers are added after the check.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder import model_run, run_check, scoring  # noqa: E402
from cube_ladder.model_server import STOP_SENTENCES, ModelServer, end_of_thinking_text, reasoning_config  # noqa: E402
from cube_ladder.question import colours  # noqa: E402
from cube_ladder.states import read_jsonl  # noqa: E402


STOP_SENTENCE_HELP = "closes thinking cut short by the budget: 'qwen', 'neutral', or the sentence itself"


def chosen_sentence(name):
    return STOP_SENTENCES.get(name, name)


def printing_config(argv):
    """The stop sentence if only the reasoning config is asked for (--print-reasoning-config), else None. Read
    apart from the other arguments, so none of them is needed for it."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--print-reasoning-config", action="store_true")
    parser.add_argument("--stop-sentence", default="qwen")
    known, _ = parser.parse_known_args(argv)
    return chosen_sentence(known.stop_sentence) if known.print_reasoning_config else None


def arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-reasoning-config", action="store_true",
                        help="print the JSON for the model server's --reasoning-config and exit")
    parser.add_argument("--data", required=True)
    parser.add_argument("--base-url", required=True, action="append",
                        help="a model server, without /v1; give it once for each server")
    parser.add_argument("--model-name", required=True, help="the name the server knows the model by")
    parser.add_argument("--model-version", required=True, help="exact model version, written into every record")
    parser.add_argument("--settings", required=True, help='JSON file: {"sampling": {...}, "source": "..."}')
    parser.add_argument("--api-key-env",
                        help="name of the environment variable holding the key (the same key for every server)")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--tries", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8, help="requests in flight at each server")
    parser.add_argument("--wait-seconds", type=float, default=10.0, help="pause before retrying a failed request")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds one request may take")
    parser.add_argument("--thinking-allowance", type=int, default=model_run.THINKING_ALLOWANCE)
    parser.add_argument("--answer-allowance", type=int, default=model_run.ANSWER_ALLOWANCE,
                        help="tokens for the answer, on top of the thinking allowance")
    parser.add_argument("--stop-sentence", default="qwen", help=STOP_SENTENCE_HELP)
    parser.add_argument("--check-after", type=int, default=100)
    parser.add_argument("--price-per-hour", type=float, required=True,
                        help="dollars per hour for all the run's machines together (every server), not per server")
    parser.add_argument("--cost-ceiling", type=float, default=300.0)
    parser.add_argument("--readable-margin", type=float, default=0.15,
                        help="how far below the unforced answers' readable share the forced answers' may be")
    parser.add_argument("--carry-on", action="store_true", help="go on after a failed check (a decision taken)")
    parser.add_argument("--retry-failed", action="store_true")
    return parser.parse_args(argv)


def made_earlier(path):
    """The check file if the check was made and is not to be made again (it passed, or the run was carried on
    after it); else None."""
    if not path.exists():
        return None
    result = json.loads(path.read_text())
    return result if result["passed"] or result.get("carried_on") else None


def make_check(args, test, servers, out, check_path, ask):
    """Ask what is still missing of the first --check-after answers, check exactly those, write the check file
    and print the outcome. Returns the result."""
    ask(limit=max(0, args.check_after - len(model_run.read_saved(out))))
    first = model_run.read_saved(out)[:args.check_after]
    # The budget is judged by the allowance each answer was asked with, which is in its own record.
    try:
        result = run_check.check(first, len(test) * args.tries, args.price_per_hour, args.cost_ceiling,
                                 args.readable_margin)
    except scoring.ScoringError as error:    # e.g. answers saved without `seconds`: say so, without a trace
        sys.exit(f"STOP: the run's check on itself cannot be made: {error}")
    # One server that answers is found once and gives all 20 counts (every server runs the same model).
    counts = model_run.from_any_server(servers, lambda server: [server.count_tokens(colours(s["cube"]))
                                                                for s in test[:20]])
    result["tokens_per_cube_string"] = sum(counts) / len(counts)
    result["servers"] = sorted({a["server"] for a in first})   # those that gave the answers checked
    result["servers_given"] = [server.base_url for server in servers]   # this start's, which --price-per-hour is for
    result["carried_on"] = not result["passed"] and args.carry_on
    check_path.write_text(json.dumps(result, indent=1))
    tested = result["forced_comparison"] == "tested"
    held = "all four checks hold" if tested else "the other three checks hold; forced against unforced not tested"
    print(f"check after {len(first)} answers: " + (held if result["passed"] else "FAILED"))
    print(f"  forced against unforced: {result['forced_comparison']} ({result['forced_answers_compared']} forced, "
          f"{result['unforced_answers_compared']} unforced answers compared; at least {result['fewest_to_compare']} "
          f"of each are needed; with {result['fewest_forced_to_judge']} to {result['fewest_to_compare'] - 1} "
          f"forced answers, at least half must be readable)")
    print(f"  server's thinking budget: {result['budget_check']} ({result['forced_answers_compared']} forced: "
          f"{result['end_text_outside_budget_count']} with the end text after the allowance, "
          f"{result['end_text_inside_budget_count']} with it inside; {result['budget_misfit_count']} that do not fit)")
    for problem in result["problems"]:
        print(f"  {problem}")
    return result


def main(argv=None):
    sentence = printing_config(sys.argv[1:] if argv is None else argv)
    if sentence is not None:
        print(reasoning_config(sentence))
        return
    args = arguments(argv)
    data = Path(args.data)
    out = data / "model_answers.jsonl"
    check_path = data / "model_run_check.json"
    settings = json.loads(Path(args.settings).read_text())
    sentence = chosen_sentence(args.stop_sentence)
    settings.update(stop_sentence=sentence, end_of_thinking_text=end_of_thinking_text(sentence),
                    thinking_allowance=args.thinking_allowance, answer_allowance=args.answer_allowance)
    test = read_jsonl(data / "test_states.jsonl")
    key = os.environ.get(args.api_key_env) if args.api_key_env else None
    servers = [ModelServer(url, args.model_name, api_key=key, wait_seconds=args.wait_seconds, timeout=args.timeout)
               for url in args.base_url]
    addresses = [server.base_url for server in servers]
    if len(set(addresses)) < len(addresses):
        sys.exit(f"the same server address is given twice: {sorted({a for a in addresses if addresses.count(a) > 1})}")
    # Failed records go before anything is asked, so failed first answers are asked again before the check.
    if args.retry_failed:
        model_run.drop_failed(out)

    def ask(limit=None):
        return model_run.run(test, servers, out, args.tries, settings, args.model_version, args.seed, limit=limit,
                             workers=args.workers)

    earlier = made_earlier(check_path)
    if earlier:
        print(f"check made earlier on {earlier['answers_checked']} answers ("
              + ("passed" if earlier["passed"] else "failed, carried on") + f"); see {check_path.name}")
    elif check_path.exists() and args.carry_on:
        earlier = json.loads(check_path.read_text())
        earlier["carried_on"] = True
        check_path.write_text(json.dumps(earlier, indent=1))
        print(f"check made earlier on {earlier['answers_checked']} answers (failed); carried on with --carry-on")
    elif not make_check(args, test, servers, out, check_path, ask)["passed"] and not args.carry_on:
        sys.exit("STOP: the run's check on itself failed (see above); run again with --carry-on after a decision")

    ask()
    use = scoring.answer_use(model_run.read_saved(out))
    print(f"{use['answers']} answers saved of {len(test) * args.tries}; failed share {use['failed_share']:.3f}, "
          f"forced share {use['forced_share']:.3f}, unreadable share {use['unreadable_share']:.3f}")
    if use["failed_share"] > 0:
        sys.exit("some requests failed: run again with --retry-failed before stage 4")


if __name__ == "__main__":
    main()
