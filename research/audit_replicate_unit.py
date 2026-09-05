#!/usr/bin/env python3
"""Gate: a cross-model claim may not be computed at the window level.

WHY THIS EXISTS.  Six times in one campaign a statement about MODEL FAMILIES was
computed over WINDOWS.  The seventh was found in `campaignB_stats.row()`:

    d = np.concatenate([dvec(D, m, arm, ref) for m in models])
    r = paired(d)

Four checkpoints x 35 windows handed to a paired t-test as 140 replicates.  They
replicate the TEXT, not the model family, so the interval is too small by about
sqrt(35) and eleven of fourteen verdicts were wrong.  The preceding assert sweep
audited 187 assertion sites and every gate call and did NOT find it, because the
statistical decision was not made in an assertion -- it was made by
`np.concatenate`, a shape-changing utility that nobody reads as a claim about
exchangeability.

So this gate reads shape changes as claims.  It flags any call to a statistical
summariser whose data argument was built by POOLING a per-model collection.

WHAT IT CANNOT DO.  It is a syntactic check.  It cannot tell whether a claim is
about checkpoints or about text -- it can only tell that windows from more than
one model were flattened into one sample before a p-value or an interval was
computed from them.  That flattening is only ever right when the claim is about
the pooled corpus itself, which in this repository it never is; if it ever is,
say so with the pragma and the pragma becomes the place the reader argues with.

  # replicate-unit: pooled-corpus  <reason>

ESCAPE HATCH, DELIBERATELY LOUD.  The pragma must sit on the pooling line or the
statistical call, and it must carry a reason.  A bare pragma does not silence.

SELF-TEST.  A gate that has never been shown to fire is not a gate.  This one
re-parses the PRE-FIX `campaignB_stats.py` (kept verbatim in
`gates/fixtures/`) and refuses to run at all unless it detects the defect there
and stays silent on the fixed version of the same function.

    python3 research/audit_replicate_unit.py            # scan research/
    python3 research/audit_replicate_unit.py --list     # every site inspected

Exit codes follow run_all_gates.py:  0 clean, 1 findings, 3 self-test broken.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "gates", "fixtures")

# Functions that consume a DATA VECTOR and emit an interval, a t or a p.  Not
# `verdict` -- that takes an already-computed result dict, so flagging it would
# report the same defect twice under two names.
STATS_FUNCS = {
    "paired", "paired_t", "ci", "boot_gain", "bootstrap",
    "ttest_rel", "ttest_ind", "ttest_1samp", "wilcoxon", "mannwhitneyu",
    "binomtest", "binom_test", "spearmanr", "pearsonr", "linregress",
    # this repository's own wrappers around the same thing
    "rho", "spearman", "exact_p", "kstest",
}
# NOT covered, on purpose: np.mean / np.std across models.  Those produce a
# POINT estimate, and every exhibit in this campaign showed the point estimate
# barely moving under repooling (-4.99 % -> -4.76 %).  What the wrong replicate
# unit destroys is the INTERVAL, so the interval is what this gate guards.  A
# pooled mean that is then printed as a claim is a prose problem, not a shape
# problem, and belongs to the reader of the header string.

# Shape changes that destroy the model boundary.  `np.array([... for m in ...])`
# is deliberately ABSENT: that is the CORRECT shape -- one row per model, each
# model contributing one number -- and flagging it would train people to route
# around the gate.
POOL_FUNCS = {"concatenate", "hstack", "vstack", "ravel", "flatten", "chain"}

# A loop variable that means "a checkpoint".  Used together with the iterator
# test below, so `for r in rest` over a list of MODELS still counts and
# `for b in CANDS` does not.
MODEL_VARS = {"m", "md", "model", "h", "ckpt", "checkpoint", "fam", "family"}
MODEL_LIST_NAMES = {"MODELS", "models", "oos", "checkpoints", "families",
                    "held", "LSEEDED", "fit_models", "rest", "have"}
PRAGMA = "# replicate-unit: pooled-corpus"


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class Scope:
    """Names bound in one function body, plus the module's own bindings."""

    def __init__(self, parent=None):
        self.bind = {}                 # name -> value expression (ast)
        self.per_model = set()         # names known to hold a per-model collection
        self.parent = parent

    def lookup(self, n):
        s = self
        while s is not None:
            if n in s.bind:
                return s.bind[n]
            s = s.parent
        return None

    def is_per_model(self, n):
        s = self
        while s is not None:
            if n in s.per_model:
                return True
            s = s.parent
        return False


def _shallow(body):
    """Every node in `body`, not descending into a nested loop.

    So the innermost loop around a node is the one that owns it.
    """
    for st in body:
        if isinstance(st, (ast.For, ast.AsyncFor, ast.While,
                           ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(st):
            yield sub


def model_lists(tree):
    """Names that hold a list of checkpoints, resolved transitively."""
    known = set(MODEL_LIST_NAMES)
    for _ in range(3):                                   # fixpoint, 3 is plenty
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                t, v = node.targets[0].id, node.value
                if isinstance(v, ast.List) and len(v.elts) >= 2 and all(
                        isinstance(e, ast.Constant) and isinstance(e.value, str)
                        for e in v.elts) and t.upper() in {
                            "MODELS", "CHECKPOINTS", "FAMILIES"}:
                    known.add(t)
                if isinstance(v, (ast.ListComp, ast.SetComp)):
                    for g in v.generators:
                        if _name(g.iter) in known:
                            known.add(t)
                if isinstance(v, ast.Call) and _name(v.func) in {"sorted", "list", "set"} \
                        and v.args and _name(v.args[0]) in known:
                    known.add(t)
    return known


def is_per_model_comp(node, known):
    """A comprehension (or generator) that iterates over checkpoints."""
    if not isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
        return False
    for g in node.generators:
        if _name(g.iter) in known:
            return True
        tgt = g.target
        names = ({tgt.id} if isinstance(tgt, ast.Name)
                 else {e.id for e in ast.walk(tgt) if isinstance(e, ast.Name)})
        # `for m in Wd` -- a dict keyed by checkpoint.  The iterator is not a
        # known list, but the loop variable says what a row is.
        if names & MODEL_VARS:
            return True
    return False


def find_pool(node, scope, known, depth=0):
    """Return the pooling Call inside `node`, following local names one hop.

    campaignC_ratio builds its per-model list with `ds.append(...)` inside a
    `for m in ...` loop and only then concatenates, so a purely local test on
    the argument expression would miss it.
    """
    if depth > 4 or node is None:
        return None
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _name(sub.func) in POOL_FUNCS:
            for a in sub.args:
                if is_per_model_comp(a, known):
                    return sub
                if isinstance(a, ast.Name) and scope.is_per_model(a.id):
                    return sub
        if isinstance(sub, ast.Attribute) and sub.attr in ("flatten", "ravel"):
            if isinstance(sub.value, ast.Name) and scope.is_per_model(sub.value.id):
                return sub
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            v = scope.lookup(sub.id)
            if v is not None:
                hit = find_pool(v, scope, known, depth + 1)
                if hit is not None:
                    return hit
    return None


def walk_body(body, scope, known, sites, findings, src_lines, path):
    """One statement list, in order, so a name means what it meant at the call."""
    for st in body:
        # ---- bindings ------------------------------------------------------
        if isinstance(st, ast.Assign) and len(st.targets) == 1 \
                and isinstance(st.targets[0], ast.Name):
            scope.bind[st.targets[0].id] = st.value
        if isinstance(st, ast.For):
            tgt = st.target
            names = ({tgt.id} if isinstance(tgt, ast.Name)
                     else {e.id for e in ast.walk(tgt) if isinstance(e, ast.Name)})
            over_models = _name(st.iter) in known or bool(names & MODEL_VARS)
            if over_models:
                # Only appends whose INNERMOST enclosing loop is this one.  A
                # `for _, mod in target_modules(model)` nested inside `for k in
                # MODELS` accumulates LAYERS of one checkpoint; concatenating
                # those is a within-model pool and correct.  Attributing them to
                # the outer loop made loguniform_size.py:150 a false positive,
                # and a gate that cries wolf is a gate that gets muted.
                for sub in _shallow(st.body):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                            and sub.func.attr == "append" \
                            and isinstance(sub.func.value, ast.Name):
                        scope.per_model.add(sub.func.value.id)

        # ---- the sites this gate is about ----------------------------------
        for sub in ast.walk(st):
            if not (isinstance(sub, ast.Call) and _name(sub.func) in STATS_FUNCS):
                continue
            sites.append((path, sub.lineno, _name(sub.func)))
            hit = None
            for a in sub.args:
                hit = find_pool(a, scope, known)
                if hit is not None:
                    break
            if hit is None:
                continue
            lines = {sub.lineno, hit.lineno}
            excused = [n for n in lines
                       if PRAGMA in src_lines[n - 1]
                       and src_lines[n - 1].split(PRAGMA)[1].strip()]
            if excused:
                continue
            findings.append({
                "file": path, "line": sub.lineno, "func": _name(sub.func),
                "pool_line": hit.lineno, "pool": _name(hit.func) or "flatten",
                "code": src_lines[sub.lineno - 1].strip(),
                "pool_code": src_lines[hit.lineno - 1].strip(),
            })

        # ---- recurse -------------------------------------------------------
        for f in ("body", "orelse", "finalbody"):
            inner = getattr(st, f, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                sub_scope = Scope(scope) if isinstance(
                    st, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
                if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in st.args.args:
                        if arg.arg in MODEL_LIST_NAMES:
                            known = known | {arg.arg}
                walk_body(inner, sub_scope, known, sites, findings, src_lines, path)


def scan_source(src, path):
    tree = ast.parse(src)
    known = model_lists(tree)
    sites, findings = [], []
    walk_body(tree.body, Scope(), known, sites, findings, src.splitlines(), path)
    # A compound statement is inspected once as a whole and again per nested
    # body, so a call inside a `for` is seen twice.  Dedupe on position: two
    # reports of one line are one defect, and a doubled count in a gate is the
    # same species of lie the gate exists to catch.
    sites = sorted(set(sites))
    seen, uniq = set(), []
    for f in findings:
        k = (f["file"], f["line"], f["func"], f["pool_line"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return sites, uniq


def scan_file(path):
    try:
        src = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return [], []
    try:
        return scan_source(src, os.path.relpath(path, os.path.dirname(HERE)))
    except SyntaxError:
        return [], []


# ---------------------------------------------------------------- self-test --
POSITIVE = os.path.join(FIXTURES, "campaignB_stats_prefix.py.txt")
NEGATIVE = """
import numpy as np
MODELS = ["a", "b", "c", "d"]
def dvec(D, m, arm, ref):
    return np.array(D[m][arm]) - np.array(D[m][ref])
def paired(d):
    return {"n": len(d)}
def row(D, arm, ref, models):
    # cross-model claim -> one replicate per CHECKPOINT
    d = np.array([float(dvec(D, m, arm, ref).mean()) for m in models])
    return paired(d)
def within(D, arm, ref, m):
    # within-model claim -> windows are the replicate and are entitled to be
    return paired(dvec(D, m, arm, ref))
"""


def self_test(verbose=False):
    """Refuse to run unless the gate is shown to fire on the known defect."""
    ok, why = True, []
    if not os.path.exists(POSITIVE):
        return False, ["fixture missing: %s" % POSITIVE]
    _, pos = scan_source(open(POSITIVE, encoding="utf-8").read(), POSITIVE)
    hit = [f for f in pos if f["func"] == "paired"]
    if not hit:
        ok = False
        why.append("did NOT fire on the pre-fix campaignB_stats.row()")
    else:
        rowhit = [f for f in hit if "np.concatenate" in f["pool_code"]]
        if not rowhit:
            ok = False
            why.append("fired on the fixture but not on the concatenate")
        elif verbose:
            for f in rowhit[:3]:
                why.append("fires at pre-fix line %d: %s"
                           % (f["pool_line"], f["pool_code"][:70]))
    _, neg = scan_source(NEGATIVE, "<fixed>")
    if neg:
        ok = False
        why.append("false positive on the FIXED shape at line %d" % neg[0]["line"])
    # and the real, fixed file must be silent about row()
    real = os.path.join(HERE, "block", "campaignB_stats.py")
    if os.path.exists(real):
        _, rf = scan_file(real)
        if any(f["line"] < 140 for f in rf):
            ok = False
            why.append("fires on the FIXED campaignB_stats.row() -- gate is wrong")
    return ok, why


def main():
    verbose = "--list" in sys.argv or "--verbose" in sys.argv
    ok, why = self_test(verbose=True)
    print("SELF-TEST: " + ("PASS" if ok else "BROKEN"))
    for w in why:
        print("   " + w)
    if not ok:
        print("\nA gate that cannot detect its own fixture reports nothing "
              "and means nothing.")
        return 3

    all_sites, all_find = [], []
    for dp, dn, fn in os.walk(HERE):
        if "__pycache__" in dp or os.path.abspath(dp).startswith(FIXTURES):
            continue
        for f in sorted(fn):
            if f.endswith(".py") and f != os.path.basename(__file__):
                s, g = scan_file(os.path.join(dp, f))
                all_sites += s
                all_find += g
    print("\nstatistical call sites inspected : %d in %d files"
          % (len(all_sites), len({s[0] for s in all_sites})))
    print("cross-model claims computed over windows : %d" % len(all_find))
    if verbose:
        print()
        for p, ln, fn in all_sites:
            print("   %-46s :%-5d %s" % (p, ln, fn))
    for f in sorted(all_find, key=lambda x: (x["file"], x["line"])):
        print("\n%s:%d" % (f["file"], f["line"]))
        print("   %-14s %s" % ("pooled at :%d" % f["pool_line"], f["pool_code"][:88]))
        print("   %-14s %s" % ("consumed by", f["code"][:88]))
        print("   the replicate unit here is the WINDOW; the models were "
              "flattened into one sample.")
        print("   Take n = models, or justify the pool with:  %s <reason>" % PRAGMA)
    if not all_find:
        print("\nNo cross-model claim is computed at the window level.")
    return 1 if all_find else 0


if __name__ == "__main__":
    sys.exit(main())
