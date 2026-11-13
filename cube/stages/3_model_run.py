"""Stage 3: the model run, every test state --tries times, with its check on itself after the first answers.

Writes model_answers.jsonl to --data, saving each answer as it arrives; the same command carries on where it
stopped. After the first --check-after answers (100) the run pauses and checks itself (cube_ladder/run_check.py)
and writes model_run_check.json, with the tokens one cube takes to write out. If a check fails it stops; after
a decision to go on anyway, run again with --carry-on. With --retry-failed, failed requests are asked again.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder import model_run, run_check, scoring  # noqa: E402
from cube_ladder.model_server import STOP_SENTENCES, ModelServer  # noqa: E402
from cube_ladder.question import colours  # noqa: E402
from cube_ladder.states import read_jsonl  # noqa: E402


def arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--base-url", required=True, help="the model server, without /v1")
    parser.add_argument("--model-name", required=True, help="the name the server knows the model by")
    parser.add_argument("--model-version", required=True, help="exact model version, written into every record")
    parser.add_argument("--settings", required=True, help='JSON file: {"sampling": {...}, "source": "..."}')
    parser.add_argument("--api-key-env", help="name of the environment variable holding the server's key")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--tries", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--wait-seconds", type=float, default=10.0, help="pause before retrying a failed request")
    parser.add_argument("--thinking-allowance", type=int, default=model_run.THINKING_ALLOWANCE)
    parser.add_argument("--answer-allowance", type=int, default=model_run.ANSWER_ALLOWANCE,
                        help="tokens for the answer, on top of the thinking allowance")
    parser.add_argument("--stop-sentence", default="qwen",
                        help="closes cut-off thinking: 'qwen', 'neutral', or the sentence itself")
    parser.add_argument("--check-after", type=int, default=100)
    parser.add_argument("--price-per-hour", type=float, required=True, help="dollars per hour for the run's machines")
    parser.add_argument("--cost-ceiling", type=float, default=300.0)
    parser.add_argument("--readable-margin", type=float, default=0.15,
                        help="how far below the unforced answers' readable share the forced answers' may be")
    parser.add_argument("--carry-on", action="store_true", help="go on after a failed check (a decision taken)")
    parser.add_argument("--retry-failed", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    data = Path(args.data)
    out = data / "model_answers.jsonl"
    settings = json.loads(Path(args.settings).read_text())
    settings.update(stop_sentence=STOP_SENTENCES.get(args.stop_sentence, args.stop_sentence),
                    thinking_allowance=args.thinking_allowance, answer_allowance=args.answer_allowance)
    test = read_jsonl(data / "test_states.jsonl")
    key = os.environ.get(args.api_key_env) if args.api_key_env else None
    server = ModelServer(args.base_url, args.model_name, api_key=key, wait_seconds=args.wait_seconds)

    def ask(limit=None):
        return model_run.run(test, server, out, args.tries, settings, args.model_version, args.seed, limit=limit,
                             workers=args.workers, retry_failed=args.retry_failed)

    ask(limit=max(0, args.check_after - len(model_run.read_saved(out))))
    first = model_run.read_saved(out)[:args.check_after]
    result = run_check.check(first, len(test) * args.tries, args.price_per_hour, args.cost_ceiling,
                             args.readable_margin)
    result["tokens_per_cube_string"] = sum(server.count_tokens(colours(s["cube"])) for s in test[:20]) / len(test[:20])
    (data / "model_run_check.json").write_text(json.dumps(result, indent=1))
    print(f"check after {len(first)} answers: " + ("all four checks hold" if result["passed"] else "FAILED"))
    for problem in result["problems"]:
        print(f"  {problem}")
    if not result["passed"] and not args.carry_on:
        sys.exit("STOP: the run's check on itself failed (see above); run again with --carry-on after a decision")

    ask()
    use = scoring.answer_use(model_run.read_saved(out))
    print(f"{use['answers']} answers saved of {len(test) * args.tries}; failed share {use['failed_share']:.3f}, "
          f"forced share {use['forced_share']:.3f}, unreadable share {use['unreadable_share']:.3f}")
    if use["failed_share"] > 0:
        sys.exit("some requests failed: run again with --retry-failed before stage 4")


if __name__ == "__main__":
    main()
