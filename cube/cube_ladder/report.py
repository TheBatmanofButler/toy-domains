"""Writes the report's tables as text and draws score against distance as an SVG picture.

No figure is worked out here: every number comes from scoring.py (and, for the same-wrong-turns table, from
wrong_turns.py). The picture is drawn by hand as SVG so that
no plotting library is needed.
"""
from xml.sax.saxutils import escape


def _cell(value):
    if value is None:
        return "n/a"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _table(header, rows):
    widths = [max(len(_cell(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(_cell(v).rjust(w) for v, w in zip(row, widths)) for row in [header] + rows]
    return "\n".join([lines[0], "-" * len(lines[0])] + lines[1:])


def scores_text(by_distance):
    """One row per distance: each program, the best programs (ties joined by +), room, and the model's figures."""
    distances = sorted(by_distance, key=int)
    programs = sorted(by_distance[distances[0]]["programs"])
    with_model = "model" in by_distance[distances[0]]
    header = ["distance", "states"] + programs + ["best", "room"]
    if with_model:
        header += ["model", "unreadable", "forced", "thinking_tokens"]
    rows = []
    for d in distances:
        row = by_distance[d]
        line = ([int(d), row["states"]] + [row["programs"][p] for p in programs]
                + ["+".join(row["best_programs"]), row["room"]])
        if with_model:
            line += [row["model"], row["unreadable_share"], row["forced_share"], row["thinking_tokens_mean"]]
        rows.append(line)
    return _table(header, rows)


def standard_errors_text(by_distance):
    """One row per distance: the standard error of each program's score, of room (the best program's, named),
    and of the model's score. n/a where a distance has one state."""
    distances = sorted(by_distance, key=int)
    programs = sorted(by_distance[distances[0]]["programs"])
    with_model = "model" in by_distance[distances[0]]
    header = ["distance"] + programs + ["room", "room_of"] + (["model"] if with_model else [])
    rows = []
    for d in distances:
        row = by_distance[d]
        line = ([int(d)] + [row["programs_standard_error"][p] for p in programs]
                + [row["room_standard_error"], row["room_standard_error_of"]])
        rows.append(line + ([row["model_standard_error"]] if with_model else []))
    return _table(header, rows)


def model_minus_program_text(by_distance):
    """One row per distance: for each program, the model's mean per-state score minus the program's on the same
    states, and that difference's standard error."""
    distances = sorted(by_distance, key=int)
    programs = sorted(by_distance[distances[0]]["programs"])
    header = ["distance"] + [f"{p}{part}" for p in programs for part in ("", "_se")]
    rows = [[int(d)] + [value for p in programs for value in (by_distance[d]["model_minus_program"][p]["mean"],
                                                              by_distance[d]["model_minus_program"][p]["standard_error"])]
            for d in distances]
    return _table(header, rows)


def budgets_text(by_distance, allowance):
    """Each side's budget in its own units, plus the upper-limit figure: most cubes the thinking could hold.
    Beside the thinking tokens, always, the number of answers without a count, so the table has one shape."""
    distances = sorted(by_distance, key=int)
    searchers = sorted(by_distance[distances[0]].get("positions_examined_mean", {}))
    header = ["distance", "allowance", "thinking_tokens", "without_thinking_count", "tokens_used", "forced",
              "cut_off_readable"]
    header += [f"{s}_positions" for s in searchers] + ["most_cubes_written"]
    rows = []
    for d in distances:
        row = by_distance[d]
        rows.append([int(d), allowance, row["thinking_tokens_mean"], row["answers_without_thinking_count"],
                     row["tokens_used_mean"], row["forced_share"], row["cut_off_but_readable_share"]]
                    + [row["positions_examined_mean"][s] for s in searchers] + [row["most_cubes_written"]])
    return _table(header, rows)


def state_by_state_text(table):
    """For each program, the four counts per distance and the 'only the model' count expected by chance, in
    two forms: if the model guessed, and if the model got states independently of the program (with its
    standard error)."""
    parts = []
    for program in sorted(table):
        rows = [[int(d), r["both"], r["only_model"], r["only_program"], r["neither"],
                 r["only_model_expected_by_chance"], r["only_model_expected_if_independent"],
                 r["only_model_if_independent_standard_error"]]
                for d, r in sorted(table[program].items(), key=lambda item: int(item[0]))]
        parts.append(f"{program}\n" + _table(["distance", "both", "only_model", "only_program", "neither",
                                               "only_model_if_guessing", "only_model_if_independent",
                                               "if_independent_se"], rows))
    return "\n\n".join(parts)


def wrong_turns_text(table):
    """For each program, one row per distance from wrong_turns.py: the cubes with a wrong try and the wrong
    tries behind the figures, the match rate, the uniform and shuffle figures, the excess (match minus
    shuffle) and its standard error, and the excess over each control with its standard error."""
    parts = []
    for program in sorted(table):
        rows_by_distance = sorted(table[program].items(), key=lambda item: int(item[0]))
        controls = sorted(rows_by_distance[0][1]["excess_over_control"])
        header = (["distance", "cubes", "wrong_tries", "match", "uniform", "shuffle", "excess", "excess_se"]
                  + [f"over_{c}{part}" for c in controls for part in ("", "_se")])
        rows = [[int(d), r["cubes"], r["wrong_tries"], r["match_rate"], r["uniform"], r["shuffle"], r["excess"],
                 r["excess_standard_error"]]
                + [value for c in controls for value in (r["excess_over_control"][c]["mean"],
                                                         r["excess_over_control"][c]["standard_error"])]
                for d, r in rows_by_distance]
        parts.append(f"{program}\n" + _table(header, rows))
    return "\n\n".join(parts)


def curve_svg(by_distance, width=720, height=420):
    """Score (0 to 1) against distance, one line per program and, if present, the model's line drawn thicker,
    in black and dashed, so it stands out from the programs. Every point has a bar of one standard error above
    and below (none where a distance has one state); bars are cut at 0 and 1 in the drawing only."""
    distances = sorted(by_distance, key=int)
    names = sorted(by_distance[distances[0]]["programs"])
    series = {name: [(by_distance[d]["programs"][name], by_distance[d]["programs_standard_error"][name])
                     for d in distances] for name in names}
    if "model" in by_distance[distances[0]]:
        series["model"] = [(by_distance[d]["model"], by_distance[d]["model_standard_error"]) for d in distances]
    left, right, top, bottom = 60, 170, 20, 50
    first, last = int(distances[0]), int(distances[-1])

    def x(d):
        return left + (int(d) - first) * (width - left - right) / max(1, last - first)

    def y(score):
        return top + (1 - score) * (height - top - bottom)

    colours = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
               "#bcbd22", "#17becf"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             f'<rect width="{width}" height="{height}" fill="white"/>',
             f'<line x1="{left}" y1="{y(0)}" x2="{x(last)}" y2="{y(0)}" stroke="black"/>',
             f'<line x1="{left}" y1="{y(0)}" x2="{left}" y2="{y(1)}" stroke="black"/>',
             f'<text x="{(left + x(last)) / 2}" y="{height - 10}" text-anchor="middle">distance from solved</text>']
    for tick in (0, 0.25, 0.5, 0.75, 1):
        parts.append(f'<text x="{left - 8}" y="{y(tick) + 4}" text-anchor="end">{tick}</text>')
    for d in distances:
        parts.append(f'<text x="{x(d)}" y="{y(0) + 18}" text-anchor="middle">{int(d)}</text>')
    for n, (name, scores) in enumerate(series.items()):
        is_model = name == "model"
        colour = "#000000" if is_model else colours[n % len(colours)]
        style = 'stroke-width="4" stroke-dasharray="8 4"' if is_model else 'stroke-width="2"'
        points = " ".join(f"{x(d):.1f},{y(s):.1f}" for d, (s, _) in zip(distances, scores))
        parts.append(f'<polyline fill="none" stroke="{colour}" {style} points="{points}"/>')
        for d, (score, error) in zip(distances, scores):
            if error is not None:
                low, high = y(max(0, score - error)), y(min(1, score + error))
                parts.append(f'<line class="error-bar" x1="{x(d):.1f}" y1="{low:.1f}" x2="{x(d):.1f}" y2="{high:.1f}" '
                             f'stroke="{colour}" stroke-width="1"/>')
        label = "MODEL" if is_model else name
        parts.append(f'<text x="{width - right + 10}" y="{top + 16 * n + 10}" fill="{colour}">{escape(label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
