"""The text the model is shown for one problem.

One sentence on the notation (for a renamed problem, one that says each symbol has been replaced by a code), the
theorem, the given facts numbered G1, G2 and so on, the 30 options numbered 1 to
30 in the problem's order, and the last paragraph as written in mizar_plan.md. Statements are shown as stage 1
saved them (statements.show); no fact's name, no article's name and nothing about which option is right is put in
by this file: every option is written the same way.
"""
SYSTEM_TEXT = "You are an expert mathematician. Follow the requested answer format exactly."

NOTATION = ("Statements are written in first-order logic in the provers' notation (! for all, ? for there exists, "
            "& and, | or, ~ not, => implies, <=> if and only if), with each symbol written as its name in the "
            "Mizar Mathematical Library.")
# The renamed problems' first sentence: the same, but for its end.
NOTATION_RENAMED = NOTATION.replace(
    "with each symbol written as its name in the Mizar Mathematical Library.",
    "with each symbol of the Mizar Mathematical Library replaced by a meaningless code, the same code wherever the "
    "symbol appears.")
HEADINGS = ("Theorem:", "Given facts:", "Options:")
RULE = ("Exactly one of these facts is cited in the author's proof of the theorem, together with the given facts. "
        "Give its number. Answer with `FACT: <number>`.")


def build_question(problem):
    given = "\n".join(f"G{n}. {fact['statement']}" for n, fact in enumerate(problem["given"], 1))
    options = "\n".join(f"{n}. {option['statement']}" for n, option in enumerate(problem["options"], 1))
    return (f"{NOTATION_RENAMED if problem.get('renamed') else NOTATION}\n\n"
            f"Theorem:\n{problem['statement']}\n\n"
            f"Given facts:\n{given}\n\n"
            f"Options:\n{options}\n\n"
            f"{RULE}")
