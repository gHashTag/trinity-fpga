#!/usr/bin/env python3
"""Run every golden oracle's `_selftest()` in CI.

Run from the repo root as:  python3 conformance/run_selftests.py
(uses an import context with `conformance/` on sys.path so sibling refs that
`import gf_ref` etc. resolve; refs without `_selftest` are reported and skipped).

Exit code: 0 only if every ref that HAS a _selftest passes it.
"""
from __future__ import annotations
import importlib
import os
import re
import sys

# A ref only matters to this gate if it declares a `_selftest`. Some refs import
# optional third-party deps (e.g. gf_mx_ref imports numpy) at module top-level but
# have NO _selftest, so they are skipped anyway. In a clean CI interpreter that
# optional dep may be absent; an ImportError on such a ref must NOT fail the gate
# (it would have been skipped). We detect "declares a _selftest" from source text
# (cheap, no import) to decide whether an import failure is fatal.
_SELFTEST_RE = re.compile(r"^\s*def\s+_selftest\s*\(", re.MULTILINE)


def _declares_selftest(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return bool(_SELFTEST_RE.search(fh.read()))
    except OSError:
        return False

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)   # sibling `import gf_ref` inside conformance/
sys.path.insert(0, REPO)


def main() -> int:
    refs = sorted(f for f in os.listdir(HERE)
                  if f.endswith("_ref.py") and not f.startswith("_"))
    passed = skipped = failed = 0
    failures = []
    for fn in refs:
        modname = fn[:-3]  # strip .py
        try:
            m = importlib.import_module(modname)
        except Exception as e:
            # Import error is fatal ONLY if this ref actually has a _selftest we
            # were supposed to run. A ref with no _selftest (would be skipped) that
            # fails to import on an optional dep is skipped, not failed.
            if _declares_selftest(os.path.join(HERE, fn)):
                failed += 1
                failures.append((fn, "IMPORT", f"{type(e).__name__}: {e}"))
                print(f"FAIL  {fn:<22} IMPORT {type(e).__name__}: {str(e)[:120]}")
            else:
                skipped += 1
                print(f"SKIP  {fn:<22} (no _selftest; import skipped: "
                      f"{type(e).__name__})")
            continue
        st = getattr(m, "_selftest", None)
        if not callable(st):
            skipped += 1
            print(f"SKIP  {fn:<22} (no _selftest)")
            continue
        try:
            st()
            passed += 1
            print(f"PASS  {fn:<22}")
        except Exception as e:
            failed += 1
            failures.append((fn, type(e).__name__, str(e)[:120]))
            print(f"FAIL  {fn:<22} {type(e).__name__}: {str(e)[:120]}")

    print(f"\n{passed} passed, {skipped} skipped (no _selftest), {failed} failed")
    if failures:
        print("Failures:")
        for fn, t, msg in failures:
            print(f"  {fn}: {t} {msg}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
