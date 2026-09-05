# DIV / SQRT Honesty Audit — binary32 proxy, NOT native GF compute

**Status:** Audit finding (Track C)
**Date:** 2026-07-14
**Scope:** `fpga/openxc7-synth/corona_compute_*_{div,sqrt}_ax7203.v`,
`gf_div_param.v`, `gf_sqrt_param.v`
**Verdict:** **Every div/sqrt cell on AX7203 is a binary32-proxy approximation,
not a native-format computation.** No div/sqrt cell is bit-exact and none is
counted in the catalog's Tier-E compute totals.

---

## 1. Headline finding

All `corona_compute_*_{div,sqrt}_ax7203.v` wrappers follow the **same dishonest
pattern**: decode the source format into IEEE-754 **binary32** (1S+8E+23M),
run the operation in binary32 via `gf_div_param` / `gf_sqrt_param`, then
quantize the binary32 result back into the source format.

This is true **even for formats that are NOT binary32** — GF16, GF32, fp24,
fp16, bf16, fp48, binary64, fp80, fp96, fp128, … every wrapper instantiates:

```verilog
gf_div_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp ( ... );   // binary32
gf_sqrt_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u_comp ( ... );  // binary32
```

Witnesses:
- `corona_compute_gf16_div_ax7203.v:92` — `gf_div_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1))`
- `corona_compute_gf16_sqrt_ax7203.v:73` — `gf_sqrt_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1))`
- `corona_compute_gf32_div_ax7203.v:96` — same binary32 core
- `corona_compute_gf32_sqrt_ax7203.v:77` — same binary32 core
- (and every other `corona_compute_*_{div,sqrt}_ax7203.v` — 26 files total)

### 1.1 What is lost by the binary32 round-trip

Because the operation happens in binary32 and is then re-quantized, the
**format-specific semantics of the source family are destroyed**:

1. **Rounding** — the source format's RNE/GRS is replaced by *two* roundings
   (source→binary32, then binary32→source). This is **double rounding** and can
   flip a correctly-rounded result by 1 ULP in either direction. For narrow
   formats (GF16, fp16, bf16) the binary32 intermediate is exact so the second
   rounding dominates; for wide formats (binary64, fp80, fp128) the binary32
   intermediate **truncates the operands before the operation**, so the result
   is silently wrong well beyond 1 ULP.
2. **Denormals / gradual underflow** — the wrapper maps source subnormals to a
   binary32 normal at a hardcoded exponent (e.g. `8'd113` for GF16, `8'd65` for
   GF32) and clamps anything below binary32's normal range to ±0. Source-format
   gradual underflow is **not** reproduced.
3. **Special-case semantics** — Inf/NaN/signed-zero propagation follows
   binary32 rules, not the source family's rules (e.g. GF6/GF8/GF12/GF20 have
   no Inf/NaN at all — `exp=all-ones` is a finite max-value — yet the wrapper
   synthesizes Inf/NaN codes through binary32).
4. **Overflow / family-split** — source-family overflow saturation
   (`HAS_INF=0` → max-finite) is approximated by clamping the binary32 exponent
   band, not by the family's own overflow law.
5. **Wide-format precision** — for binary64/fp80/fp96/fp128 the binary32 core
   computes on a **truncated** mantissa. The result is an approximation, not a
   rounded exact value; the error can be enormous (e.g. fp128 div is computed
   in 24 bits of precision, losing ~88 mantissa bits).

**Conclusion: a div/sqrt "cell" for format X is really a "binary32 cell with
X-shaped input/output sockets". It is not a format-X arithmetic unit.**

---

## 2. Specific bugs

### 2.1 `gf_sqrt_param.v` is hardcoded to binary32 despite its parameters

The module declares `EXP_BITS`, `MANT_BITS`, `TOTAL`, `BIAS` as parameters,
but the **entire datapath uses fixed 24-bit widths and binary32 magic
constants**, so it only functions at `MANT_BITS == 23`. Every wrapper passes
`MANT_BITS(23)` precisely because any other value is broken.

| Line | Code | Why it is binary32-only |
|------|------|-------------------------|
| `gf_sqrt_param.v:47` | `wire signed [22:0] exp_half` | fixed 23-bit width |
| `gf_sqrt_param.v:52` | `wire [23:0] mant24 = {1'b1, ma};` | assumes `ma` is 24 bits → only valid at `MANT_BITS=23` |
| `gf_sqrt_param.v:60` | `... - 24'h800000` | `0x800000` = 1.0 in Q24 |
| `gf_sqrt_param.v:62` | `24'h800000 - (x_minus_1 >> 1)` | Q24 magic constant |
| `gf_sqrt_param.v:67-70` | `reg [47:0] y_sq; reg [23:0] y_cur;` | 24/48-bit registers |
| `gf_sqrt_param.v:78` | `26'sd50331648` | `3.0` in Q24 (`3 << 24`) |
| `gf_sqrt_param.v:131` | `sqrt_mant[46:24-1+1]` | result slice assumes 24-bit mantissa |

**Effect:** the parameter interface is cosmetic. `gf_sqrt_param` is a binary32
rsqrt (Newton-Raphson, Quake-III-style magic guess) that cannot be retargeted
to any other width without rewriting the datapath.

### 2.2 NBA stale-output bug in BOTH `gf_div_param` and `gf_sqrt_param`

In the `FINISH` / `PACK` state, `result_packed` is assigned with a
**nonblocking** assignment (`<=`) and `out_y` is loaded from `result_packed`
in the **same** always block on the **same** clock edge:

```verilog
// gf_sqrt_param.v:111-134  (PACK state)
result_packed <= { ... };   // NBA: new value scheduled
...
out_y <= result_packed;     // NBA: reads the OLD result_packed
out_valid <= 1;
```

Because both are NBA, `out_y <= result_packed` captures the **previous** value
of `result_packed`, not the value computed in this cycle. `out_valid` asserts
one cycle early relative to the correct data. The same bug is present in the
divider:

```verilog
// gf_div_param.v:125-141  (FINISH state)
result_packed <= { ... };   // NBA
...
out_y <= result_packed;     // stale (one result behind)
out_valid <= 1;
```

**Effect:** when results stream back-to-back, every output is the *previous*
result. The bug is masked in the current UART wrappers only because they issue
one frame at a time and the stale read happens to land on a zeroed/reset
`result_packed` — but it is a genuine correctness defect in the core, and any
pipelined use would emit garbage.

### 2.3 No conformance vectors and no CI for div/sqrt

`t27/conformance/` contains golden vectors for ADD/MUL-adjacent formats
(`t27:conformance/gf{4,8,12,16,20,24}_vectors.json`, `sacred_physics*.json`,
`gf_family_bench.json`, `arch_bench.json`) but **zero** files referencing
division or square root:

```
t27/conformance/  ──(grep div|sqrt)──►  (no matches)
```

There is no `verify_div_rtl.py`, no `gf_div_ref_tb.v`, no random or exhaustive
div/sqrt oracle. The "compute-SW verified by two independent oracles" claim in
`CATALOG_MATRIX_83.md` applies to **ADD and MUL only**. The div/sqrt cores have
**no bit-exact witness of any kind** — not in simulation, not on silicon. Any
CI gate that appears to cover them is exercising the UART infra, not the
arithmetic result. (This is the "fake CI" item: the wrappers build and flash,
which looks like coverage, but nothing checks the numeric answer.)

---

## 3. What "native" div/sqrt would require

To replace the binary32 proxy with a genuine format-X division / square root,
one of the following is needed:

1. **Native per-family RTL.** A divider that operates on the source mantissa
   width directly (e.g. a restoring/SRT division over `2*(MANT+1)`-bit
   dividend, RNE rounding from the exact remainder, family-split overflow,
   gradual underflow packed from the exact quotient — mirroring what
   `gf_mul_param.v` already does for the product). Same for sqrt
   (digit-recurrence, or a width-parameterized Newton-Raphson whose Q-format
   constants are derived from `MANT_BITS` rather than hardcoded to 24).
2. **Honest proxy + documented error bound.** Keep the binary32 round-trip but
   (a) fix the NBA stale-output bug, (b) measure the worst-case ULP error per
   format against a high-precision oracle (Python `Fraction` / `mpmath`), and
   (c) publish the error bound so the proxy is an *approximation with a stated
   guarantee* rather than an unmarked substitution. For narrow formats
   (≤binary32 precision) the error is ≤1 ULP after the double-rounding fix;
   for wide formats (binary64/fp80/fp96/fp128) the proxy is unusable as-is
   because the input is truncated.

Either path also needs conformance vectors and a second independent oracle
(the same two-oracle discipline used for ADD/MUL in `gf_adder_param` /
`gf_mul_param`).

---

## 4. Recommendation (for the paper and the catalog)

- **In the paper**, describe div/sqrt as a **"binary32-proxy approximation, not
  bit-exact"**. Do not list div/sqrt cells alongside the GF4–GF32 ADD/MUL/SUB
  bit-exact cells. If a div/sqrt datapath is shown, label it
  *"binary32 intermediate, ≤1 ULP for ≤24-bit mantissa formats; approximate for
  wider formats"* and cite the double-rounding caveat.
- **In `CATALOG_MATRIX_83.md`**, the compute-HW Tier-E totals must **exclude**
  div/sqrt (they already do — the totals say "ADD 10/10 + MUL 10/10 + SUB
  10/10"). Any future div/sqrt claim must carry an explicit
  "binary32 proxy, not native format" asterisk. (An asterisk note has been
  added to the catalog alongside this audit.)
- **Fix the NBA stale-output bug** in `gf_div_param.v:141` and
  `gf_sqrt_param.v:134` (move `out_y <= result_packed` to the cycle after the
  pack, or compute `result_packed` combinationally so the NBA reads the new
  value) before trusting any div/sqrt output, even as an approximation.
- **Add div/sqrt conformance vectors** (exhaustive for GF4/GF6/GF8, large
  random for the rest) with two independent oracles before claiming any
  div/sqrt coverage tier.

---

## 5. File index

| File | Role | Honest status |
|------|------|---------------|
| `fpga/openxc7-synth/gf_div_param.v` | parametric divider core (claimed) | NBA stale-output bug (`:141`); no conformance vectors; only ever used at binary32 |
| `fpga/openxc7-synth/gf_sqrt_param.v` | parametric sqrt core (claimed) | **hardcoded to binary32** (`:47,52,60,62,78,131`); NBA stale-output bug (`:134`) |
| `fpga/openxc7-synth/corona_compute_*_{div,sqrt}_ax7203.v` (26 files) | AX7203 wrappers | all decode→binary32→compute→quantize; not native format |

*Honesty note: Vasilev, ORCID 0009-0008-4294-6159. This document describes a
proxy/approximation, not bit-exact native hardware.*
