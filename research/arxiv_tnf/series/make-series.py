#!/usr/bin/env python3
"""Generate the Trinity S3AI paper series from the single source manuscript.

The series is four papers cut from one 8,061-line source, in five renderings:

  A  paper-a-methodology  How a comparison fails      (the transferable result)
  B  paper-b-format       Ternary Network Floats      (the format result)
  C  paper-c-record       the full record version     (everything, unchanged)
  D  paper-d-series       How a comparison fails      (the series rendering)
     paper-d-isqed        the same paper for ISQED    (10 pages, double-blind)

Every paper in the series opens with the same title plate, the same logo and the
same triptych plates, because it is one body of work and three documents that
looked like three projects would read as three.

The ISQED rendering is the exception, and it is a rendering and not a fourth
opinion: the same cut under three constraints the venue imposes and the series
does not -- at most ten IEEE two-column pages, double-blind, and standing alone.
The third has the teeth. A and B may say "the hardware section of the companion
paper" because the companion is part of the same publication; a conference
submission has no companion, and under double-blind a pointer at an unpublished
sibling is also a pointer at its author. Every reference that leaves the ISQED
rendering is therefore routed to "the extended version of this work", which is
true, checkable and anonymous.

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

import difflib
import hashlib
import re
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE.parent / "tnf_paper.tex"

# --- the cut -----------------------------------------------------------------
# Half-open line ranges into tnf_paper.tex, in the order they appear in the
# generated body. Each range is a whole \section or a run of them.

RANGES = {
    "a": [
        (1238, 1348),   # The comparison at matched physical width
        (1431, 1487),   # Two width defects, and why they generalise
        (5901, 6262),   # How a comparison fails while every measurement is correct
        (6262, 6375),   # Adjacent work this paper is measured against
        (6375, 6452),   # What the formal statements are, and what they are
        (6452, 6915),   # Three results added in this revision
        (7680, 7812),   # Limitations
        (7812, 7840),   # Reproducibility, Disclosure
    ],
    "b": [
        (455, 489),     # The format
        (489, 589),     # Why a ladder, and why this one
        (589, 1007),    # The law is general, and it measures tapering
        (1007, 1087),   # Accuracy
        (1087, 1238),   # The 16-bit field
        (1348, 1431),   # Hardware
        (1527, 1690),   # What the law says about improving the ladder
        (1690, 2078),   # Why ternary, and exactly how much
        (3636, 3925),   # Two formats close a ternary node
        (4391, 4847),   # Fineness costs registers, not adders
    ],
}

# Paper C is the record: the whole body, cut nowhere.
RANGES["c"] = [(189, 7840)]

# Paper D is A without its revision notes. It keeps the two measurements that
# are the contribution, the six failure modes that are the subject, the worked
# example, the epistemics, the related work and the limitations -- and drops
# 6452-6915 (3,984 words), which is addressed to a reader of the previous
# version and means nothing to a reader meeting the work here. That cut is also
# what brings the ISQED rendering of it inside ten pages.
RANGES["d"] = [
    (5901, 6262),   # How a comparison fails while every measurement is correct
    (1238, 1348),   # The comparison at matched physical width  (worked example)
    (1431, 1487),   # Two width defects, and why they generalise
    (6375, 6452),   # What the formal statements are, and what they are not
    (6262, 6375),   # Adjacent work this paper is measured against
    (7680, 7812),   # Limitations
    (7812, 7840),   # Reproducibility, Disclosure
]

# --- renderings, not cuts ----------------------------------------------------
# A paper id names a RENDERING. D exists twice on purpose, and the reason is the
# whole argument of this file: the series is one body of work and must read like
# one, so D is set in the house style with the same title plate, the same logo
# and the same triptychs as A, B and C. ISQED then wants that same paper
# deformed three ways -- two columns, ten pages, no author -- and that
# deformation is a rendering of the paper, not a different paper.
#
# Both renderings come from ONE line range and ONE rewrite list. A cut that
# lived in two places would be changed in one of them.
PAPERS = ("a", "b", "c", "d", "d-isqed")

CUT = {"a": "a", "b": "b", "c": "c", "d": "d", "d-isqed": "d"}

# Renderings whose canon plates are dropped rather than set. The plates are the
# series' own engravings and every paper carries them; only the ten-page limit
# cannot afford eleven full-width ones, so only the ISQED rendering loses them.
STRIP_FIGURES = {"d-isqed"}

# Renderings that stand alone. A reference leaving one of these cannot name a
# sibling document, so every destination collapses to \extended.
STANDALONE = {"d-isqed"}

# Renderings already handed to a venue. The ISQED rendering was submitted as
# paper 66, and the venue holds that text: a correction to it is an erratum the
# owner sends, not a regeneration here. Its files are checked against the hash
# of what was submitted instead of being written, and every later step (the
# pruned bibliography, the double-blind gate) reads the frozen text. The cut is
# still rendered, so the build says how far the source has moved since; that is
# information, not a problem.
FROZEN = {
    "paper-d-isqed-body.tex":
        "bbe4e784ed54bde207871e88569e606db864e56c7b38a87b29588fe10bb9ed2c",
    "paper-d-isqed-newsection.tex":
        "99d0effc6a97f45787d5db8c4b27b32f10c98c56cb0e2c7b7fbda5206ae9cdf5",
}

# Which files each rendering is assembled from. Listed rather than globbed:
# paper-d-*.tex also matches the ISQED rendering's files, so a glob would hand
# the double-blind gate one document while it reported on another -- measuring
# the wrong artefact, which is the defect this paper is about.
BODY = {
    "a": "paper-a-body.tex",
    "b": "paper-b-body.tex",
    "c": "paper-c-body.tex",
    "d": "paper-d-body.tex",
    "d-isqed": "paper-d-isqed-body.tex",
}

WRAPPERS = {
    "a": ["paper-a-methodology.tex", "paper-a-newsection.tex"],
    "b": ["paper-b-format.tex"],
    "c": ["paper-c-record.tex", "paper-c-abstract.tex"],
    # The series rendering is one column, so it inputs A's section as written
    # rather than the copy fitted to a 3.5-inch measure.
    "d": ["paper-d-series.tex", "paper-a-newsection.tex"],
    "d-isqed": ["paper-d-isqed.tex", "paper-d-isqed-newsection.tex"],
}

# The built PDF of a rendering is named after its wrapper.
PDF = {p: WRAPPERS[p][0].replace(".tex", ".pdf") for p in PAPERS}

# The record version keeps the manuscript's own abstract, which is where the
# budget convention is declared and labelled. A and B state their own.
ABSTRACT_RANGE = (82, 187)

TITLES = {
    "a": "How a Comparison Fails",
    "b": "Ternary Network Floats",
    "c": "Ternary Network Floats (record version)",
    "d": "How a Comparison Fails While Every Measurement Is Correct",
    "d-isqed": "How a Comparison Fails (ISQED 2027 submission)",
}

# Which document each rendering points at when a reference leaves it. The record
# version holds every section, so it is the backstop for all of them. The series
# rendering of D sits inside the series and may name its siblings; the ISQED one
# has none to name.
COMPANION = {"a": "b", "b": "a", "c": None, "d": "b", "d-isqed": None}

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
    "cor:slackartefact":         ("c", "the slack-artefact corollary"),
    "sec:blockbound":            ("c", "the block-axis section"),
    "tab:blockbound":            ("c", "the block-axis table"),
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
    # Defined inside the revision-notes section, which only paper D drops.
    "sec:variantA":              ("c", "the variant-A section"),
    "tab:ladderversions":        ("c", "the ladder-version table"),
}

# --- the double-blind gate ---------------------------------------------------
# ISQED: "Manuscripts identifying author names and/or affiliations will be
# rejected without review." That is a rejection with no appeal and no reviewer
# report, so it is worth a check that fails the build rather than a habit of
# reading carefully. Every generated part of a STANDALONE paper -- body,
# wrapper, bibliography -- is searched for these, and a hit is an error.
#
# Matched CASE-INSENSITIVELY, which is not a detail. These ran case-sensitively
# and passed a manuscript whose page 3 read "TRINITY S3AI": the sources write
# the name "Trinity S\textsuperscript{3}AI", the figures draw it upper-case, and
# /Trinity\s*S3AI/ matches neither of the two forms that actually appear. A name
# is the same name in any case.
IDENTIFYING = [
    r"Vasilev",
    r"Dmitrii",
    r"gHashTag",
    r"t27\.ai",
    r"ORCID",
    r"Trinity\s*S\\?textsuperscript|Trinity\s*S.?3.?AI|Trinity\s*S\^3",
    r"trinity-series",          # the house style carries the logo and the name
    r"seriesplate|seriesauthor",
]

# The bibliography cites two of the author's own arXiv papers. Public prior work
# may be cited under double-blind -- a non-author would cite it the same way --
# but the source URL on one of them is a personal account name, which is not a
# citation, it is a signature. It is removed for D only.
BIB_ANONYMISE = [
    (r"Source: \\url\{https://github\.com/gHashTag/t27\},\s*tag\s*\n?\\texttt\{v4\.0-trinity\}\.",
     "The tagged source release accompanying that paper is public."),
    (r"D\.~Vasilev\.", "Author names omitted for double-blind review."),
]

# --- passages that a mechanical substitution would wreck ----------------------
# Two places reference half a dozen labels in one breath. Expanding each into
# its own named pointer would print the destination six times in four lines.
# They are rewritten whole, once, here.

# The methodology cut's rewrites. A and the series rendering of D are the same
# cut inside the same series, so they share this list rather than hold a copy
# each: a second copy is a second place to forget.
METHODOLOGY_REWRITES = [
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
]

REWRITES = {
    "a": METHODOLOGY_REWRITES,
    "b": [],
    "c": [],
    "d": METHODOLOGY_REWRITES,
    # The ISQED rendering carries the same untraced-figures table and the same
    # reason for naming its destination once in the caption rather than sixteen
    # times in the cells -- but it must name the destination it actually has,
    # and it has no sibling to name.
    "d-isqed": [
        (
            "strict registry. Each is retained and marked $^{\\ast}$ at every point of use, and",
            "strict registry. Table and theorem names in the middle column refer to the\n"
            "extended version of this work, where the full twenty-one-row experiment is\n"
            "tabulated. Each figure is retained and marked $^{\\ast}$ at every point of use, and",
        ),
    ],
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


def strip_figures(text):
    """Drop the ornament and keep the data.

    78 of the source's 87 figures are canon plates: full-width three-panel
    engravings, and not one of them is \\ref'd anywhere in 8,061 lines. The
    other nine are generated plots of measurements, and four of those ARE
    referenced. So the rule is not "delete figures", it is "delete the ones
    whose image comes out of canon/" -- which keeps the distinction the source
    already makes and costs no cross reference.

    A plate that turned out to be referenced after all would leave a dangling
    label, and the routing check downstream fails on it rather than letting
    LaTeX print ?? and exit 0.
    """
    text = re.sub(r"\\triptych\{[^}]*\}\{.*?\}\{[^}]*\}\s*", "", text, flags=re.DOTALL)
    text = re.sub(
        r"\\begin\{figure\}(?:(?!\\end\{figure\}).)*?"
        r"\\includegraphics\[[^\]]*\]\{canon/[^}]*\}"
        r"(?:(?!\\end\{figure\}).)*?\\end\{figure\}\s*",
        "", text, flags=re.DOTALL)
    # What survives is a single-column float in a two-column layout, where
    # \textwidth is both columns and overflows the page without erroring.
    return text.replace("includegraphics[width=\\textwidth]",
                        "includegraphics[width=\\columnwidth]")


def break_long_paths(text):
    """Give TeX somewhere to break inside a long artefact path.

    This paper cites its evidence by path, and a path in \\texttt has no
    hyphenation point: cmtt is loaded with \\hyphenchar=-1, so TeX treats
    `research/frontier/WITHDRAWAL_FMAX_UNSOURCED_2026-08-10.md` as one
    unbreakable 54-character word. There is nowhere to break it, so it is set
    into the margin -- 66pt into it, in a 6.5-inch measure -- and that is an
    overfull box, which is a warning among hundreds and EXITS 0.

    This is a property of the text and not of any venue, so it is applied to
    every rendering. It used to live inside fit_two_columns, which only the
    ISQED rendering calls, on the theory that a 3.5-inch column was what made
    the path overhang. It was not: the same path overhangs the wide measure
    too, and papers A, C and the series rendering of D each shipped it hanging
    in the gutter while the conference version, alone, set it correctly.

    \\allowbreak after each separator, never a hyphen: a break in a path must
    not add a character, because a reader who copies the line has to get the
    path back. Only tokens long enough to be at risk are touched, so short
    identifiers are not littered with break points that would never be taken.

    Idempotent -- a token that already carries \\allowbreak is left alone, so
    running this after fit_two_columns cannot double the break points.
    """
    def unwrap(m):
        inner = m.group(1)
        if "\\allowbreak" in inner:
            return m.group(0)
        if len(inner) < 24 or ("/" not in inner and "\\_" not in inner):
            return m.group(0)
        broken = inner.replace("/", "/\\allowbreak ").replace("\\_", "\\_\\allowbreak ")
        return "\\texttt{%s}" % broken

    return re.sub(r"\\texttt\{([^{}]*)\}", unwrap, text)


def fit_two_columns(text):
    """Make one-column material survive a 3.5-inch measure.

    Tables laid out for a 6.5-inch line run into the gutter at half that width,
    and that is not an error -- LaTeX sets an overfull box, prints a warning
    among hundreds and exits 0. IEEE practice is to set them smaller;
    \\footnotesize is the smallest step that keeps them legible. \\footnotesize
    alone is not always enough -- a three-column table whose middle column is a
    phrase still overhangs -- so each tabular is also wrapped in
    \\adjustbox{max width=\\columnwidth}. "max width" and not \\resizebox: the
    latter scales every table to the column, enlarging the narrow ones, while
    this one touches only what would not otherwise fit.

    Long artefact paths are handled by break_long_paths, which every rendering
    needs and which is therefore not here.
    """
    text = break_long_paths(text)
    text = re.sub(r"\\begin\{tabular\}",
                  "\\\\adjustbox{max width=\\\\columnwidth}{\\\\begin{tabular}", text)
    text = re.sub(r"\\end\{tabular\}", "\\\\end{tabular}}", text)
    return re.sub(r"(\\begin\{table\}(?:\[[^\]]*\])?)(\\centering)?",
                  lambda m: m.group(1) + (m.group(2) or "") + "\\footnotesize ",
                  text)


def build_bibliography(text, cited):
    """Keep the entries this paper cites, in the order the source lists them.

    The shared list has 94 entries because it serves the record version. A
    \\bibitem nobody cites still sets a numbered paragraph, and 65 of them cost
    roughly a page and a half of a ten-page limit -- so pruning here is what
    makes the limit reachable without cutting argument. It is also just what a
    reference list is: the works referred to.

    Anonymisation happens on the way out, because two of the entries are the
    author's own prior work. Public prior work may be cited under double-blind
    -- a reader who is not the author would cite it identically -- but the
    author's name in the author position, and a repository URL that is a
    personal account name, are signatures rather than citations.
    """
    entries = re.split(r"(?=\\bibitem\{)", text)
    head = entries[0]
    kept = []
    for entry in entries[1:]:
        key = re.match(r"\\bibitem\{([^}]+)\}", entry).group(1)
        if key in cited:
            kept.append(entry.rstrip() + "\n\n")
    tail = "\\end{thebibliography}\n"
    kept[-1] = kept[-1].replace("\\end{thebibliography}", "").rstrip() + "\n\n"
    out = head.replace("{thebibliography}{9}", "{thebibliography}{99}") \
          + "".join(kept) + tail
    for pattern, replacement in BIB_ANONYMISE:
        out = re.sub(pattern, replacement, out)
    return out


def identifying_hits(text):
    """Every line that would get a double-blind submission rejected unread.

    LaTeX comments are stripped first. What is submitted is a PDF, a comment
    sets no type, and the alternative is a rule that forbids the source from
    explaining the rule -- the comment block in paper-d-isqed.tex naming the
    things that must not appear would itself be the violation.
    """
    out = []
    for n, raw in enumerate(text.split("\n"), 1):
        line = re.sub(r"(?<!\\)%.*$", "", raw)
        for pattern in IDENTIFYING:
            if re.search(pattern, line, re.I):
                out.append((n, pattern, line.strip()[:90]))
                break
    return out


def pdf_gate(paper):
    """The same gate, over the PDF -- because the sources are not what ships.

    The source gate passed on a manuscript whose page 3 read TRINITY S3AI. The
    wordmark is drawn inside the figures by canon_style.py, so it is vector text
    in an included plot: invisible to any grep of the .tex files and perfectly
    visible to a reviewer, to pdftotext, and to a moderator's search. Checking
    the source and declaring the PDF clean is measuring the wrong artefact,
    which is the failure this paper is about.

    A missing PDF is reported, not skipped. A gate that goes quiet when its
    input is absent is the clause-folded-to-a-constant defect in Section II.
    """
    pdf = HERE / PDF[paper]
    if not pdf.exists():
        return [f"{paper}: {pdf.name} is not built, so the PDF gate did not run"]
    r = subprocess.run(["pdftotext", str(pdf), "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return [f"{paper}: pdftotext failed on {pdf.name}; PDF gate did not run"]
    out = []
    for n, line in enumerate(r.stdout.split("\n"), 1):
        for pattern in IDENTIFYING:
            if re.search(pattern, line, re.I):
                out.append(f"{paper}: {pdf.name} page-text line {n} identifies "
                           f"the author [/{pattern}/]: {line.strip()[:90]}")
                break
    return out


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


def _macro_spans(text, macro):
    """Every \\macro{...} in text, as (start, end, argument), braces matched."""
    out = []
    for m in re.finditer(r"\\" + macro + r"\{", text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if not depth:
            out.append((m.start(), i, text[m.end():i - 1]))
    return out


# What separates two items of a list and nothing else. A full stop or a verb
# between two pointers means they are separate claims, not a list, and the
# qualifier is not shared.
_LIST_JOIN = re.compile(r"^(,|\s+and\b|,\s+and\b|;)\s*$")


def collapse_pointer_runs(text):
    """In a list of pointers, qualify the last one only.

    Seven references to the same document in one sentence expanded to seven
    copies of the same twelve-word phrase:

        The economy theorem of the extended version of this work, the
        no-free-lunch theorem of the extended version of this work, [...]

    The source wrote "Theorem 3, Theorem 5, Theorem 7", which is short because a
    number is short; a named pointer is not, and the substitution that is right
    once is unreadable seven times in a row. English already distributes a
    trailing qualifier over a list, so the fix is to let it: strip the wrapper
    from every item but the last, and the one at the end covers them all.
    """
    for macro in ("extended", "companion", "record"):
        while True:
            spans = _macro_spans(text, macro)
            run = None
            for a, b in zip(spans, spans[1:]):
                if _LIST_JOIN.match(text[a[1]:b[0]]):
                    run = a
                    break
            if run is None:
                break
            start, end, arg = run
            text = text[:start] + arg + text[end:]
    return text


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
        # A standalone paper has no sibling to name. Under double-blind it must
        # not have one: "see the companion paper" identifies the author as
        # surely as a signature would.
        if paper in STANDALONE:
            return "\\extended"
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
    text = extract(src, RANGES[CUT[paper]])
    text = to_triptych(text)
    for before, after in REWRITES[paper]:
        if before not in text:
            problems.append(f"{paper}: rewrite did not match: {before[:60]!r}")
        text = text.replace(before, after)
    # Every rendering, because an unbreakable path overhangs any measure.
    text = break_long_paths(text)
    if paper in STRIP_FIGURES:
        text = strip_figures(text)
    if paper in STANDALONE:
        text = fit_two_columns(text)
    here = defined_labels(text)
    text = fix_table_cells(text, here)
    text = apply_pointers(text, paper, problems)
    text = collapse_pointer_runs(text)
    return text


def frozen(path, generated, problems):
    """The submitted text of a frozen file, after checking it is still that text."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != FROZEN[path.name]:
        problems.append(f"{path.name} is frozen and no longer matches what was submitted")
    elif generated != text:
        diff = difflib.unified_diff(text.splitlines(), generated.splitlines(), n=0)
        moved = sum(1 for l in diff if l[:1] in "+-" and l[:3] not in ("+++", "---"))
        print(f"{path.name:22} frozen as submitted; rendering the source now "
              f"would change {moved} lines (not written)")
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

    # The series bibliography is the record version's, lifted unchanged. It was
    # a hand copy of the manuscript's, and a hand copy is a second place to
    # forget an entry.
    b0 = next(i for i, l in enumerate(src) if l.startswith("\\begin{thebibliography}"))
    b1 = next(i for i, l in enumerate(src) if l.startswith("\\end{thebibliography}"))
    bib = "\n".join(src[b0:b1 + 1]) + "\n\n"
    bib_path = HERE / "bibliography.tex"
    if check:
        if not bib_path.exists() or bib_path.read_text(encoding="utf-8") != bib:
            problems.append("bibliography.tex on disk differs from generated")
    else:
        bib_path.write_text(bib, encoding="utf-8")

    # The section deriving the two headline measurements is shared with paper A,
    # which is set one-column -- and so is the series rendering of D, which
    # therefore inputs A's file as written. Only the ISQED rendering needs the
    # same prose at half the measure, and it gets a fitted copy rather than a
    # second hand-maintained original.
    newsec = fit_two_columns((HERE / "paper-a-newsection.tex").read_text(encoding="utf-8"))
    newsec_path = HERE / "paper-d-isqed-newsection.tex"
    if newsec_path.name in FROZEN:
        newsec = frozen(newsec_path, newsec, problems)
    elif check:
        if not newsec_path.exists() or newsec_path.read_text(encoding="utf-8") != newsec:
            problems.append(f"d-isqed: {newsec_path.name} on disk differs from generated")
    else:
        newsec_path.write_text(newsec, encoding="utf-8")

    for paper in PAPERS:
        path = HERE / BODY[paper]
        if path.name in FROZEN:
            # A rewrite that no longer matches the moved source says nothing
            # about the frozen text, so its complaints are not collected.
            body = frozen(path, build_body(src, paper, []), problems)
        else:
            body = build_body(src, paper, problems)
        # A label used and not defined here is a reference this script failed to
        # route. The LaTeX build would print it as ?? and still exit 0.
        # The wrapper documents carry labels too (the budget convention is in
        # the abstract), so they are read rather than assumed.
        wrapper = set()
        for name in WRAPPERS[paper]:
            f = HERE / name
            if f.exists():
                wrapper |= defined_labels(f.read_text(encoding="utf-8"))
        dangling = used_labels(body) - defined_labels(body) - wrapper
        for label in sorted(dangling):
            problems.append(f"{paper}: unrouted reference \\ref{{{label}}}")
        if path.name in FROZEN:
            pass
        elif check:
            old = path.read_text(encoding="utf-8") if path.exists() else None
            if old != body:
                problems.append(f"{paper}: {path.name} on disk differs from generated")
        else:
            path.write_text(body, encoding="utf-8")
        written.append((paper, path, body))

    # The pruned, anonymised bibliography, built once D is assembled so that it
    # can be asked what D actually cites rather than told.
    bodies = {p: body for p, _, body in written}
    cited = set()
    for text in [bodies["d-isqed"], newsec,
                 (HERE / "paper-d-isqed.tex").read_text(encoding="utf-8")]:
        for group in re.findall(r"\\cite\{([^}]+)\}", text):
            cited |= {k.strip() for k in group.split(",")}
    full_bib = (HERE / "bibliography.tex").read_text(encoding="utf-8")
    known = set(re.findall(r"\\bibitem\{([^}]+)\}", full_bib))
    for key in sorted(cited - known):
        problems.append(f"d: \\cite{{{key}}} has no entry in bibliography.tex")
    anon_bib = build_bibliography(full_bib, cited)
    anon_bib_path = HERE / "bibliography-anon.tex"
    if check:
        if not anon_bib_path.exists() or anon_bib_path.read_text(encoding="utf-8") != anon_bib:
            problems.append("d: bibliography-anon.tex on disk differs from generated")
    else:
        anon_bib_path.write_text(anon_bib, encoding="utf-8")
    print(f"{'bibliography-anon.tex':22} {len(cited):>5} of {len(known)} entries cited")

    # The double-blind gate, over everything a standalone paper actually ships.
    for paper in sorted(STANDALONE):
        parts = {BODY[paper]: bodies[paper],
                 "bibliography-anon.tex": anon_bib}
        for name in WRAPPERS[paper]:
            f = HERE / name
            if f.exists():
                parts[name] = f.read_text(encoding="utf-8")
        for name, text in sorted(parts.items()):
            for n, pattern, line in identifying_hits(text):
                problems.append(f"{paper}: {name}:{n} identifies the author "
                                f"[/{pattern}/]: {line}")
        problems.extend(pdf_gate(paper))

    for paper, path, body in written:
        words = sum(len(l.split()) for l in body.split("\n")
                    if not l.lstrip().startswith("%"))
        print(f"{path.name:22} {len(body.splitlines()):>5} lines  "
              f"{body.count('triptych'):>3} plates  "
              f"{len(defined_labels(body)):>3} labels  "
              f"{words:>6} words")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    print("\nevery reference routed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
