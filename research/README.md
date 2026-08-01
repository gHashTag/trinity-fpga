# Reproducing the numbers in this directory

Every claim recorded in `specs/numeric/*.t27` and cited in
`VERIFICATION_DOSSIER.md` comes from a script here. This file says how to re-run
each one and what it should print.

It exists because of a defect found in this campaign's own work: pass 51 tried to
re-run the ml_dtypes cross-validation on a clean machine and got an `ImportError`
instead of a number. The claim was true — it reproduced exactly once the dependency
was installed — but nothing said a dependency was needed. A result that holds only
in the environment that produced it is weaker than one that says what it requires.

## Dependencies

Measured by AST across **all 49 scripts** in this directory, so lazy imports inside
functions are included. (This table said "15 scripts" until 2026-08-02; the directory
grew and the count did not. The conclusion did not change.)

| scripts | need |
|---|---|
| `crossval_ml_dtypes.py` | `ml_dtypes==0.5.4`, `numpy` |
| 8 others | an in-tree module — `conformance/gf_ref.py`, `conformance/tekum_ref.py`, `conformance/verify_adder_e24.py`, or `research/bibliography_defects.py` |
| **the remaining 40** | **Python standard library only** |

So the third-party surface is one script. For that one:

```bash
python3 -m pip install 'ml_dtypes==0.5.4' numpy
```

Prefer an isolated environment — nothing here needs to be installed system-wide.

Two scripts additionally consume data produced by a C bridge (`libtakum_bridge.c`)
and take their input paths as arguments; see their docstrings for the exact `cc`
invocation. They are not runnable without a built libtakum, and say so on exit 2.

## What each script should print

Run from the repository root.

| script | expected result | exit |
|---|---|---|
| `verify_phi_rule.py` | `catalogued GF formats satisfying the rule: 17/17` | 0 |
| `verify_lucas_exact.py` | identity holds for every n in 1..256 at 500 digits; worst residue `4.000E-392` at n=256 | 0 |
| `crossval_ml_dtypes.py` | `total codes compared: 66224   divergences: 0` (14 zero-sign codes excluded) | 0 |
| `verify_oracle_exactness.py` | all 12 uncaveated oracles return exact carriers | 0 |
| `verify_extended_expansion.py` | `double_double` and `quad_double` hold non-overlap | 0 |
| `verify_quire_associativity.py` | locates the documented boundary; not a defect report | 0 |
| `gen_conformance_pack.py` | regenerates a pack | 0 |
| `verify_arithmetic_invariants.py` | commutativity etc. across families; **slow** — see below | 0 |
| `verify_wide_arithmetic.py` | all six laws over 16 GoldenFloat widths through gf1024; `violations: 0` in ~1 s | 0 |

### Scripts that exit non-zero on purpose

A non-zero exit here means *the script found what it was built to find*, not that
it failed:

| script | exit | why |
|---|---|---|
| `verify_negation_invariant.py` | 1 | a family violates its own encoding's negation rule — the finding is the point |
| `audit_generated_packs.py` | 1 | reports the unresolved tekum oracle question |
| `crossval_libtakum.py` | 2 | missing input: needs the C bridge's TSV files as arguments |
| `proto_takum_decode_log.py` | 2 | same — takes a TSV path |

### The one genuine caveat

`verify_arithmetic_invariants.py` samples `K = 24` codes per format and tests all
`24 × 24 = 576` ordered pairs. Cost is `O(k²)` per format with exact rational
arithmetic, and on the wide GoldenFloat rungs a single multiply is enormous — it
did **not** complete within 600 s on an arm64 Mac. Budget accordingly, or expect
the same non-termination recorded in
`specs/numeric/arithmetic_invariant_sweep.t27` for gf64 and above.

`verify_wide_arithmetic.py` covers the GoldenFloat ladder that sweep cannot reach,
in about a second, by sampling exponents near 1.0 instead of across the whole
range. The cause of the blowup is documented in
`specs/numeric/wide_rung_commutativity.t27`: a denormal's `Fraction` denominator
needs roughly `bias` bits, which is 8.4 Mbit at gf64 and physically impossible
above gf96. Its coverage is correspondingly narrower — read the scope lines it
prints.

Note on reading `verify_arithmetic_invariants.py`'s output: the counts it shows
under `x*0` are **not** defects. They are `mul(-x, 0)` returning negative zero,
whose raw code differs from `pos_zero` while the value is still zero. That law has
to be stated over values, not codes; `verify_wide_arithmetic.py` does so and reports
`OK`.

## Reading the results

Each script prints its own scope limits, and several print the reason a result is
weaker than it looks (`sampled, not exhaustive`; `verifies the identity, not the
implementation`). Those lines are part of the result — the specs quote them rather
than the headline number alone, and anyone citing these figures should do the same.

## Two results that depend on the interpreter

`verify_oracle_exactness.py` reports **12** oracles with `numpy` installed and
**11** without — `gf_mx_ref.py` imports numpy, and on an interpreter lacking it the
oracle is *not tested* rather than failed. The script now says so explicitly and
still exits 0; an earlier version counted the load failure as an exactness failure
and printed "1 oracle did not satisfy the exactness they claim" about an oracle it
had never run.

The dossier's "12 oracles verified exact, 19,106 codes" figure is therefore correct
**with numpy present**. Without it the count is 11.

## Reading crossval_p3109.py's exit code

It exits **0** when the finite codes agree *or* differ by a single uniform ratio,
and **1** only when the ratios scatter. That is deliberate: P3109 uses
`bias = 2^(e-1)` where IEEE 754 and OCP use `2^(e-1) - 1`, so every finite value
differs by exactly a factor of two — measured across 258,524 codes at two widths,
one distinct ratio. A constant offset is two correct decoders reading two
conventions; a *scattered* set of ratios would be a defect.

An earlier version exited 1 on any difference, which contradicted the script's own
printed conclusion.
