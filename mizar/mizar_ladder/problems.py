"""Builds the problems: every theorem of the 33 articles put in one bin, 300 of the qualifying ones drawn as test
problems, and all the other qualifying ones as training problems, from the library's files and the seed. Nothing
is built from any other article.

A theorem is usable when its author cites at least two different facts, at least one of them a theorem or lemma
that can be held back: one that reads differently from every other cited fact and from the theorem. A theorem with
no such fact is not usable. One of them is held back, drawn with a generator made from the seed and the theorem's
name. Its neighbours are the theorems and lemmas of its own article stated before the theorem, not cited by it,
and not the same statement as it, as the theorem or as any fact the theorem cites; of several with one statement,
only the first in the library's order. "The same statement" is judged twice, on the statement and on the text the
solver is shown (Mizar gives one name to several symbols), each time up to the names of the variables and the
order of each quantifier's list (statements.canonical). So no two options read the same and none repeats a given
fact or the theorem. With 29 or more neighbours the theorem qualifies; 29 of them and the held-back fact, in an
order set by the seed and the theorem's name, are the problem's 30 options. Every check here stops the build with
a message.
"""
import json
import random

from mizar_ladder import statements
from mizar_ladder.library import ARTICLES, article, group, kind

OPTIONS = 30
NOT_USABLE, TOO_FEW, QUALIFIES = "not usable", "too few neighbours", "qualifies"
BINS = (NOT_USABLE, TOO_FEW, QUALIFIES)


class BuildError(Exception):
    pass


def write_jsonl(path, records):
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def is_theorem_or_lemma(name):
    return kind(name) in ("theorem", "lemma")


class Builder:
    """What the build needs from the library, read once: the theorems and lemmas of each article in the library's
    order, and each fact's two keys: its statement with its variables renamed, and its shown text likewise."""

    def __init__(self, library, seed):
        self.library = library
        self.seed = seed
        self.names = library.mizar_names()
        self.by_article = {}
        for name, _ in library.facts():
            if is_theorem_or_lemma(name):
                self.by_article.setdefault(article(name), []).append(name)
        self._keys = {}

    def keys(self, name):
        """{the statement with its variables renamed, the shown text with them renamed}: a fact reads the same
        as another when they share a key."""
        if name not in self._keys:
            self._keys[name] = fact_keys(self.library.statement(name), self.names)
        return self._keys[name]

    def neighbours(self, theorem, fact, cited):
        """The theorems and lemmas of `fact`'s article stated before `theorem` and not cited by it, that read
        differently from `fact`, the theorem, every cited fact and every neighbour found before them; in the
        library's order."""
        before = self.library.position(theorem)
        taken = set().union(*(self.keys(n) for n in [fact, theorem, *cited]))
        found = []
        for n in self.by_article.get(article(fact), []):
            if self.library.position(n) >= before:
                break
            if n not in cited and not self.keys(n) & taken:
                taken |= self.keys(n)
                found.append(n)
        return found

    def can_be_held_back(self, theorem, cited):
        """The cited theorems and lemmas that read differently from every other cited fact and the theorem."""
        return [c for c in cited if is_theorem_or_lemma(c) and not self.keys(c) & set().union(
            *(self.keys(n) for n in [theorem, *cited] if n != c))]

    def check_cited(self, theorem, cited):
        """Every cited fact is in the theorem's problem file and is stated earlier than the theorem."""
        _, in_file = self.library.problem_file(theorem)
        in_file = set(in_file)
        for fact in cited:
            if fact == theorem:
                raise BuildError(f"{theorem}: it cites itself")
            if fact not in in_file:
                raise BuildError(f"{theorem}: cited fact {fact} is not in its problem file")
            if self.library.position(fact) >= self.library.position(theorem):
                raise BuildError(f"{theorem}: cited fact {fact} is stated after it")

    def classify(self, theorem):
        """The theorem's line for theorems.jsonl: its name, article, cited facts, bin, held-back fact and
        number of neighbours (the last two empty when not usable)."""
        cited = self.library.cited(theorem)
        self.check_cited(theorem, cited)
        record = {"theorem": theorem, "article": article(theorem), "cited": cited, "bin": NOT_USABLE,
                  "held_back": None, "neighbour_count": None}
        candidates = self.can_be_held_back(theorem, cited)
        if len(cited) < 2 or not candidates:
            return record
        held_back = random.Random(f"{self.seed}:{theorem}:held back").choice(candidates)
        count = len(self.neighbours(theorem, held_back, cited))
        record.update(held_back=held_back, neighbour_count=count,
                      bin=QUALIFIES if count >= OPTIONS - 1 else TOO_FEW)
        return record

    def problem(self, record, problem_id):
        """The problem for a qualifying theorem's record: 29 neighbours drawn and the 30 options put in order,
        both with a generator made from the seed and the theorem's name."""
        theorem, held_back, cited = record["theorem"], record["held_back"], record["cited"]
        rng = random.Random(f"{self.seed}:{theorem}:options")
        options = [held_back] + rng.sample(self.neighbours(theorem, held_back, cited), OPTIONS - 1)
        rng.shuffle(options)
        problem = {"id": problem_id, "theorem": theorem, "article": record["article"],
                   "statement": self.shown(theorem),
                   "given": [{"name": n, "statement": self.shown(n)} for n in cited if n != held_back],
                   "options": [{"name": n, "statement": self.shown(n)} for n in options],
                   "held_back": options.index(held_back) + 1, "cited_count": len(cited),
                   "group": group(record["article"]), "seed": self.seed}
        check_problem(problem, self.library, cited, held_back, self.names)
        return problem

    def shown(self, name):
        return statements.show(self.library.statement(name), self.names)


def fact_keys(statement, names):
    """A fact's two keys (see Builder.keys)."""
    return {("statement", tuple(statements.renamed(statement))), ("shown", statements.shown_key(statement, names))}


def check_problem(problem, library, cited, held_back, names=None):
    """The checks on one problem that stop the build. `names` is the Mizar name table (read if not given)."""
    names = library.mizar_names() if names is None else names
    theorem = problem["theorem"]
    options = [o["name"] for o in problem["options"]]
    if len(options) != OPTIONS or len(set(options)) != OPTIONS:
        raise BuildError(f"{theorem}: {len(set(options))} different options, not {OPTIONS}")
    if options[problem["held_back"] - 1] != held_back:
        raise BuildError(f"{theorem}: option {problem['held_back']} is not the held-back fact {held_back}")
    if held_back in [g["name"] for g in problem["given"]]:
        raise BuildError(f"{theorem}: the held-back fact {held_back} is among the given facts")
    for name in options:
        if library.position(name) >= library.position(theorem):
            raise BuildError(f"{theorem}: option {name} is stated after the theorem")
        if name != held_back and name in cited:
            raise BuildError(f"{theorem}: wrong option {name} is cited by the author")
    keys = {name: fact_keys(library.statement(name), names) for name in options}
    for n, one in enumerate(options):
        for other in options[n + 1:]:
            if keys[one] & keys[other]:
                raise BuildError(f"{theorem}: options {one} and {other} read the same")
    for given in [theorem] + [g["name"] for g in problem["given"]]:
        theirs = fact_keys(library.statement(given), names)
        for name in options:
            if keys[name] & theirs:
                raise BuildError(f"{theorem}: option {name} reads the same as {given}")


def check_bins(records, theorems):
    """Every theorem in `theorems` is in exactly one bin, and nothing else is binned."""
    counts = {}
    for record in records:
        if record["bin"] not in BINS:
            raise BuildError(f"{record['theorem']}: unknown bin {record['bin']!r}")
        counts[record["theorem"]] = counts.get(record["theorem"], 0) + 1
    twice = sorted(t for t, n in counts.items() if n > 1)
    missing = sorted(set(theorems) - set(counts))
    extra = sorted(set(counts) - set(theorems))
    if twice or missing or extra:
        raise BuildError(f"theorems in two bins {twice[:5]}, in no bin {missing[:5]}, not of the articles {extra[:5]}")


def check_sets(test, train, test_count, articles):
    """The checks on the two sets as a whole."""
    if len(test) != test_count:
        raise BuildError(f"{len(test)} test problems, not exactly {test_count}")
    outside = [p["theorem"] for p in train
               if p["article"] not in articles or article(p["theorem"]) not in articles]
    if outside:
        raise BuildError(f"training problems whose theorem is not of the articles: {outside[:5]}")
    shared = {p["theorem"] for p in test} & {p["theorem"] for p in train}
    if shared:
        raise BuildError(f"theorems in both sets: {sorted(shared)[:5]}")


def build(library, seed, test_count=300, articles=ARTICLES):
    """(theorem records of the articles, test problems, training problems). The test problems are `test_count`
    qualifying theorems of the articles drawn with the seed; the training problems are all the other qualifying
    theorems of the articles, built the same way. Nothing is built from any other article.
    Both sets are numbered in the library's order."""
    builder = Builder(library, seed)
    theorems = library.theorems(set(articles))
    records = [builder.classify(t) for t in theorems]
    check_bins(records, theorems)
    qualifying = [r for r in records if r["bin"] == QUALIFIES]
    if len(qualifying) < test_count:
        raise BuildError(f"{len(qualifying)} qualifying theorems, fewer than {test_count}")
    drawn = set(random.Random(f"{seed}:test set").sample([r["theorem"] for r in qualifying], test_count))
    for record in records:
        record["test"] = record["theorem"] in drawn
    test = [builder.problem(r, f"test-{n:04d}") for n, r in enumerate((r for r in qualifying if r["test"]), 1)]
    train = [builder.problem(r, f"train-{n:04d}") for n, r in enumerate((r for r in qualifying if not r["test"]), 1)]
    check_sets(test, train, test_count, articles)
    return records, test, train
