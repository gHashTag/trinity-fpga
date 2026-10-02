#!/usr/bin/env python3
"""Does every file a document names actually exist?

Enumerating the pairs that must agree showed all existing gates are code against
code, and that every pair with a document on one side is unguarded. One of them
-- the paper against its measurements -- is now covered. This covers the rest:
a document that names a file, a script or a gate is making a checkable claim
about the tree, and nothing checked it.

Sixteen claims were withdrawn during this work and three gates were added,
renamed or moved. A path in prose does not update itself.
"""
import os, re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def exists(p):
    """`Path.exists()` that cannot abort the run.

    A document naming an absolute path -- `/root/bitnet_h100_metrics.json` is
    the one in this tree -- makes `base / p` collapse to that absolute path,
    because joining with an absolute right operand discards the left. Stat-ing
    it is then a stat of somebody's home directory. pathlib ignores ENOENT and
    ENOTDIR but not EACCES, so on a machine where `/root` exists and is 0700 --
    every CI runner -- this raised PermissionError and killed the checker
    before it reported anything.

    On a developer Mac `/root` does not exist, so `.exists()` answered False and
    the whole gate looked fine. Unreadable is not the same as absent, but for a
    checker asking "does this repository contain the file it names" the answer
    is False either way.
    """
    try:
        if not p.exists():
            return False
    except OSError:
        return False
    return _case_exact(p)


_LISTING = {}


def _case_exact(p):
    """Does every component of `p` match the case actually stored on disk?

    `Path.exists()` answers a question about the HOST FILESYSTEM, and macOS
    answers it case-insensitively while every Linux runner does not. One
    reference -- `docs/internal/agents.md` against a tree holding
    `docs/docs/internal/AGENTS.md` -- resolved on a developer Mac and failed in
    CI, so this gate was verified green locally and was red on main at the very
    commit that "fixed" it. A checker whose verdict depends on who ran it is
    not a checker.

    Walking the components against real directory listings makes the answer the
    same everywhere. Listings are memoised: successes are the common path and
    the walk would otherwise be a stat storm.
    """
    try:
        # `..` and `.` are not entries in any directory listing, so a path
        # carrying them must be normalised BEFORE the walk. Textual
        # normalisation, not `resolve()`: resolving follows symlinks and would
        # answer about the link target rather than the path the document wrote.
        parts = pathlib.Path(os.path.normpath(str(p.absolute()))).parts
    except OSError:
        return False
    cur = pathlib.Path(parts[0])
    for part in parts[1:]:
        key = str(cur)
        entries = _LISTING.get(key)
        if entries is None:
            try:
                entries = set(os.listdir(cur))
            except OSError:
                return False
            _LISTING[key] = entries
        if part not in entries:
            return False
        cur = cur / part
    return True


DOCS = sorted(set(list(ROOT.glob("research/**/*.md")) + list(ROOT.glob("*.md"))
                  + list(ROOT.glob("docs/**/*.md"))))

# A path-like token: has a slash and an extension we own, or is a bare script name
PATHY = re.compile(r'`([A-Za-z0-9_./-]+\.(?:py|v|sh|tex|yml|yaml|md|t27|json))`')

SIBLING_NAMES = ["t27", "trinity-s3ai", "claim-audit-lab", "tri-net", "trios-mesh",
                 "zig-golden-float"]

# Trees this checker cannot see, named by the first path segment. Two kinds,
# one rule: if the author says which repository a file lives in, the reference
# is answerable by a reader even though no runner can resolve it.
#
#   UPSTREAM  -- third-party, never checked out anywhere, ours to reference only
#   OWNER     -- our OTHER repositories. `gHashTag/trinity/...`, owner-first,
#                because `trinity/` alone would shadow the real ./trinity
#                directory in this tree and silently excuse local rot. Checked:
#                no ./gHashTag exists, and none of the UPSTREAM names collide
#                with a directory here either.
UPSTREAM = ["nextpnr-xilinx", "prjxray", "prjxray-db", "litex-boards", "litex",
            "openxc7", "yosys", "openFPGALoader"]
OWNER = ["gHashTag"]
QUALIFIED = set(UPSTREAM) | set(OWNER)

def _index(root):
    """basename -> True, built once. The first version ran an rglob per reference
    per sibling tree; 1511 references across six trees is a quarter of a million
    directory walks, and a gate slow enough to skip is worse than no gate."""
    names = set()
    if root.is_dir():
        for q in root.rglob("*"):
            if q.is_file(): names.add(q.name)
    return names

_OWN = _index(ROOT)
_SIB = {s_: _index(ROOT.parent / s_) for s_ in SIBLING_NAMES}

fails, checked, refs = [], 0, 0
cross, vendored, by_design, upstream = [], [], [], []
for d in DOCS:
    try: txt = d.read_text(errors="ignore")
    except Exception: continue
    checked += 1
    # A document whose purpose IS to record names that no longer exist -- a
    # rename map, a rot inventory -- declares it once at the top rather than
    # phrasing every row to dodge the checker. An explicit exclusion is
    # auditable; a phrasing trick is not.
    if "<!-- doc-refs: names-absent-files-by-design -->" in txt:
        by_design.append(str(d.relative_to(ROOT))); continue
    for m in PATHY.finditer(txt):
        p = m.group(1); refs += 1
        if p.startswith("http"): continue
        # A temporary path is expected to be gone; naming one is not a broken
        # reference, it is a note about a run that has finished.
        if p.startswith(("/tmp/", "/private/tmp/", "/var/")): continue
        # A path in a third-party repository is a real reference, and no CI
        # runner will ever have that tree to check it against. Requiring the
        # repo name as the first segment is what makes it checkable at all:
        # existence cannot be confirmed, but the author having said WHICH tree
        # it lives in can be -- and that is also the thing a reader needs. A
        # bare `design.json` is unresolvable by anybody; the prefixed form
        # names a file someone can actually go and open.
        if p.split("/")[0] in QUALIFIED:
            upstream.append(f"{str(d.relative_to(ROOT))}: names `{p}`"); continue
        rel = str(d.relative_to(ROOT))
        if p.startswith("external/") or rel.startswith("external/"):
            # A vendored document carries paths relative to ITS OWN root.
            # A vendored document carries paths relative to ITS OWN root,
            # so resolving them against ours measures the wrong tree.
            vendored.append(f"{rel}: names `{p}`"); continue
        # A document may name a file precisely to record that it is missing --
        # SCRIPT_ROT names tef_mul_wp.v as the module a build script instantiates
        # and nothing defines. Flagging that would be flagging the finding.
        w = txt[max(0, m.start()-160): m.end()+160].lower()
        if any(k in w for k in ("does not exist", "no definition", "nowhere in",
                                "absent from", "which is gone", "not in the tree")):
            continue
        # Sibling repositories are part of this work and a document may name a
        # path in one of them; that is a real reference, not a dangling one.
        # One list: this used to be a hand copy of SIBLING_NAMES that had lost
        # zig-golden-float, so a path in that repo was "rot" here and a known
        # sibling to materialise_siblings.sh.
        SIBLINGS = SIBLING_NAMES
        cands = [ROOT / p, ROOT / "tools" / p, ROOT / "conformance" / p,
                 ROOT.parent / p, d.parent / p] + [ROOT.parent / sib / p for sib in SIBLINGS]
        # a bare filename may live anywhere in the tree
        if "/" not in p:
            if p in _OWN: continue
            _hit = next((s_ for s_ in SIBLING_NAMES if p in _SIB[s_]), None)
            if _hit:
                # Excluded, but RECORDED. An exclusion nobody can see reads as
                # coverage. These references resolve only in a sibling repo, so
                # a checkout without them cannot tell them from rot; that
                # is a reason to name them, not to drop them silently.
                cross.append(f"{str(d.relative_to(ROOT))}: names `{p}`" f" -> resolves in {_hit}")
                continue
        _sib = next((sib for sib in SIBLINGS if exists(ROOT.parent / sib / p)), None)
        if _sib and not exists(ROOT / p):
            # Same rule as the bare-name case: excluded, but named. A checkout
            # without the siblings cannot tell this from rot -- which is why the
            # exclusion belongs in a file rather than in the checker's silence.
            cross.append(f"{str(d.relative_to(ROOT))}: names `{p}` -> resolves in {_sib}")
            continue
        if any(exists(c) for c in cands): continue
        fails.append(f"{d.relative_to(ROOT)}: names `{p}`, which does not exist")

# Ratchet: the tree carries historical documents naming files removed long ago.
# Blocking on that debt would make the gate useless; fail only on NEW ones.
import sys as _s
BASE = pathlib.Path(__file__).with_name("doc_refs_baseline.txt")
print(f"documents scanned: {checked}   path references: {refs}")
print(f"excluded as cross-repo (target exists in a sibling): {len(cross)}")
print(f"excluded as vendored (relative to their own root):   {len(vendored)}")
print(f"excluded as upstream (third-party, repo-qualified):  {len(upstream)}")
print(f"excluded by declaration (documents recording absent names): {len(by_design)}")
[print(f"    {b}") for b in by_design]
# The exclusions are PUBLISHED, because an exclusion nobody can see reads as
# coverage: the references the gate deliberately does not verify, in files
# someone can read. They used to be rewritten on every run. That dirtied the
# tree of anyone who ran the gate, and nothing compared the committed copies
# with what the gate computed -- so both went stale for weeks while the docs
# moved on (#817), and "a file someone can read" was not what the gate had
# excluded. Now they are written only with --update-lists, and a run checks
# them like a ratchet:
#
#   an exclusion the published list does not name  -> FAIL (a hidden exclusion)
#   a published entry this run no longer excludes   -> note (shrink the list)
#
# Same shape as the baseline below and check_artefact_agreement's: fail on
# what is new, report what has gone. The cross-repo list depends on the
# siblings next to this checkout -- CI materialises them with
# tools/materialise_siblings.sh, and so should anyone regenerating the list.
# --update-lists is separate from --update-baseline on purpose: refreshing the
# published exclusions must not also launder new dangling references into the
# baseline.
from collections import Counter as _Counter
LISTS = {"doc_refs_crossrepo.txt": cross, "doc_refs_upstream.txt": upstream}
hidden = []
for _name, _rows in LISTS.items():
    _path = pathlib.Path(__file__).with_name(_name)
    if "--update-lists" in _s.argv:
        _path.write_text("\n".join(sorted(_rows)) + ("\n" if _rows else ""))
        print(f"list written: tools/{_name} ({len(_rows)})")
        continue
    _have = _Counter(l for l in (_path.read_text().splitlines() if _path.exists() else [])
                     if l.strip())
    _now = _Counter(_rows)
    _gone = sorted((_have - _now).elements())
    if _gone:
        print(f"\n{len(_gone)} entry/entries in tools/{_name} no longer excluded -- "
              f"run with --update-lists to shrink it:")
        for _l in _gone: print(f"  [gone] {_l}")
    hidden += [(_name, _l) for _l in sorted((_now - _have).elements())]
uniq = sorted(set(fails))
known = {l for l in BASE.read_text().splitlines() if l.strip()} if exists(BASE) else set()
# A baseline entry that no longer reproduces is a pre-approved defect: the
# reference was fixed, or now resolves somewhere, and the line stays in the
# baseline -- so if it breaks again, nothing says so. Seven sat there for
# weeks: references that resolve in a sibling were counted twice, as known rot
# AND as published cross-repo exclusions, so a sibling deleting the target
# would have passed in silence. PHPStan (reportUnmatchedIgnoredErrors) and
# ESLint's bulk suppressions fail on an unmatched entry for this reason; so
# does this gate. --prune-baseline only REMOVES entries (baseline & current):
# it cannot add one, so pruning never launders a new dangling reference, which
# is what --update-baseline would do.
stale = sorted(known - set(uniq))
if "--prune-baseline" in _s.argv and "--update-baseline" in _s.argv:
    # Together, the rewrite would win and silently undo the prune's promise.
    print("refusing --prune-baseline with --update-baseline: the update can add "
          "entries, the prune exists so that nothing is added -- pick one")
    _s.exit(2)
if "--prune-baseline" in _s.argv:
    kept = sorted(known & set(uniq))
    BASE.write_text("\n".join(kept) + ("\n" if kept else ""))
    print(f"baseline pruned: {len(stale)} removed, {len(kept)} kept")
if "--update-baseline" in _s.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known")
if any(f in _s.argv for f in ("--update-lists", "--update-baseline", "--prune-baseline")):
    _s.exit(0)
new = sorted(set(uniq) - known)
if new:
    print(f"\nFAIL: {len(new)} NEW dangling reference(s)\n")
    for f in new: print(f"  {f}")
if hidden:
    print(f"\nFAIL: {len(hidden)} exclusion(s) not in the published lists -- "
          f"run with --update-lists and commit them:\n")
    for _name, _l in hidden: print(f"  tools/{_name}: {_l}")
if stale:
    print(f"\nFAIL: {len(stale)} baseline entry/entries no longer reproduce -- "
          f"run with --prune-baseline and commit tools/doc_refs_baseline.txt:\n")
    for f in stale: print(f"  [stale] {f}")
if new or hidden or stale:
    _s.exit(1)
print(f"OK: no new dangling references ({len(known)} known, all still reproduce), "
      f"every exclusion published")
_s.exit(0)
