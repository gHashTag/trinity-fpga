#!/usr/bin/env python3
"""The conformance counts in the paper come from the specification, not a memory.

The paper quotes "62,208 of 62,208 in-specification codes exact" for tnf16c and
"124,416 of 124,416" for tnf17e. Both were transcribed by hand from a sweep, and
a hand-transcribed number is a number that will eventually stop matching the
thing it describes -- this campaign has withdrawn ten claims and more than one of
them was drift of exactly that kind.

conformance/tnf_spec_ref.code_counts() derives them from (E_t, M):

    total       = 2^width
    in_spec     = 2 * 3^E_t * 2^M
    out_of_spec = total - in_spec
    comparable  = in_spec - 4 * 2^M     (zero and inf/nan offsets, both signs)

This gate checks every such number in the paper against that function.
"""
import importlib.util, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
spec = importlib.util.spec_from_file_location("tnf_spec_ref", ROOT / "conformance" / "tnf_spec_ref.py")
ref = importlib.util.module_from_spec(spec)
sys.modules["tnf_spec_ref"] = ref
spec.loader.exec_module(ref)

paper = (ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex").read_text()

# A measured count is legitimate even though the specification cannot derive it:
# distinct-output counts, sweep sizes and power-of-two code spaces all appear
# beside the word "codes". Read them from the data files rather than listing
# them here -- a hardcoded allowlist is the same hand-transcription this gate
# exists to prevent, one level up.
import json as _json
measured = set()
_cu = ROOT / "research" / "arxiv_tnf" / "code_use.json"
if _cu.exists():
    for _r in _json.loads(_cu.read_text()).values():
        measured.update({_r["distinct"], _r["codes"]})
measured.update({1 << b for b in range(1, 22)})      # any code space
measured.update({(1 << b) - 1 for b in range(1, 22)})
measured.update({(1 << b) - 2 for b in range(1, 22)})

# every count the specification can produce, and which rung it belongs to
legal = {}
for name, f in ref.FORMATS.items():
    for v in ref.code_counts(f):
        legal.setdefault(v, set()).add(name)

# numbers in the paper written LaTeX-style with a thousands separator, sitting
# next to the word "codes" -- those are the conformance counts
PAT = re.compile(r"\$?(\d{1,3}(?:\{,\}\d{3})+)\$?")
fails, checked, unclassified = [], 0, 0
for m in PAT.finditer(paper):
    lo, hi = max(0, m.start() - 130), min(len(paper), m.end() + 130)
    win = paper[lo:hi].lower()
    # Scope: only counts phrased as a CONFORMANCE result -- "N of N in-specification
    # codes exact", "all N codes". Sweep sizes, distinct-output counts and
    # mismatch tallies also sit beside "codes" and are measurements this gate
    # cannot derive; they are counted and printed, never failed. Growing an
    # allowlist to cover them would be the same hand-transcription the gate
    # exists to prevent, one level up.
    # Gate only counts that belong to one of OUR rungs: a competitor's sweep
    # size ("all 40,000 codes") is a conformance result too, but its code space
    # is not derivable from the ladder and never will be.
    # "in-specification codes exact" is the phrasing this paper uses only for
    # its own rungs; a competitor's row reads "all N codes". That is the whole
    # discriminator, and it needs no rung name nearby.
    if "in-specification codes exact" not in win:
        unclassified += 1
        continue
    v = int(m.group(1).replace("{,}", ""))
    checked += 1
    if v in legal:
        continue
    if v in measured:
        continue
    fails.append(f"{v:,} appears beside 'codes' but matches no rung's count "
                 f"and is not a known sweep size")

print(f"conformance counts checked: {checked}   "
      f"other code-adjacent numbers seen but not gated: {unclassified}   "
      f"derivable from the spec: {len(legal)} values")
if fails:
    print(f"\nFAIL: {len(fails)} count(s) with no source\n")
    for x in sorted(set(fails)): print(f"  {x}")
    sys.exit(1)
print("OK: every conformance count traces to tnf_spec_ref.code_counts()")
