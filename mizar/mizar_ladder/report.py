"""Writes the report's tables as text and draws each program's and the model's score as bars in an SVG picture.

No figure is worked out here: every number comes from scoring.py (and, for the same-wrong-answers table, from
wrong_answers.py; for the programs counted together, from together.py). Every table has one row for all problems,
then rows by number of cited facts and by article group, in the order scoring.py gives them. The picture is drawn
by hand as SVG so that no plotting library is needed.
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


def scores_text(by_row):
    """One line per row: each program, the best programs (ties joined by +), room, and the model's figures."""
    names = list(by_row)
    programs = sorted(by_row[names[0]]["programs"])
    with_model = "model" in by_row[names[0]]
    header = ["row", "problems"] + programs + ["best", "room"]
    if with_model:
        header += ["model", "unreadable", "forced", "thinking_tokens"]
    rows = []
    for name in names:
        row = by_row[name]
        line = ([name, row["problems"]] + [row["programs"][p] for p in programs]
                + ["+".join(row["best_programs"]), row["room"]])
        if with_model:
            line += [row["model"], row["unreadable_share"], row["forced_share"], row["thinking_tokens_mean"]]
        rows.append(line)
    return _table(header, rows)


def standard_errors_text(by_row):
    """One line per row: the standard error of each program's score, of room (the best program's, named), and
    of the model's score. n/a where a row has one problem."""
    names = list(by_row)
    programs = sorted(by_row[names[0]]["programs"])
    with_model = "model" in by_row[names[0]]
    header = ["row"] + programs + ["room", "room_of"] + (["model"] if with_model else [])
    rows = []
    for name in names:
        row = by_row[name]
        line = ([name] + [row["programs_standard_error"][p] for p in programs]
                + [row["room_standard_error"], row["room_standard_error_of"]])
        rows.append(line + ([row["model_standard_error"]] if with_model else []))
    return _table(header, rows)


def model_minus_program_text(by_row):
    """One line per row: for each program, the model's mean per-problem score minus the program's on the same
    problems, and that difference's standard error."""
    names = list(by_row)
    programs = sorted(by_row[names[0]]["programs"])
    header = ["row"] + [f"{p}{part}" for p in programs for part in ("", "_se")]
    rows = [[name] + [value for p in programs for value in (by_row[name]["model_minus_program"][p]["mean"],
                                                            by_row[name]["model_minus_program"][p]["standard_error"])]
            for name in names]
    return _table(header, rows)


def budgets_text(by_row, allowance):
    """The model's budget and its use. Beside the thinking tokens, always, the number of answers without a
    count, so the table has one shape."""
    header = ["row", "allowance", "thinking_tokens", "without_thinking_count", "tokens_used", "forced",
              "cut_off_readable"]
    rows = []
    for name, row in by_row.items():
        rows.append([name, allowance, row["thinking_tokens_mean"], row["answers_without_thinking_count"],
                     row["tokens_used_mean"], row["forced_share"], row["cut_off_but_readable_share"]])
    return _table(header, rows)


def problem_by_problem_text(table):
    """For each program, the four counts per row and the 'only the model' count expected by chance, in two
    forms: if the model guessed, and if the model got problems independently of the program (with its standard
    error)."""
    parts = []
    for program in sorted(table):
        rows = [[name, r["both"], r["only_model"], r["only_program"], r["neither"],
                 r["only_model_expected_by_chance"], r["only_model_expected_if_independent"],
                 r["only_model_if_independent_standard_error"]]
                for name, r in table[program].items()]
        parts.append(f"{program}\n" + _table(["row", "both", "only_model", "only_program", "neither",
                                               "only_model_if_guessing", "only_model_if_independent",
                                               "if_independent_se"], rows))
    return "\n\n".join(parts)


def together_text(table):
    """One line per row from together.py: the problems, how many the best single program gets (and which, ties
    joined by +), how many at least one program gets, how many none gets; with the model, how many of each of the
    last two it gets."""
    names = list(table)
    with_model = "model_gets_of_at_least_one_program" in table[names[0]]
    header = ["row", "problems", "best_single", "best_programs", "at_least_one", "none"]
    if with_model:
        header += ["model_of_at_least_one", "model_of_none"]
    rows = []
    for name in names:
        r = table[name]
        line = [name, r["problems"], r["best_single_program"], "+".join(r["best_single_programs"]),
                r["at_least_one_program"], r["no_program"]]
        if with_model:
            line += [r["model_gets_of_at_least_one_program"], r["model_gets_of_no_program"]]
        rows.append(line)
    return _table(header, rows)


def wrong_answers_text(table):
    """For each program, one line per row from wrong_answers.py: the problems with a wrong try and the wrong
    tries behind the figures, the match rate, the uniform and shuffle figures, the excess (match minus shuffle)
    and its standard error, and the excess over each control with its standard error."""
    parts = []
    for program in sorted(table):
        rows_in_order = list(table[program].items())
        controls = sorted(rows_in_order[0][1]["excess_over_control"])
        header = (["row", "problems", "wrong_tries", "match", "uniform", "shuffle", "excess", "excess_se"]
                  + [f"over_{c}{part}" for c in controls for part in ("", "_se")])
        rows = [[name, r["problems"], r["wrong_tries"], r["match_rate"], r["uniform"], r["shuffle"], r["excess"],
                 r["excess_standard_error"]]
                + [value for c in controls for value in (r["excess_over_control"][c]["mean"],
                                                         r["excess_over_control"][c]["standard_error"])]
                for name, r in rows_in_order]
        parts.append(f"{program}\n" + _table(header, rows))
    return "\n\n".join(parts)


def bars_svg(by_row, row="all problems", width=720, height=420):
    """Score (0 to 1) in one row, one bar per program and, if present, the model's bar in black, so it stands
    out from the programs. Every bar has a line of one standard error above and below its top (none where the
    row has one problem); the lines are cut at 0 and 1 in the drawing only."""
    figures = by_row[row]
    series = {name: (figures["programs"][name], figures["programs_standard_error"][name])
              for name in sorted(figures["programs"])}
    if "model" in figures:
        series["model"] = (figures["model"], figures["model_standard_error"])
    left, right, top, bottom = 60, 20, 20, 90
    slot = (width - left - right) / len(series)

    def y(score):
        return top + (1 - score) * (height - top - bottom)

    colours = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
               "#bcbd22", "#17becf"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             f'<rect width="{width}" height="{height}" fill="white"/>',
             f'<line x1="{left}" y1="{y(0)}" x2="{width - right}" y2="{y(0)}" stroke="black"/>',
             f'<line x1="{left}" y1="{y(0)}" x2="{left}" y2="{y(1)}" stroke="black"/>',
             f'<text x="{(left + width - right) / 2}" y="{height - 10}" text-anchor="middle">{escape(row)}</text>']
    for tick in (0, 0.25, 0.5, 0.75, 1):
        parts.append(f'<text x="{left - 8}" y="{y(tick) + 4}" text-anchor="end">{tick}</text>')
    for n, (name, (score, error)) in enumerate(series.items()):
        is_model = name == "model"
        colour = "#000000" if is_model else colours[n % len(colours)]
        x = left + n * slot + slot * 0.15
        parts.append(f'<rect class="bar" x="{x:.1f}" y="{y(score):.1f}" width="{slot * 0.7:.1f}" '
                     f'height="{y(0) - y(score):.1f}" fill="{colour}"/>')
        middle = x + slot * 0.35
        if error is not None:
            low, high = y(max(0, score - error)), y(min(1, score + error))
            parts.append(f'<line class="error-bar" x1="{middle:.1f}" y1="{low:.1f}" x2="{middle:.1f}" y2="{high:.1f}" '
                         f'stroke="#555555" stroke-width="1"/>')
        label = "MODEL" if is_model else name
        parts.append(f'<text x="{middle:.1f}" y="{y(0) + 18}" text-anchor="middle" fill="{colour}">{escape(label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def second_table_text(table):
    """The second table (second_table.py): the four prover bins, then over the problems with right options under
    the prover's key, every program's and the model's score under each key with its standard error, the model
    minus each program, and how the keys relate."""
    keys = ("prover", "either", "author")
    header = ["", *[f"{k}{part}" for k in keys for part in ("", "_se")]]

    def line(name, figures):
        return [name] + [value for k in keys for value in (figures[k]["mean"], figures[k]["standard_error"])]
    scores = [line(name, figures) for name, figures in table["programs"].items()] + [line("model", table["model"])]
    minus = [line(name, figures) for name, figures in table["model_minus_program"].items()]
    bins = ", ".join(f"{name} {count}" for name, count in table["bins"].items())
    return "\n\n".join([
        f"Prover bins: {bins}; the prover's two runs disagreed on {_cell(table['runs_disagreed_share'])} of the "
        f"calls. The table is over the {table['problems']} problems with right options.",
        "Scores under the prover's key, under either key, and under the author's key\n" + _table(header, scores),
        "Model minus each program on the same problems\n" + _table(header, minus),
        f"Held-back option right under the prover's key: {_cell(table['held_back_right_share'])}; other options "
        f"right under it, per problem: {_cell(table['other_right_mean'])}; option calls that proved the theorem "
        f"without the option in the proof: {table['proved_without_use_calls']}"])


def renamed_text(table):
    """Named against renamed (renaming.py): per row, the model named and renamed with standard errors, the drop
    with its standard error, the shares of paired tries right under both, named only, renamed only and neither,
    and the forced share and mean thinking tokens under each; then the renamed model minus each program."""
    header = ["row", "problems", "named", "named_se", "renamed", "renamed_se", "drop", "drop_se", "both",
              "named_only", "renamed_only", "neither", "forced_named", "forced_renamed", "thinking_named",
              "thinking_renamed"]
    rows = [[name, r["problems"], r["model_named"], r["model_named_standard_error"], r["model_renamed"],
             r["model_renamed_standard_error"], r["drop"]["mean"], r["drop"]["standard_error"], r["both_right"],
             r["named_only"], r["renamed_only"], r["neither"], r["forced_share_named"], r["forced_share_renamed"],
             r["thinking_tokens_named"], r["thinking_tokens_renamed"]] for name, r in table.items()]
    first = next(iter(table.values()))
    programs = sorted(first["renamed_minus_program"])
    minus_header = ["row"] + [f"{p}{part}" for p in programs for part in ("", "_se")]
    minus = [[name] + [value for p in programs for value in (r["renamed_minus_program"][p]["mean"],
                                                             r["renamed_minus_program"][p]["standard_error"])]
             for name, r in table.items()]
    return "\n\n".join([_table(header, rows), "Renamed model minus each program, per-problem difference on the "
                        "same problems: mean, then standard error\n" + _table(minus_header, minus)])


def two_allowances_text(table):
    """The renamed model at the named run's thinking allowance and at another (renaming.two_allowances): per row,
    each score with its standard error, the difference with its standard error, the four shares of paired tries,
    and the forced share and mean thinking tokens under each."""
    header = ["row", "problems", "at_named", "at_named_se", "at_other", "at_other_se", "difference",
              "difference_se", "both", "named_only", "other_only", "neither", "forced_named", "forced_other",
              "thinking_named", "thinking_other"]
    rows = [[name, r["problems"], r["at_named_allowance"], r["at_named_allowance_standard_error"],
             r["at_other_allowance"], r["at_other_allowance_standard_error"], r["difference"]["mean"],
             r["difference"]["standard_error"], r["both_right"], r["named_allowance_only"],
             r["other_allowance_only"], r["neither"], r["forced_share_named_allowance"],
             r["forced_share_other_allowance"], r["thinking_tokens_named_allowance"],
             r["thinking_tokens_other_allowance"]] for name, r in table.items()]
    return _table(header, rows)
