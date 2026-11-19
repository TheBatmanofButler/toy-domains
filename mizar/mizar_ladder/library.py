"""The one place that knows the library's files: every fact and its statement in the library's order, the problem
file of each theorem, the facts each author's proof cites, and Mizar's names for the coded symbols.

The folder is given as a setting. At start the sha256 of each checked file is compared with the values written in
README.md, and a file that differs stops the run. Names of facts are read by rule: `t<number>_<article>` is a
theorem, `l<number>_<article>` a lemma, `d<number>_<article>` a definition, anything else is "other"; the article
is everything after the first underscore, since an article's own name can hold one (`xboole_1`).
"""
import hashlib
import re
from pathlib import Path

# The 33 articles every problem comes from, test and training alike: the articles the library needs for the
# Bolzano-Weierstrass theorem (MPTP2078), in the library's order.
ARTICLES = ("xboole_0", "xboole_1", "enumset1", "zfmisc_1", "subset_1", "setfam_1", "relat_1", "funct_1",
            "ordinal1", "wellord1", "relset_1", "mcart_1", "wellord2", "funct_2", "finset_1", "pre_topc",
            "orders_2", "lattices", "tops_1", "tops_2", "compts_1", "connsp_2", "filter_1", "lattice3",
            "yellow_0", "yellow_1", "waybel_0", "tmap_1", "tex_2", "yellow_6", "waybel_7", "waybel_9",
            "yellow19")

# The three article groups the scores are reported by, as given with the plan.
GROUPS = {
    "sets, relations and functions": ("xboole_0", "xboole_1", "enumset1", "zfmisc_1", "subset_1", "setfam_1",
                                      "relat_1", "funct_1", "ordinal1", "wellord1", "relset_1", "mcart_1",
                                      "wellord2", "funct_2", "finset_1"),
    "orderings and lattices": ("orders_2", "lattices", "filter_1", "lattice3", "yellow_0", "yellow_1", "waybel_0",
                               "yellow_6", "waybel_7", "waybel_9", "yellow19"),
    "topology": ("pre_topc", "tops_1", "tops_2", "compts_1", "connsp_2", "tmap_1", "tex_2"),
}

STATEMENTS, ORDER, REFERENCES, NAMES, PROBLEMS = "statements", "seq", "00mizrefs", "00constrnames", "problems_small_consist"
_KIND = {"t": "theorem", "l": "lemma", "d": "definition"}
_NAMED = re.compile(r"([tld])\d+_.+")
_FOF = re.compile(r"fof\(([^,]+), (\w+),(.*)\)\.\s*")
# A row of the checksum table in README.md: | `file` | `sha256` |
_CHECKSUM_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE)


class LibraryError(Exception):
    pass


def article(name):
    """Everything after the first underscore of a fact's name."""
    if "_" not in name:
        raise LibraryError(f"{name!r} has no article in its name")
    return name.split("_", 1)[1]


def kind(name):
    """"theorem", "lemma", "definition" or "other", read from the name."""
    found = _NAMED.fullmatch(name)
    return _KIND[found.group(1)] if found else "other"


def group(article_name):
    """Which of the three groups one of the 33 articles is in; None for any other article."""
    for name, articles in GROUPS.items():
        if article_name in articles:
            return name
    return None


def readme_checksums(readme):
    """{file name: sha256} from the checksum table in README.md."""
    return dict(_CHECKSUM_ROW.findall(Path(readme).read_text()))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_fof(line):
    """(name, role, formula) of one `fof(name, role, formula).` line; the white space around the formula is not
    part of it."""
    found = _FOF.fullmatch(line)
    if not found:
        raise LibraryError(f"not a fof line: {line[:120]!r}")
    return found.group(1), found.group(2), found.group(3).strip()


class Library:
    """The library's files in `folder`. `checksums` is {file name: sha256}; by default the table in README.md."""

    def __init__(self, folder, checksums=None):
        self.folder = Path(folder)
        if checksums is None:
            checksums = readme_checksums(Path(__file__).resolve().parent.parent / "README.md")
        if not checksums:
            raise LibraryError("no checksums to check the library's files against")
        for name, expected in sorted(checksums.items()):
            found = sha256(self.folder / name)
            if found != expected:
                raise LibraryError(f"{name}: sha256 {found}, README.md says {expected}; stopping")
        self._order = [line.strip() for line in open(self.folder / ORDER) if line.strip()]
        self._position = {name: n for n, name in enumerate(self._order)}
        if len(self._position) != len(self._order):
            raise LibraryError("a fact is listed twice in the library's order")
        self._statements = {}
        for line in open(self.folder / STATEMENTS):
            if line.strip():
                name, _, formula = parse_fof(line.strip())
                self._statements[name] = formula
        if set(self._statements) != set(self._position):
            raise LibraryError("the statements and the library's order do not name the same facts")
        self._references = {}
        for line in open(self.folder / REFERENCES):
            if line.strip():
                theorem, cited = line.rstrip("\n").split(":", 1)
                # Repeats are kept out: a fact cited twice is one cited fact.
                self._references[theorem] = list(dict.fromkeys(name for name in cited.split(",") if name))
        self._theorems = self._find_theorems()
        self._theorem_order = sorted(self._theorems, key=self._position.__getitem__)

    def _find_theorems(self):
        """{theorem: its article folder}, from the problem files: one sub-folder per article, one file per theorem
        named `<article>__<theorem>`. Plain files at the top of the folder are not problems."""
        found = {}
        for folder in sorted(p for p in (self.folder / PROBLEMS).iterdir() if p.is_dir()):
            for path in folder.iterdir():
                prefix, _, theorem = path.name.partition("__")
                if prefix != folder.name or article(theorem) != folder.name or theorem not in self._position:
                    raise LibraryError(f"unexpected problem file {path}")
                found[theorem] = folder.name
        return found

    def facts(self):
        """Every fact's (name, statement), in the library's order."""
        return [(name, self._statements[name]) for name in self._order]

    def statement(self, name):
        return self._statements[name]

    def position(self, name):
        return self._position[name]

    def theorems(self, articles=None):
        """The theorems (facts with a problem file), in the library's order; only those of `articles` if given."""
        return [n for n in self._theorem_order if articles is None or self._theorems[n] in articles]

    def articles(self):
        """Every article that has a problem file, in the library's order."""
        first = {}
        for theorem in self.theorems():
            first.setdefault(self._theorems[theorem], self._position[theorem])
        return sorted(first, key=first.__getitem__)

    def problem_file(self, theorem):
        """(the theorem's statement, the names of the other facts in its problem file in the file's order)."""
        path = self.folder / PROBLEMS / self._theorems[theorem] / f"{self._theorems[theorem]}__{theorem}"
        statement, names = None, []
        for line in open(path):
            if line.startswith("%") or not line.strip():
                continue
            name, role, formula = parse_fof(line.strip())
            if role == "conjecture":
                if name != theorem or statement is not None:
                    raise LibraryError(f"{path}: conjecture {name}, expected {theorem} once")
                statement = formula
            else:
                names.append(name)
        if statement is None:
            raise LibraryError(f"{path}: no conjecture")
        return statement, names

    def cited(self, theorem):
        """The different facts the author's proof refers to, in order of first mention."""
        if theorem not in self._references:
            raise LibraryError(f"{theorem} has no line in the file of references")
        return list(self._references[theorem])

    def references(self):
        """{theorem: its cited facts} for every line of the file of references."""
        return {theorem: list(cited) for theorem, cited in self._references.items()}

    def mizar_names(self):
        """{coded symbol: the name the library gives it}; the first one listed when there are several."""
        names = {}
        for line in open(self.folder / NAMES):
            if line.strip():
                symbol, name = line.split()
                names.setdefault(symbol, name)
        return names
