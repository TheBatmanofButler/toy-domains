"""The model run's check on itself, after its first answers (100 by default).

Four checks, from cube_plan.md: every record is complete; forced answers come back readable about as often as
unforced ones; no more than 15% of answers are unreadable; the projected cost of the whole run is under the
ceiling. With too few forced or too few unforced answers to compare, the second check is reported as not
tested, except that a handful of forced answers (3 to 9) mostly unreadable still fails it. Beside those four,
a check that the server's thinking budget behaves as the run assumes (`budget_check`). The answers checked are
part of the real data. The answers' figures come from scoring.py; the speed and cost projection are worked out
here. Speed is the number of answers checked over the time from the first request starting to the last answer
finishing (see `answers_per_hour`). With several servers the speed is theirs together, so the price per hour is
the total for all of them.
"""
from mizar_ladder import scoring
from mizar_ladder.scoring import ScoringError
from mizar_ladder.thinking_end import ALLOWANCE_TOLERANCE, fits_allowance


def answers_per_hour(answers):
    """Speed, in answers per hour: the number of `answers` over the time from the first request starting to
    the last answer finishing. A request started at its record's `finished_at` less its `seconds` (how long
    that try took). Measured from the first start, not the first finish, because requests sent together finish
    together: the time between finishes says nothing about how long each took. A single answer gives one
    answer over its own duration. A pause in the run (the time between two starts of it) only adds to the
    time measured, so it makes the run look slower, never faster. Records saved without `seconds` (an older
    file) cannot be measured and give a plain error."""
    if not answers:
        raise ScoringError("no answers to measure speed on")
    unmeasured = [f"{a['problem_id']} try {a['try']}" for a in answers if "seconds" not in a or "finished_at" not in a]
    if unmeasured:
        raise ScoringError(f"speed cannot be measured: {len(unmeasured)} answers were saved without how long they "
                           f"took (`seconds`) or when they finished (`finished_at`), first {unmeasured[:3]}")
    first_start = min(a["finished_at"] - a["seconds"] for a in answers)
    last_finish = max(a["finished_at"] for a in answers)
    if last_finish <= first_start:
        raise ScoringError("speed cannot be measured: the answers took no time")
    return len(answers) / ((last_finish - first_start) / 3600)


def projected_run(answers_per_hour, answers_needed, price_per_hour):
    """Hours and dollars for a run of `answers_needed` answers at the measured speed."""
    hours = answers_needed / answers_per_hour
    return {"hours": hours, "cost": hours * price_per_hour}


def readable_share(answers):
    """Share of `answers` from which an option can be read; None if there are none."""
    if not answers:
        return None
    return sum(scoring.model_option(a) is not None for a in answers) / len(answers)


# The fields the budget check reads; answers saved before the run recorded them cannot be checked.
BUDGET_FIELDS = ("stop_sentence_found_in", "thinking_tokens_before_end_text", "completion_token_ids",
                 "think_end_token_id", "end_text_token_ids")


def budget_misfit(a):
    """Why answer `a` does not fit the run's picture of the server's budget, or None if it fits. Judged
    against the allowance in the answer's own settings (the one it was asked with, which a later start may
    have changed). The run assumes the server closes the thinking with its end text at the allowance, and only
    there. So the end text found away from the allowance (the server closing early or late, or the model
    writing the sentence itself) does not fit, nor does thinking past the allowance with no end text (a server
    not enforcing the budget). Thinking that ends by itself anywhere under the allowance, even a few tokens
    under, is healthy: the model is free to stop thinking when it likes."""
    allowance = a["settings"]["thinking_allowance"]
    end_text_length = len(a["end_text_token_ids"] or []) if a["stop_sentence_found_in"] else 0
    before = a["thinking_tokens_before_end_text"]
    if before is None:
        why = ("the server returned no token ids" if a["completion_token_ids"] is None
               else "the end-of-thinking marker is not a single token")
        return f"thinking tokens cannot be counted ({why})"
    if a["stop_sentence_found_in"] and not fits_allowance(before, allowance, end_text_length)[0]:
        return f"end text after {before} thinking tokens, allowance {allowance}"
    if not a["stop_sentence_found_in"] and a["thinking_tokens"] >= allowance + ALLOWANCE_TOLERANCE:
        return f"no end text, {a['thinking_tokens']} thinking tokens, allowance {allowance}"
    return None


def budget_check(answers):
    """(outcome, problem or None, the answers that do not fit, each named with why) for the server's thinking
    budget (see `budget_misfit`). Failed answers are left out (they fail as incomplete)."""
    worked = [a for a in answers if not a["failed"]]
    if any(field not in a for a in worked for field in BUDGET_FIELDS):
        return ("not checked", "budget not checked: the answers were saved without the fields this check reads "
                               "(where the end text was found and the thinking tokens before it)", [])
    misfits = [f"{a['problem_id']} try {a['try']}: {why}" for a in worked if (why := budget_misfit(a))]
    if not misfits:
        return "as assumed", None, []
    outcome = "not checked" if all("cannot be counted" in m for m in misfits) else "not as assumed"
    return outcome, (f"the server's thinking budget is not behaving as assumed, or cannot be checked, "
                     f"on {len(misfits)} answers: {misfits[:10]}"), misfits


def check(answers, answers_needed, price_per_hour, cost_ceiling=300.0, readable_margin=0.15,
          unreadable_limit=0.15, fewest_to_compare=10, fewest_forced_to_judge=3):
    """Returns {"passed": bool, "problems": [...], and the figures behind each check}.

    Forced answers pass when their readable share is at least the unforced answers' readable share minus
    `readable_margin`. With fewer than `fewest_to_compare` forced answers, or unforced ones, two shares that
    small say little, so the comparison is "not tested" (field `forced_comparison`): it is not counted as a
    problem and the run carries on, but the file and the printout say plainly that it was not tested.
    One exception: from `fewest_forced_to_judge` (3) up to one below `fewest_to_compare` forced answers, fewer
    than half of them readable is a problem even untested: too few to compare shares, but enough to show the
    forced answers may not be giving readable answers. Below 3 forced answers nothing is judged.
    The budget check (`budget_check` above) judges each answer by the allowance it was asked with."""
    problems = []
    incomplete = [f"{a['problem_id']} try {a['try']}" for a in answers
                  if a["failed"] or not a["question"] or a["thinking"] is None or a["answer_text"] is None
                  or a["generated_tokens"] is None]
    with_thinking = sum(bool(a["thinking"]) for a in answers) / len(answers)
    if incomplete:
        problems.append(f"incomplete records (failed, or missing question, thinking, answer or token count): "
                        f"{incomplete[:10]}")
    if with_thinking <= 0.5:   # thinking must be there on most (more than half) of the answers
        problems.append(f"thinking is empty on most answers (present on {with_thinking:.2f}); the server may be "
                        f"putting the thinking in the answer field")
    forced_answers = [a for a in answers if a["forced"]]
    unforced_answers = [a for a in answers if not a["forced"]]
    forced, unforced = readable_share(forced_answers), readable_share(unforced_answers)
    tested = min(len(forced_answers), len(unforced_answers)) >= fewest_to_compare
    if tested and forced < unforced - readable_margin:
        problems.append(f"forced answers readable {forced:.2f}, unforced {unforced:.2f}: more than "
                        f"{readable_margin} apart")
    readable_forced = sum(scoring.model_option(a) is not None for a in forced_answers)
    if (not tested and fewest_forced_to_judge <= len(forced_answers) < fewest_to_compare
            and readable_forced < len(forced_answers) / 2):
        problems.append(f"only {readable_forced} of {len(forced_answers)} forced answers readable, fewer than half "
                        f"(too few forced answers to compare with the unforced ones, but too few readable to go on)")
    use = scoring.answer_use(answers)
    if use["unreadable_share"] > unreadable_limit:
        problems.append(f"{use['unreadable_share']:.2f} of answers unreadable, above {unreadable_limit}")
    budget, budget_problem, misfits = budget_check(answers)
    if budget_problem:
        problems.append(budget_problem)
    speed = answers_per_hour(answers)
    projected = projected_run(speed, answers_needed, price_per_hour)
    if projected["cost"] > cost_ceiling:
        problems.append(f"projected cost ${projected['cost']:.0f} is above ${cost_ceiling:.0f}")
    return {"passed": not problems, "problems": problems, "answers_checked": len(answers),
            "share_with_thinking": with_thinking, "forced_readable_share": forced,
            "unforced_readable_share": unforced, "readable_margin": readable_margin,
            "forced_comparison": "tested" if tested else "not tested", "forced_answers_compared": len(forced_answers),
            "unforced_answers_compared": len(unforced_answers), "fewest_to_compare": fewest_to_compare,
            "fewest_forced_to_judge": fewest_forced_to_judge, **use, "budget_check": budget,
            "budget_misfits": misfits[:10], "budget_misfit_count": len(misfits),
            "end_text_inside_budget_count": sum(a.get("end_text_inside_budget") is True for a in answers),
            "end_text_outside_budget_count": sum(a.get("end_text_inside_budget") is False for a in answers),
            "thinking_allowances": sorted({a["settings"]["thinking_allowance"] for a in answers}),
            "answers_per_hour": speed, "projected_hours": projected["hours"], "projected_cost": projected["cost"],
            "price_per_hour": price_per_hour, "cost_ceiling": cost_ceiling}
