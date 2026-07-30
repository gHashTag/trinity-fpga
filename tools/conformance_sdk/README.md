# Trinity Conformance SDK

A single API/CLI to **audit a low-precision numeric decoder against the Trinity
independent golden oracles**. This is the tooling counterpart of the
"format-conformance infrastructure" line in
`docs/funding/TRI-NET_grant_onepager_RU.md`: let an ML team plug in *their*
FP8 / OCP-MX / NF4 / posit / custom decoder and get a value-level bit-exact audit
against references they did not write.

> Status: `v0.1.0` — `[Verified SW]`. The golden oracles live in
> `conformance/*_ref.py` (exact `fractions.Fraction` arithmetic). HW-in-loop is
> out of scope here (see the AX7203 conformance scripts in `conformance/`).

## Install / layout
Pure Python, no extra deps (uses `fractions`, standard library). The package is
`tools/conformance_sdk/` and auto-discovers every `conformance/*_ref.py`.

## Catalog (one command)
```
python3 -m tools.conformance_sdk report
```
Reports every golden oracle (`conformance/*_ref.py`) discovered in this repo. The
count is computed dynamically at runtime as `len(catalog())` (not hard-coded), so
it tracks whatever oracles are present. As of this writing that is a superset of
the **83-format SSOT catalog** (canonical list: t27 `specs/numeric/formats_catalog.t27`):
it additionally carries GF width-extensions (gf48/64/96/128/256/512/1024),
legacy/historical floats (VAX, x87, Cray, PDP-11, IBM HFP, MS-MBF), decimal and
extended-precision oracles that live in this repo for testing but are outside the
83-format SSOT. Do not read the reported number as "the catalog size" — it is the
repo's oracle count; the SSOT is 83. The report also runs a golden-decode sanity
check per discovered format, grouped by family.

## Audit your decoder
```
python3 -m tools.conformance_sdk check \
    --format mxfp8_e4m3 \
    --decoder my_package:my_decode \
    --random 5000
```
`--decoder` is `module:func` (or `module.func`); `func(raw: int) -> value` where
`value` is a float, a `fractions.Fraction`, or a special sentinel (NaN/Inf/zero).
The checker runs your decoder over the SSOT vectors (when present) plus N random
raws within the format width, compares against the golden on the *mathematical
value* (NaN/Inf/zero compared by class — payload differences are not penalised),
and prints the match rate with the first mismatches. Exit code: `0` on 100%, `1`
otherwise — usable in CI.

## Encode & round-trip audit
Most oracles also provide a golden `encode(value) -> raw`. Three commands expose it:
```
# encode one value; shows the raw bits and what it decodes back to (exposes rounding)
python3 -m tools.conformance_sdk encode --format fp8_e4m3 --value 0.375
python3 -m tools.conformance_sdk encode --format fp8_e4m3 --value 3/8      # fraction
python3 -m tools.conformance_sdk encode --format fp8_e4m3 --value nan      # nan/inf/-inf

# round-trip audit vs golden (exhaustive for width <= 16, random sample above)
python3 -m tools.conformance_sdk roundtrip --format fp8_e4m3
```
`roundtrip` checks two independent properties and prints both rates (exit `0`
only if both are 100%):
- **encode-stable** (`raw -> value -> raw`): re-encoding a decoded value returns
  a raw that decodes to the *same value* (no representable value is lost). The
  bit pattern may legitimately differ (NaN payload, -0 vs +0), so the check is on
  the value, not the bits.
- **idempotent** (`value -> raw -> raw`): the projection onto the representable
  grid is stable under re-encoding.

## FP8 audit (built-in naive decoder)
`fp8_e4m3` is the classic trap: it has **no Inf**, and **NaN only at
exp=max & mant=max** — every other exp=max pattern is a *finite normal* (up to
±448). A textbook "exp all-ones ⇒ Inf/NaN" decoder silently turns the 14 largest
finite magnitudes into Inf/NaN, corrupting inference at the top of the range.
```
python3 -m tools.conformance_sdk fp8-audit --format fp8_e4m3
```
This ships a deliberately naive IEEE-rule decoder and audits it against the
golden over the full 256-code sweep, printing the exact raws where a naive
implementation is wrong (e4m3: 14 divergences at 0x78–0x7e / 0xf8–0xfe; e5m2:
0 — it is IEEE-like). Use it as a template check for your own FP8 kernel.

## Programmatic API
```python
from tools.conformance_sdk import check_decoder, audit_report, catalog
print(audit_report())
r = check_decoder("fp8_e4m3", my_decode, n_random=10000)
print(r["rate"], r["mismatches"][:5])

from tools.conformance_sdk.roundtrip import check_roundtrip, encode_value
from tools.conformance_sdk.fp8_audit import audit_fp8, naive_ieee_fp8
print(check_roundtrip("gf16"))        # exhaustive 65536/65536
print(encode_value("fp8_e4m3", "0.1"))  # {'exact': False, 'decodes_to': '0.1015625', ...}
print(audit_fp8("fp8_e4m3")["diverge_count"])  # 14
```

## Verification of v0.1
Self-check (user decoder == the golden itself) and a negative control:
```
nf4           16/16     100.00%
fp8_e4m3     256/256    100.00%   # exhaustive for 8-bit
mxfp8_e4m3   256/256    100.00%
binary16    2186/2186   100.00%   # SSOT vectors + random
posit8       256/256    100.00%
NEG-CONTROL fp8_e4m3(always 0.0)   0.93%   # the audit catches a wrong decoder
```

## Scope and honest limits (v0.1)
- Audits **decode** (raw → value) and **encode / round-trip** (value ↔ raw).
  ADD/MUL compute-audit is designed-in but not exposed in the CLI yet.
- `roundtrip`/`encode` require the ref to expose `encode()`; refs without it are
  reported as skipped (most do — bf16, fp8, gf, ieee, int, lns, mxfp, nf4,
  posit, takum, tekum, decimal, extended, legacy).
- The `fp8-audit` naive decoder is a *teaching control*, not a Trinity codec —
  it is intentionally wrong on e4m3 to demonstrate the audit; do not copy it.
- Comparison is on the binary64 value of the exact golden (golden decodes are
  exact; a correctly-rounded decoder matches). For formats wider than binary64
  (e.g. gf96+) the value-level audit still works because the SDK compares the
  golden's own exact value — but a *user* decoder returning a rounded binary64
  may show mismatches that are rounding, not bugs (interpret with that in mind).
- HW-in-loop (AX7203 UART) is a separate path; this SDK is the SW reference
  oracle side.

## License
Apache-2.0 (same as the rest of the repo).
