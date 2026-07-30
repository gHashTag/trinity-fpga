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
import sys

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
        except Exception as e:  # import error is a real failure (CI must catch it)
            failed += 1
            failures.append((fn, "IMPORT", f"{type(e).__name__}: {e}"))
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
