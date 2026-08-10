# RETRACTED — this withdrawal was wrong. The Fmax figures are real nextpnr-xilinx measurements.

**Everything previously in this file is withdrawn. I claimed the ladder Fmax numbers had no
source and implied they were unsupported. They are backed by 298 nextpnr-xilinx logs sitting in
the same directory. The error was mine and it was serious: I accused correct work of reporting
unmeasured numbers.**

## The evidence I missed

    247.10  ->  fpga/phiscale/cs_phi32_4.log
    231.21  ->  fpga/phiscale/cs_plas32_3.log
    184.98  ->  fpga/phiscale/cs_d4_32_3.log

29 distinct designs, 298 log files, ~5 seeds each — exactly the "median of five seeds" the table
claims. The logs are unambiguously **nextpnr-xilinx targeting an XC7A200T**:

    Info:     Created 89 SLICE_LUTX cells from: 9x LUT6
    Info:     Created 80 SLICE_FFX  cells from: 48x FDRE
    Info:              SLICE_LUTX:    89/269200
    Info:                  CARRY4:     0/33650
    $auto$xilinx_dffopt.cc:347:execute$2580

`SLICE_LUTX`, `SLICE_FFX`, `CARRY4`, the 269200 cell count and `xilinx_dffopt.cc` are
nextpnr-xilinx internals. ECP5 would emit `TRELLIS_*`; nothing else produces these.

## How I got it wrong

1. **I searched for the wrong filenames.** I looked for `.fasm`, `.bit`, and names containing
   "route", "timing" or "report". The evidence was in `.log` files, 298 of them, in the directory
   I was standing in. A single `ls *.log` would have settled it.

2. **I treated a stale README as authoritative.** `fpga/phiscale/README.md` says "No Fmax.
   `nextpnr-xilinx` is not installed on this machine." That note belongs to an **earlier** design
   (`scale_phi`) from before the tool was available. I read it as a statement about the ladder
   runs and concluded the two documents contradicted each other. They do not — one is simply
   older than the other.

3. **`which nextpnr-xilinx` returning nothing proved less than I assumed.** The binary is not on
   the PATH *now*. That says nothing about whether it was available when the runs were made, and
   the logs show it was.

4. **I escalated on absence of evidence.** Having failed to find a source, I wrote that the
   numbers "match nothing measurable here" and described the provenance line as one that "cannot
   be right". Two of my own checks had already come back inconclusive (a bad awk aggregation, a
   grep that matched digit substrings) and I proceeded anyway.

## The second error, which followed from the first

I ran the three designs through **ECP5** place-and-route, got 324.68 / 320.92 / 308.64 MHz, and
concluded that the "25 % slower at degree 4" claim was "wrong in direction, not just provenance"
because ECP5 showed only 4.9 %.

That comparison was meaningless. On the fabric the table actually names:

    phi  247.10 MHz     deg4 184.98 MHz     ->  25.2 % slower

**The original claim is exactly right.** Fabric changes timing ratios — that is why the device is
named in the heading — and I compared across fabrics as though it were a contradiction.

The ECP5 numbers themselves are valid measurements of a different device, and the FF column
matching (192/200/320) is a coincidence of the design, not evidence of mixed provenance as I
claimed.

## Corrections now applied

- `LADDER_THIRD_MODEL_BREAKS_4BIT_2026-08-10.md` — the LUT/reg/Fmax columns are **restored**, and
  my "withdrawn / unsourced" annotations removed.
- `research/ladder/cost_surviving.py` — the "UNSOURCED, do not cite" comment is **removed**; the
  table is measured, on xc7a200t, via nextpnr-xilinx, with logs on disk.
- Memory §59 and §60 are corrected in place.

## What this episode is worth keeping

The provenance question was reasonable; the conclusion was not. **A failed search is not a
finding.** The standard I applied to competitor formats — implement from the source, never from
memory — has an obverse I did not apply here: *before asserting that a measurement does not
exist, exhaust the search*. `ls *.log` in the working directory would have cost one second.

What survives from the audit, and is worth doing properly: the decoder table in section 01
(974.66, 925.93, …) does **not** appear in these 298 logs. That is not an accusation — those runs
are from a different campaign and their logs are presumably elsewhere. Locating them is the
correct next step, and the correct way to state the current position is *"not yet located"*, not
*"unsourced"*.

---

# Audit closed: every number located, plus one real qualification

An independent agent searched **by value rather than by guessed filename** — the method my own
failed search should have used.

## Section 01 (decoders): located, 10 of 10 reproduce exactly

`fpga/tnet/ws_*.log` — **110 logs = 22 designs × 5 seeds.** Not `fpga/phiscale/`, and the prefix
is `ws_`, not `cs_`. Every quoted value reproduces as the median of five seeds:

    gfternary  66 LUT  [994.04, 994.04, 974.66, 860.59, 957.85] -> med 974.66  ✓
    int8       76      [949.67, 999.00, 859.11, 893.66, 925.93] -> med 925.93  ✓
    posit32   517      [ 45.62,  51.87,  49.05,  51.08,  45.43] -> med  49.05  ✓
    posit64  2629      [  6.82,   6.66,   6.35,   6.91,   6.78] -> med   6.78  ✓
    … all ten, to the cent

Tool unambiguous: all 110 logs carry `SLICE_LUTX`, `CARRY4: 0/33650`, `269200`,
`$auto$xilinx_dffopt.cc` and Artix-7 `LIOB33_*` tile names; **zero** contain `TRELLIS`. The
driving scripts name the binary and chipdb explicitly:
`t27/target/nextpnr-xilinx/build/nextpnr-xilinx` with `chipdb/xc7a200tfbg484.bin`.

Section 03's logs are in `phiscale/` after all, under the `cs_e_` prefix: phi 89/621.89,
r5 95/482.39, r6 122/612.00 — 15 logs, 3 designs × 5 seeds, all exact.

## The qualification the audit did find

**The timing constraint in `fpga/tnet/bench.xdc` was not applied.** The file ends with
`create_clock -period 5.000` (200 MHz), yet **all 110 `ws_` logs and all 30 `cs_e_` Fmax lines
read `(PASS at 12.00 MHz)`** — nextpnr-xilinx did not consume the `create_clock` and fell back to
its 12 MHz default.

So these Fmax figures are nextpnr's **unconstrained post-route critical-path estimates**, with no
timing-driven placement pressure toward a real target. This applies **uniformly to every design in
both campaigns**, so the relative comparisons and ratios — which are what the claims rest on — are
apples-to-apples and unaffected.

**But the absolute numbers should be labelled unconstrained estimates rather than signed-off
timing closure**, and ~975 MHz for GFTernary in particular reads as implausibly high for
Artix-7 fabric precisely because nothing constrained it. Whether a constrained rerun changes the
*ordering* is untested.

Second, smaller: the LUT column is extracted from seed 1, not the median. It happens not to
matter — LUT count is bit-identical across all five seeds for every design — so it equals the
median by invariance. Worth stating precisely if the table is cited.

## Net

Provenance: **fully sourced, 10/10 and 6/6 reproduced independently.** My withdrawal was wrong
twice over — the phiscale logs existed, and the tnet logs existed too. The audit's only genuine
finding is the unconstrained-timing caveat, which narrows how the absolute MHz figures may be
described without touching any comparative claim.
