#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Can every oracle be loaded by the loaders that sweep for them?

Pass 156 found `verify_negation_invariant.py` printing "no golden oracle" for all four
takum widths. No oracle was missing. `conformance/takum_log_ref.py` was failing to
import, and the handler swallowed it.

The cause is specific and repeatable. A module using `@dataclass` looks itself up in
`sys.modules` while the decorator runs. Loaded through `spec_from_file_location` under a
synthetic module name and executed without being registered first, it is not there, and
the import dies with `'NoneType' object has no attribute '__dict__'`.

Pass 157 measured the blast radius rather than assuming it:

    17 scripts use spec_from_file_location; 16 did not register
    18 oracles in conformance/*_ref.py; exactly 1 fails that way -- takum_log_ref.py
    8 of those scripts sweep every *_ref.py, so all 8 silently omitted it

Including `crossval_libtakum.py` -- the script whose whole purpose is cross-validating
takum against libtakum, structurally unable to see the logarithmic takum oracle. That is
a large part of why passes 144 to 146 spent three passes on the wrong comparand.

This check keeps both halves honest: every oracle must load under the pattern the
sweeping loaders use, and every sweeping loader must register before executing.

    python3 research/audit_module_loaders.py [--self-check]
"""
from __future__ import annotations

import glob
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")

SEARCH = ["research/*.py", "conformance/*.py", "tools/**/*.py"]


def loaders() -> list[tuple[str, bool, bool]]:
    """(path, registers_in_sys_modules, sweeps_every_ref) for each dynamic loader."""
    out = []
    seen = set()
    for pat in SEARCH:
        for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if p in seen:
                continue
            seen.add(p)
            text = open(p, encoding="utf-8", errors="replace").read()
            if "spec_from_file_location" not in text:
                continue
            registers = "sys.modules[" in text
            sweeps = bool(re.search(
                r'endswith\(["\']_ref\.py["\']\)|glob[^\n]*_ref\.py', text))
            out.append((os.path.relpath(p, ROOT), registers, sweeps))
    return sorted(out)


def unloadable() -> list[tuple[str, str]]:
    """Oracles that fail under the unregistered pattern the sweepers use."""
    bad = []
    if CONF not in sys.path:
        sys.path.insert(0, CONF)
    for p in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        fn = os.path.basename(p)
        name = "probe_" + fn[:-3]
        try:
            spec = importlib.util.spec_from_file_location(name, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)          # deliberately unregistered
        except Exception as e:
            bad.append((fn, f"{type(e).__name__}: {str(e)[:60]}"))
        finally:
            sys.modules.pop(name, None)
    return bad


def self_check() -> int:
    """The probe must actually reproduce the failure it was written for. If
    takum_log_ref.py ever loads unregistered, this check has stopped testing anything
    and should say so rather than report a clean sweep."""
    bad = [fn for fn, _ in unloadable()]
    ok = "takum_log_ref.py" in bad
    print(f"  takum_log_ref.py fails unregistered -> {ok}  "
          f"{'ok' if ok else 'THE PROBE NO LONGER REPRODUCES THE FAULT'}")
    print(f"\nself-check: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    ls = loaders()
    sweepers = [l for l in ls if l[2]]
    unregistered = [l for l in ls if not l[1]]
    at_risk = [l for l in sweepers if not l[1]]
    bad = unloadable()

    print(f"dynamic loaders found              : {len(ls)}")
    print(f"  register before executing        : {len(ls) - len(unregistered)}")
    print(f"  do NOT register                  : {len(unregistered)}")
    print(f"  of which sweep every *_ref.py    : {len(at_risk)}\n")

    print(f"oracles in conformance/*_ref.py    : "
          f"{len(glob.glob(os.path.join(CONF, '*_ref.py')))}")
    print(f"  fail under an unregistered load  : {len(bad)}")
    for fn, err in bad:
        print(f"    {fn:<24} {err}")

    if at_risk:
        print(f"\nSWEEPING LOADERS THAT WOULD MISS THEM: {len(at_risk)}")
        for path, _, _ in at_risk:
            print(f"    {path}")

    print("""
A sweeping loader that does not register is only a problem when an oracle needs it, and
today exactly one does. That is why this reports both halves: the count of fragile
loaders alone would overstate the damage, and the count of failing oracles alone would
hide who cannot see them.

--self-check requires the probe to still reproduce the original failure. If
takum_log_ref.py ever loads unregistered, this check has stopped testing anything, and a
clean sweep from a blind probe is worth less than no sweep at all.""")
    return 1 if at_risk else 0


if __name__ == "__main__":
    raise SystemExit(main())
