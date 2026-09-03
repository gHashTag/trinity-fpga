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
import re, pathlib, sys

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
        return p.exists()
    except OSError:
        return False


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
        SIBLINGS = ["t27", "trinity-s3ai", "claim-audit-lab", "tri-net", "trios-mesh"]
        cands = [ROOT / p, ROOT / "tools" / p, ROOT / "conformance" / p,
                 ROOT.parent / p, d.parent / p] + [ROOT.parent / sib / p for sib in SIBLINGS]
        # a bare filename may live anywhere in the tree
        if "/" not in p:
            if p in _OWN: continue
            _hit = next((s_ for s_ in SIBLING_NAMES if p in _SIB[s_]), None)
            if _hit:
                # Excluded, but RECORDED. An exclusion nobody can see reads as
                # coverage. These references resolve only in a sibling repo, so
                # CI -- which has no siblings -- cannot tell them from rot; that
                # is a reason to name them, not to drop them silently.
                cross.append(f"{str(d.relative_to(ROOT))}: names `{p}`" f" -> resolves in {_hit}")
                continue
        _sib = next((sib for sib in SIBLINGS if exists(ROOT.parent / sib / p)), None)
        if _sib and not exists(ROOT / p):
            # Same rule as the bare-name case: excluded, but named. CI has no
            # siblings, so it cannot tell this from rot -- which is why the
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
(pathlib.Path(__file__).with_name("doc_refs_crossrepo.txt")
 .write_text("\n".join(sorted(cross)) + ("\n" if cross else "")))
# Written for the same reason as the cross-repo list: an exclusion nobody can
# see reads as coverage. These are the references the gate deliberately does
# not verify, in a file someone can read.
(pathlib.Path(__file__).with_name("doc_refs_upstream.txt")
 .write_text("\n".join(sorted(upstream)) + ("\n" if upstream else "")))
uniq = sorted(set(fails))
if "--update-baseline" in _s.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); _s.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if exists(BASE) else set()
new = sorted(set(uniq) - known)
if new:
    print(f"\nFAIL: {len(new)} NEW dangling reference(s)\n")
    for f in new: print(f"  {f}")
    _s.exit(1)
print(f"OK: no new dangling references ({len(known)} known)")
_s.exit(0)
if fails:
    print(f"\nFAIL: {len(fails)} reference(s) to files that are not there\n")
    for f in sorted(set(fails)): print(f"  {f}")
    sys.exit(1)
print("OK: every file named in a document exists")
