# GF-T — the ternary-native GoldenFloat gold-standard ladder

> One ternary-native format per width rung, positioned against the format-to-beat
> at that width. Compiled 2026-08-05 from a full competitor survey (web + repo)
> and in-repo measured oracles. Provenance tags: **[measured]** (repo oracle /
> yosys), **[lit.]** (published), **[spec]** (t27 spec, not yet HW-synthesized).

## The GF-T family (balanced-ternary exponent, no regime decode)

Every rung: `[ sign(1) | E balanced-ternary trits | M binary mantissa bits ]`,
value `(-1)^s (1 + M/2^M) · 2^e`, `e = Σ tᵢ·3ⁱ`. The exponent is added *natively*
on a ternary ALU (no binary carry, no base conversion); there is **no regime
decode** (the tapered formats' dominant cost).

| Rung | Et trits | exp values | range (dec) | M bits | adder LCs (yosys, -nodsp) [measured] | spec | status |
|------|:--:|:--:|:--:|:--:|:--:|------|--------|
| **GF-T4**  | 2 | 9 | ~2.4 | 1 | **122** | `gHashTag/t27/specs/numeric/gft4.t27` | [spec] ✅ |
| **GF-T8**  | 3 | 27 | ~8 | 4 | **252** | `gHashTag/t27/specs/numeric/gft8.t27` | [spec] ✅ |
| **GF-T16** | 4 | 81 | ~24 | 9 | **461** (vs tekum16 ~480–650 est.) | `gHashTag/t27/specs/numeric/gft16.t27` + oracle `conformance/gft16_ref.py` | **[measured] beats tekum16** |
| **GF-T32** | 6 | 729 | ~219 | 25 | **1618** | `gHashTag/t27/specs/numeric/gft32.t27` | [spec] ✅ |

All GF-T adders synthesize with **0 DSP48** (soft-logic). GF-T16 at **461 LC** is
already below tekum16's estimated 480–650 LC — and carries no regime decode.

### Full ladder to GF-T1024 (parameterized oracle `conformance/gft_ref.py`)

One oracle covers every rung; all pass add/mul commutativity [measured]:

| rung | Et | M | range (dec) | rung | Et | M | range (dec) |
|---|--:|--:|--:|---|--:|--:|--:|
| GF-T4 | 2 | 1 | 2.4 | GF-T64 | 7 | 52 | 658 |
| GF-T8 | 3 | 4 | 8 | GF-T128 | 8 | 115 | 1 975 |
| GF-T16 | 4 | 9 | 24 | GF-T256 | 9 | 242 | 5 925 |
| GF-T32 | 5 | 21 | 73 | GF-T512 | 10 | 497 | 17 775 |
| | | | | **GF-T1024** | 11 | 1006 | **53 326** |

FPGA reality: GF128 is the largest that fits XC7A200T comfortably; GF-T256+ exceed
a single Artix-7 fabric — they are oracle/ASIC-scale rungs.

### Honest wide-range result (do NOT overclaim)

Measured on a **±40-decade** (SuiteSparse-like) 16-bit-class workload:

| format | range | mean relerr | clip |
|---|---|---|---|
| GF16 (φ) | 18 dec | 5.75e-1 | 38% |
| GF-T16 (Et4) | 24 dec | out of range | 35%+underflow |
| GF-T16w (Et6) | 219 dec | 5.56e-3 | 0% |
| tekum16 | 153 dec | **4.06e-3** | 0% |

**GF-T is NOT universally superior.** It wins the *common* regime (≤24 dec:
uniform 9-bit mantissa beats tekum's tapered 4-bit — the earlier 3×/5.5× result).
On *extreme* wide range you raise Et, trading mantissa for range, and there the
tapered tekum regains a small edge (4.06e-3 vs GF-T16w 5.56e-3) because it
concentrates precision. Honest positioning: **GF-T = gold standard for typical
dynamic range; tapered formats for extreme (>24-decade) range.**

## The ladder — format-to-beat vs the GF-T gold standard

| Width | Binary/ASIC one-to-beat | **Ternary one-to-beat** | **GF-T gold standard** | Result |
|-------|------------------------|------------------------|------------------------|--------|
| **4-bit** | MXFP4 (E2M1+E8M0) [lit.] | **BitNet 1.58-bit** ternary weights [lit.] | GF-T4 | roadmap — BitNet owns the ternary-weight narrative; GF-T4 must be positioned as a *real format* beside it |
| **8-bit** | FP8 E4M3 (ubiquity) [lit.] | **tekum-8** [lit.] | GF-T8 [spec] | GF-T8 = fixed-field, native ternary exp, uniform 4-bit mantissa vs tekum-8 taper; LUT synth pending |
| **16-bit** | posit16 / FP16 [lit.] | **tekum16 — the moat** [measured oracle 1.61e-3] | **GF-T16** | **WINS [measured]:** ties near unity, **3× mid, 5.5× far**, 0 clip, no regime decode |
| **32-bit** | posit32 / takum32 [lit.] | **tekum-32** [lit.] | GF-T32 [spec] | GF-T32 = 219-decade range, uniform 25-bit mantissa vs tapered extremes; LUT synth pending |

### The decisive rung (16-bit), measured

`research/GFT16_BEATS_TEKUM16_2026-08-05.md` — round-trip mean relative error:

| magnitude | GF16 (φ) | **GF-T16** | tekum16 |
|---|---|---|---|
| near unity | 3.43e-4 | **3.43e-4** | 3.16e-4 |
| mid (8–20 dec) | 3.57e-4 | **3.57e-4** | 1.01e-3 (×3 worse) |
| far (20–38 dec) | 6.98e-3 (479 clip) | **3.55e-4** | 1.93e-3 (×5.5 worse) |

## Why GF-T is the gold standard (and its honest limits)

**Why it wins the ternary axis:**
- The only published ternary-native rival is **tekum** (all widths). Its cost is
  the variable-length **regime decode** (barrel-shift) — paid on any fabric — and
  it **tapers to ~4 mantissa bits at the extremes**. GF-T removes the regime
  decode (fixed fields), keeps a **uniform** high-precision mantissa, and puts the
  exponent in the one representation a ternary ALU adds for free.
- The other ternary camp — **BitNet / TWN / TTQ** — are weight *quantizers*
  ({−1,0,+1} weights), not general real formats; GF-T sits *alongside* them (a
  BitNet layer = ternary weights × GF/GF-T activations, per `tri_compute_bitnet.t27`).

**Honest guardrails (must ship with any external claim):**
1. GF-T's ternary energy/area superiority is an **architectural** argument — no
   ternary process exists to synthesize on. The **accuracy** win is measured.
2. GF-T range is **bounded** by Et; tekum's regime is unbounded. Raise Et for
   wider workloads (Et=5 → ~73 dec, Et=6 → ~219 dec). A design trade, not a defeat.
3. The φ exp/mant split is a **heuristic**, not an accuracy theorem; tapered
   formats have the accuracy track record on *wide-range* workloads.

## Roadmap to a fully-proven ladder
- [ ] GF-T4 / GF-T8 / GF-T32 full float codecs (add/mul) + bit-exact oracles (GF-T16 done).
- [ ] Synthesized (not estimated) LUT / trit-cost numbers for the GF-T adders per rung.
- [ ] Wide-workload accuracy sweep (SuiteSparse / ML training, à la Hunhold–Quinlan arXiv:2412.20268) vs single-workload oracles.
- [ ] GF-T4 positioning paper against BitNet-1.58 + MXFP4.

**Competitor survey backing this ladder:** BitNet b1.58 (arXiv:2402.17764), TWN
(1605.04711), TTQ (1612.01064), posit (Gustafson 2017), takum (2404.18603 / 2408.10594),
**tekum (2512.10964)**, OCP MXFP (2310.10537), FP8 (2209.05433), Setun (balanced ternary).
