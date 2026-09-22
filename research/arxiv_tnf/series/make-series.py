#!/usr/bin/env python3
"""Generate the Trinity S3AI paper series from the single source manuscript.

The series is three documents cut from one 7,924-line source:

  A  paper-a-methodology  How a comparison fails      (the transferable result)
  B  paper-b-format       Ternary Network Floats      (the format result)
  C  paper-c-record       the full record version     (everything, unchanged)

This script is the ONLY place the cut is written down. Line ranges, the canon
plate conversion, and the cross-paper reference table all live here, so that a
change to the cut is one edit and not three.

Cross-paper references are the reason this is a program and not a shell
pipeline. A \\ref whose \\label went to a different document renders as ?? and
the build still exits 0, so the split silently degrades the text. Every such
reference is rewritten here into a NAMED pointer -- "the hardware section of the
companion paper" -- and any label this table does not cover is reported as an
error rather than left to the log.

Usage:  python3 make-series.py [--check]
        --check  regenerate into memory and fail if the files on disk differ
"""

import re
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE.parent / "tnf_paper.tex"

# --- the cut -----------------------------------------------------------------
# Half-open line ranges into tnf_paper.tex, in the order they appear in the
# generated body. Each range is a whole \section or a run of them.

RANGES = {
    "a": [
        (1225, 1289),   # The comparison at matched physical width
        (1372, 1428),   # Two width defects, and why they generalise
        (5721, 6082),   # How a comparison fails while every measurement is correct
        (6082, 6195),   # Adjacent work this paper is measured against
        (6195, 6272),   # What the formal statements are, and what they are
        (6272, 6735),   # Three results added in this revision
        (7500, 7632),   # Limitations
        (7632, 7660),   # Reproducibility, Disclosure
    ],
    "b": [
        (442, 476),     # The format
        (476, 576),     # Why a ladder, and why this one
        (576, 994),     # The law is general, and it measures tapering
        (994, 1074),    # Accuracy
        (1074, 1225),   # The 16-bit field
        (1289, 1372),   # Hardware
        (1468, 1631),   # What the law says about improving the ladder
        (1631, 1902),   # Why ternary, and exactly how much
        (3460, 3749),   # Two formats close a ternary node
        (4215, 4671),   # Fineness costs registers, not adders
    ],
}

# Paper C is the record: the whole body, cut nowhere.
RANGES["c"] = [(176, 7660)]

# The record version keeps the manuscript's own abstract, which is where the
# budget convention is declared and labelled. A and B state their own.
ABSTRACT_RANGE = (82, 174)

TITLES = {
    "a": "How a Comparison Fails",
    "b": "Ternary Network Floats",
    "c": "Ternary Network Floats (record version)",
}

# Which document each paper points at when a reference leaves it. The record
# version holds every section, so it is the backstop for both.
COMPANION = {"a": "b", "b": "a", "c": None}

# --- cross-paper reference table ---------------------------------------------
# label -> (destination paper, noun phrase). The phrase is written lowercase;
# it is capitalised automatically at the start of a sentence.

POINTERS = {
    # Paper A referring into Paper B
    "sec:catalogue":    ("b", "the taper-catalogue section"),
    "sec:hardware":     ("b", "the hardware section"),
    "sec:closure":      ("b", "the closure section"),
    "sec:whyternary":   ("b", "the enumeration section"),
    "sec:accuracy":     ("b", "the accuracy section"),
    "tab:acc":          ("b", "the accuracy table"),
    "tab:closure":      ("b", "the closure table"),
    "tab:hierarchy":    ("b", "the hierarchy table"),
    "tab:ladder":       ("b", "the routed-ladder table"),
    "tab:law":          ("b", "the value-law table"),
    "tab:spec":         ("b", "the specification table"),
    "thm:economy":      ("b", "the economy theorem"),
    "thm:lucas-trace":  ("b", "the Lucas-trace theorem"),
    "thm:nofree":       ("b", "the no-free-lunch theorem"),
    "thm:packing-density": ("b", "the packing-density theorem"),
    # Paper B referring into Paper A
    "sec:matchedwidth": ("a", "the matched-width section"),
    "tab:accphys":      ("a", "the equal-storage accuracy table"),
    "thm:rangeperbit":  ("a", "the range-per-bit theorem"),
    # Both papers referring into the record version
    "cor:phi-ratio-bound":       ("c", "the $\\varphi$-ratio bound"),
    "lem:phi-rounding-envelope": ("c", "the $\\varphi$-rounding-envelope lemma"),
    "prop:phi-product-negative": ("c", "the negative-product proposition"),
    "cor:zeropath":              ("c", "the zero-path corollary"),
    "thm:barrelrange":           ("c", "the barrel-range theorem"),
    "thm:boundary":              ("c", "the boundary theorem"),
    "thm:geoscale":              ("c", "the geometric-scale theorem"),
    "thm:radixopt":              ("c", "the optimal-radix theorem"),
    "thm:taperdelay":            ("c", "the taper-delay theorem"),
    "cor:three":                 ("c", "the three-currencies corollary"),
    "tab:window":                ("c", "the crossover-window table"),
    "sec:cleantable":            ("c", "the crossover section"),
    "sec:scaleapplier":          ("c", "the scale-applier section"),
    "sec:window":                ("c", "the applicability section"),
    "sec:codes":                 ("c", "the universal-code section"),
    "tab:fullthroughput":        ("c", "the full-throughput table"),
    "tab:rejected":              ("c", "the rejected-format table"),
    "tab:tnet":                  ("c", "the T-Net table"),
}

# --- passages that a mechanical substitution would wreck ----------------------
# Two places reference half a dozen labels in one breath. Expanding each into
# its own named pointer would print the destination six times in four lines.
# They are rewritten whole, once, here.

REWRITES = {
    "a": [
        # The taxonomy of formal statements: a list mixing labels that stay in
        # this paper with labels that do not.
        (
            "Theorem~\\ref{thm:economy}, Theorem~\\ref{thm:nofree},\n"
            "Theorem~\\ref{thm:packing-density}, Theorem~\\ref{thm:lucas-trace},\n"
            "Lemma~\\ref{lem:phi-rounding-envelope}, Corollary~\\ref{cor:phi-ratio-bound} and\n"
            "Proposition~\\ref{prop:phi-product-negative} are of this kind.",
            "The economy, no-free-lunch, packing-density and Lucas-trace theorems of\n"
            "\\companionname, and the $\\varphi$-rounding-envelope lemma, the\n"
            "$\\varphi$-ratio bound and the negative-product proposition of \\recordname,\n"
            "are of this kind.",
        ),
        # The provenance column of the untraced-figures table. Sixteen rows each
        # naming a table in another document: the pointer goes in the caption
        # once, and the cells carry bare names.
        (
            "strict registry. Each is retained and marked $^{\\ast}$ at every point of use, and",
            "strict registry. Table and theorem names in the middle column refer to\n"
            "\\recordname, where the full twenty-one-row experiment is tabulated. Each figure\n"
            "is retained and marked $^{\\ast}$ at every point of use, and",
        ),
    ],
    "b": [],
    "c": [],
}

# Inside the untraced-figures table the cells are rewritten to bare names, since
# the caption now carries the destination. Applied only within that table.
TABLE_CELL_NAMES = {
    "tab:fullthroughput": "full-throughput table",
    "tab:tnet": "T-Net table",
    "tab:rejected": "rejected-format table",
    "tab:hierarchy": "hierarchy table",
    "thm:barrelrange": "barrel-range theorem",
}

REF_WORDS = r"Sections?|Tables?|Theorems?|Lemmas?|Corollary|Corollaries|Propositions?|Equations?"


def read_source():
    return SOURCE.read_text(encoding="utf-8").split("\n")


def extract(src, ranges):
    out = []
    for a, b in ranges:
        chunk = src[a - 1:b - 1]
        head = chunk[0].strip() if chunk else ""
        name = re.sub(r"\\section\*?\{", "", head)
        name = re.sub(r"\\label\{[^}]*\}", "", name).rstrip().rstrip("}")
        out.append(f"% ---- tnf_paper.tex lines {a}-{b - 1}: {name} ----")
        out.extend(chunk)
        out.append("")
    return "\n".join(out)


def to_triptych(text):
    """Rewrite canon figure environments into the \\triptych plate.

    The plates are three-panel engravings and every one of them is set the same
    way. Leaving 31 copies of the same five lines in the bodies means the next
    change to the plate format reaches whichever copies someone remembers.
    """
    pattern = re.compile(
        r"\\begin\{figure\}\[[^\]]*\]\\centering\s*\n"
        r"\\includegraphics\[width=\\textwidth\]\{canon/([^}]+)\}\s*\n"
        r"\\caption\{Canon plate\.\s*(.*?)\}\s*\n"
        r"\\label\{([^}]+)\}\s*\n"
        r"\\end\{figure\}",
        re.DOTALL,
    )

    def repl(m):
        return "\\triptych{%s}{%s}{%s}" % (m.group(1), m.group(2).strip(), m.group(3))

    return pattern.sub(repl, text)


def fix_table_cells(text, here):
    """Bare names inside the untraced-figures table only.

    Sixteen of its rows name a table in the provenance column. Expanding each
    into a full pointer prints the destination sixteen times in one table, so
    the destination goes in the caption and the cells carry bare names -- but
    only in a document that does not contain those tables itself.
    """
    start = text.find("\\label{tab:untraced}")
    if start < 0:
        return text
    end = text.find("\\end{table}", start)
    if end < 0:
        return text
    body = text[start:end]
    for label, name in TABLE_CELL_NAMES.items():
        if label in here:
            continue
        body = re.sub(
            r"(?:Tables?|Theorems?)~\\ref\{" + re.escape(label) + r"\}(?: and~\\ref\{([^}]+)\})?",
            lambda m, n=name: (
                n + " and " + TABLE_CELL_NAMES.get(m.group(1), m.group(1))
                if m.group(1) else n
            ),
            body,
        )
    return text[:start] + body + text[end:]


def apply_pointers(text, paper, problems):
    """Turn every reference that left this document into a named pointer.

    Whether a reference left is decided by what this document actually defines,
    not by the destination recorded in the table. The record version contains
    every label, so nothing in it is rewritten; move a section between A and B
    and the pointers follow without the table being touched.
    """
    companion = COMPANION[paper]
    here = defined_labels(text)

    def destination(target):
        if companion is not None and target == companion:
            return "\\companion"
        return "\\record"

    def sentence_start(s, pos):
        # A paragraph break counts: after a float or a blank line the pointer
        # opens the sentence even though no full stop precedes it.
        if re.search(r"\n[ \t]*\n[ \t]*$", s[:pos]):
            return True
        before = s[:pos].rstrip()
        if not before:
            return True
        return before[-1] in ".!?" or before.endswith("---")

    def repl(m):
        label = m.group("label")
        if label in here:
            return m.group(0)          # it stayed in this document
        if label not in POINTERS:
            return m.group(0)          # reported by the caller's own check
        target, phrase = POINTERS[label]
        if sentence_start(text, m.start()):
            phrase = phrase[0].upper() + phrase[1:]
        return "%s{%s}" % (destination(target), phrase)

    pattern = re.compile(r"(?:(?:" + REF_WORDS + r")~)?\\ref\{(?P<label>[^}]+)\}")
    return pattern.sub(repl, text)


def defined_labels(text):
    return set(re.findall(r"\\label\{([^}]+)\}", text))


def used_labels(text):
    return set(re.findall(r"\\(?:ref|autoref|eqref)\{([^}]+)\}", text))


def build_body(src, paper, problems):
    text = extract(src, RANGES[paper])
    text = to_triptych(text)
    for before, after in REWRITES[paper]:
        if before not in text:
            problems.append(f"{paper}: rewrite did not match: {before[:60]!r}")
        text = text.replace(before, after)
    here = defined_labels(text)
    text = fix_table_cells(text, here)
    text = apply_pointers(text, paper, problems)
    return text


def main():
    check = "--check" in sys.argv
    src = read_source()
    problems = []
    written = []

    # The record version's abstract, lifted unchanged.
    a0, a1 = ABSTRACT_RANGE
    abstract = "\n".join(src[a0 - 1:a1 - 1]) + "\n"
    abstract_path = HERE / "paper-c-abstract.tex"
    if check:
        if not abstract_path.exists() or abstract_path.read_text(encoding="utf-8") != abstract:
            problems.append("c: paper-c-abstract.tex on disk differs from generated")
    else:
        abstract_path.write_text(abstract, encoding="utf-8")

    for paper in ("a", "b", "c"):
        body = build_body(src, paper, problems)
        # A label used and not defined here is a reference this script failed to
        # route. The LaTeX build would print it as ?? and still exit 0.
        # The wrapper documents carry labels too (the budget convention is in
        # the abstract), so they are read rather than assumed.
        wrapper = set()
        for f in HERE.glob(f"paper-{paper}-*.tex"):
            if f.name != f"paper-{paper}-body.tex":
                wrapper |= defined_labels(f.read_text(encoding="utf-8"))
        dangling = used_labels(body) - defined_labels(body) - wrapper
        for label in sorted(dangling):
            problems.append(f"{paper}: unrouted reference \\ref{{{label}}}")
        path = HERE / f"paper-{paper}-body.tex"
        if check:
            old = path.read_text(encoding="utf-8") if path.exists() else None
            if old != body:
                problems.append(f"{paper}: {path.name} on disk differs from generated")
        else:
            path.write_text(body, encoding="utf-8")
        written.append((paper, path, body))

    for paper, path, body in written:
        print(f"{path.name:22} {len(body.splitlines()):>5} lines  "
              f"{body.count('triptych'):>3} plates  "
              f"{len(defined_labels(body)):>3} labels")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    print("\nevery reference routed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
