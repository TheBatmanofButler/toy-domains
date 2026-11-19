"""The settings every answer was asked under, which the report shows once for the whole run.

The report sets the model's thinking beside one allowance, so all answers must share it, and the other
settings that change what the model writes: the answer allowance, the stop sentence, the sampling values and
the model version. If any differ the figures would mix answers asked in different ways, so this stops and
says what differs and how many answers have each value, rather than showing the first answer's settings.
"""
import json

# Where each compared value sits in a saved answer: under "settings", except the model version.
COMPARED = ("thinking_allowance", "answer_allowance", "stop_sentence", "sampling", "model_version")


class SettingsDiffer(Exception):
    pass


def _value(answer, name):
    return answer["model_version"] if name == "model_version" else answer["settings"][name]


def shared_settings(answers):
    """{name: value} for every compared setting, when all answers share it; otherwise SettingsDiffer, naming
    each setting that differs with every value and its number of answers."""
    if not answers:
        raise SettingsDiffer("no answers to read the settings from")
    shared, problems = {}, []
    for name in COMPARED:
        # The sampling values are a dictionary: written out with sorted keys, equal values compare equal.
        counts = {}
        for answer in answers:
            key = json.dumps(_value(answer, name), sort_keys=True)
            counts[key] = counts.get(key, 0) + 1
        if len(counts) == 1:
            shared[name] = _value(answers[0], name)
        else:
            values = ", ".join(f"{key} ({count} answer{'s' * (count != 1)})" for key, count in sorted(counts.items()))
            problems.append(f"{name}: {values}")
    if problems:
        raise SettingsDiffer("the answers were not all asked under the same settings; " + "; ".join(problems))
    return shared
