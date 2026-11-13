"""The model run's check on itself, after its first answers (100 by default).

Four checks, from cube_plan.md: every record is complete; forced answers come back readable about as often as
unforced ones; no more than 15% of answers are unreadable; the projected cost of the whole run is under the
ceiling. The answers checked are part of the real data. The answers' figures come from scoring.py; the speed
and cost projection are worked out here.
"""
from cube_ladder import scoring
from cube_ladder.scoring import ScoringError


def answers_per_hour(finished_at):
    """Speed from the times (seconds) at which answers finished: answers after the first, per hour between
    the first and the last. A pause in the run makes it look slower, never faster."""
    if len(finished_at) < 2 or max(finished_at) == min(finished_at):
        raise ScoringError("need at least two answers finished at different times to measure speed")
    return (len(finished_at) - 1) / ((max(finished_at) - min(finished_at)) / 3600)


def projected_run(answers_per_hour, answers_needed, price_per_hour):
    """Hours and dollars for a run of `answers_needed` answers at the measured speed."""
    hours = answers_needed / answers_per_hour
    return {"hours": hours, "cost": hours * price_per_hour}


def readable_share(answers):
    """Share of `answers` from which a turn can be read; None if there are none."""
    if not answers:
        return None
    return sum(scoring.model_turn(a) is not None for a in answers) / len(answers)


def check(answers, answers_needed, price_per_hour, cost_ceiling=300.0, readable_margin=0.15,
          unreadable_limit=0.15):
    """Returns {"passed": bool, "problems": [...], and the figures behind each check}.

    Forced answers pass when their readable share is at least the unforced answers' readable share minus
    `readable_margin`. If there are no forced answers, or no unforced ones, there is nothing to compare and
    that check holds; the figures say so."""
    problems = []
    incomplete = [f"{a['state_id']} try {a['try']}" for a in answers
                  if a["failed"] or not a["question"] or a["thinking"] is None or a["answer_text"] is None
                  or a["generated_tokens"] is None]
    with_thinking = sum(bool(a["thinking"]) for a in answers) / len(answers)
    if incomplete:
        problems.append(f"incomplete records (failed, or missing question, thinking, answer or token count): "
                        f"{incomplete[:10]}")
    if with_thinking <= 0.5:   # thinking must be there on most (more than half) of the answers
        problems.append(f"thinking is empty on most answers (present on {with_thinking:.2f}); the server may be "
                        f"putting the thinking in the answer field")
    forced = readable_share([a for a in answers if a["forced"]])
    unforced = readable_share([a for a in answers if not a["forced"]])
    if forced is not None and unforced is not None and forced < unforced - readable_margin:
        problems.append(f"forced answers readable {forced:.2f}, unforced {unforced:.2f}: more than "
                        f"{readable_margin} apart")
    use = scoring.answer_use(answers)
    if use["unreadable_share"] > unreadable_limit:
        problems.append(f"{use['unreadable_share']:.2f} of answers unreadable, above {unreadable_limit}")
    speed = answers_per_hour([a["finished_at"] for a in answers])
    projected = projected_run(speed, answers_needed, price_per_hour)
    if projected["cost"] > cost_ceiling:
        problems.append(f"projected cost ${projected['cost']:.0f} is above ${cost_ceiling:.0f}")
    return {"passed": not problems, "problems": problems, "answers_checked": len(answers),
            "share_with_thinking": with_thinking, "forced_readable_share": forced,
            "unforced_readable_share": unforced, "readable_margin": readable_margin, **use,
            "answers_per_hour": speed, "projected_hours": projected["hours"], "projected_cost": projected["cost"],
            "price_per_hour": price_per_hour, "cost_ceiling": cost_ceiling}
