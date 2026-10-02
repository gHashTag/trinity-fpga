#!/usr/bin/env python3
"""Do the paper's quantitative claims still hold after fifteen passes of corrections?

Passes 231-247 changed goldens, rebuilt every vector pack, corrected oracles and
edited 4,776 sites of RTL. research/arxiv_submission/paper.tex asserts numbers
about that same corpus. Nothing had checked whether the assertions still match
what they assert about.

Four claims are checkable from this repository:

  vectors      "All oracles, vectors (2.4M), and ..." -- count them
  decode       "~41 of 83 catalog formats carry at least one bit-exact decode
                cell on silicon (41 decode ports)"
  gf compute   "of these, 10 GF formats (GF4--GF32) additionally carry bit-exact
                compute cells (ADD/MUL)"
  gf64         "GF64 reaches 70.1% (359/512) due to a timing-closure issue"

A fifth is not: "72 of 83" formats carrying an independent executable oracle needs
the catalog membership list, and the SSOT for that is formats_catalog.t27 in the
t27 repository, which is not present here. The oracles carry 84 format keys, but
several are known NOT to be catalog rows -- fp16_e6m9 and fp24_7m16 exist only in
the silicon-sprint packs, and bf16/bfloat16 is an alias pair -- so 84 neither
confirms nor refutes 72. It is reported and left open.

A cell counts only with all four Tier-E links in one comment: a public CI run
URL, the bitstream SHA-256, a UART "HW RESULT: N/N bit-exact" line, and the
matching IDCODE. That is the definition the paper itself uses one sentence later.

Usage:  python3 research/audit_paper_claims.py [--comments FILE]
"""
import collections
import glob
import importlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
PAPER = os.path.join(HERE, "arxiv_submission", "paper.tex")
sys.path.insert(0, CONF)

ISSUE = "repos/gHashTag/trinity-fpga/issues/199/comments?per_page=100&page=%d"
UART = re.compile(r"HW RESULT:\s*\d+/\d+\s*bit-exact", re.I)
SHA = re.compile(r"\b[0-9a-f]{64}\b", re.I)
CI = re.compile(r"actions/runs/\d+")
# Low 28 bits only: rev-1 silicon reads 0x13636093, the bench reads 0x03636093 (#633)
IDCODE = re.compile(r"0x[01]3636093", re.I)
PROOF = re.compile(r"Tier-E proof:\s*`?([\w_]+)`?\s*\(([^)]*)\)")
COMPUTE = re.compile(r"compute HW cell|compute-HW", re.I)
GF2 = re.compile(r"GF\(2([⁰¹²³⁴-⁹]+)\)")
SUP = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))


def comments(path=None):
    if path and os.path.exists(path):
        return json.load(open(path))
    out = []
    for page in range(1, 6):
        r = subprocess.run(["gh", "api", ISSUE % page], capture_output=True, text=True)
        if r.returncode:
            break
        d = json.loads(r.stdout)
        if not d:
            break
        out += d
    return out


def complete(cs):
    return [c for c in cs
            if UART.search(c["body"]) and SHA.search(c["body"])
            and CI.search(c["body"]) and IDCODE.search(c["body"])]


def main():
    path = None
    if "--comments" in sys.argv:
        path = sys.argv[sys.argv.index("--comments") + 1]
    cs = comments(path)
    full = complete(cs)

    vectors = 0
    for p in glob.glob(os.path.join(CONF, "vectors", "*.json")):
        vectors += len(json.load(open(p)).get("vectors", []))

    keys = set()
    for p in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        try:
            m = importlib.import_module(os.path.basename(p)[:-3])
        except Exception:                             # noqa: BLE001
            continue
        keys |= set(getattr(m, "FORMATS", {}))

    decode = set()
    for c in full:
        m = PROOF.search(c["body"])
        if m and "decode" in m.group(2).lower():
            decode.add(m.group(1))

    gf_compute = set()
    for c in full:
        if not COMPUTE.search(c["body"]):
            continue
        # The ledger writes the same width two ways -- "GF(2^16)" in some
        # comments and "gf16" in others -- so both have to normalise to one key
        # or a width gets counted twice. Keeping them separate reported 13 where
        # there are 10.
        m = GF2.search(c["body"])
        if m:
            gf_compute.add("gf" + "".join(SUP[ch] for ch in m.group(1)))
            continue
        m2 = re.search(r"\bgf(\d+)\b", c["body"], re.I)
        if m2:
            gf_compute.add("gf" + m2.group(1))

    gf64 = [c for c in full if re.search(r"\bgf64\b", c["body"], re.I)]
    n359 = [c for c in cs if "359/512" in c["body"]]
    n359_full = [c for c in n359 if c in full]

    def verdict(ok):
        return "HOLDS" if ok else "DOES NOT HOLD"

    print("complete Tier-E chains in issue #199 : %d of %d comments"
          % (len(full), len(cs)))
    print()
    print("%-12s %-34s %s" % ("claim", "paper says", "corpus says"))
    print("%-12s %-34s %s  %s" % ("vectors", "2.4M", "{:,}".format(vectors),
                                  verdict(2.35e6 <= vectors <= 2.45e6)))
    print("%-12s %-34s %d  %s" % ("decode", "~41 of 83 formats, 41 ports",
                                  len(decode), verdict(len(decode) == 41)))
    print("%-12s %-34s %d  %s" % ("gf compute", "10 GF formats (GF4-GF32)",
                                  len(gf_compute), verdict(len(gf_compute) == 10)))
    print("%-12s %-34s %d complete-chain mentions  %s"
          % ("gf64", "70.1% (359/512)", len(gf64), verdict(bool(gf64))))
    print("%-12s %-34s %d comments contain it, %d of them complete chains"
          % ("", "the string 359/512", len(n359), len(n359_full)))
    print()
    odd = sorted(w for w in gf_compute if w not in keys)
    if odd:
        print("NOTATION")
        print("  compute widths that are not format keys : %s" % ", ".join(odd))
        print("  The ledger writes GF(2^k) for a k-BIT format, so GF(2^2) reads as")
        print("  gf2 -- and the narrowest GF format in the corpus is gf4. The count")
        print("  of distinct widths is unaffected; which format that comment means")
        print("  is not settled by the notation.")
        print()
    print("NOT CHECKABLE HERE")
    print("  \"72 of 83 formats carry an independent executable oracle\".")
    print("  The catalog membership list is formats_catalog.t27 in the t27")
    print("  repository, which is not present. The oracles carry %d format keys,"
          % len(keys))
    print("  and several are known not to be catalog rows -- fp16_e6m9 and")
    print("  fp24_7m16 exist only in the silicon-sprint packs, bf16/bfloat16 is")
    print("  an alias pair -- so %d neither confirms nor refutes 72." % len(keys))
    bad = (len(decode) != 41) or (len(gf_compute) != 10) or not gf64
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
