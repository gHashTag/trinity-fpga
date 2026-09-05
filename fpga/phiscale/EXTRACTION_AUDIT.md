# What each extraction actually read, checked one by one

Every xc7 cell count in this directory was found to be exactly 3.0× too large:
`synth_xilinx` prints its own statistics before the script's explicit `stat`, and
the extraction summed LUT lines across every block in the log. That is corrected
(`ON_A_PART_WITH_DSP.md`, `TERN_LAYER.md`, `conformance/device_fit.py`).

One bad extraction is a reason to check every other one. These are the results.

## The iCE40 frequencies: sound

`nextpnr-ice40` prints **two** frequency figures per run — a post-placement
estimate and a post-route final:

```
line  67: Max frequency ... 209.60 MHz     (before "Routing complete", line 105)
line 312: Max frequency ... 204.08 MHz     (after routing)
```

The extraction used `tail -1`, which takes the **post-route** figure. Every
frequency published here is therefore the final one, not the estimate. **No
correction needed.**

The utilisation figures come from a single table read the same way; `1746` for
the memory-backed φ layer reproduces exactly.

## The iCE40 cell counts: sound

`ICESTORM_LC` appears on ten lines of a nextpnr log, but nine are progress
messages and the tenth is the utilisation table. `tail -1` takes the table.
Verified by re-running: same number.

## What the numbers are, stated once

- **yosys** — cell counts **after synthesis**. `synth_xilinx` takes a **family**,
  not a device; it has no device option, so any header naming a part was wrong.
- **nextpnr-ice40** — real place-and-route and a static timing model. A model.
- **icepack** — a real 135,100-byte bitstream. Nothing is attached to load it.
- **iverilog** — simulation.

**Nothing in this directory has touched silicon.** No board appears in the USB
tree; `nextpnr-xilinx` and `prjxray` are not installed, so no bitstream for the
target family can be built at all.

## A figure outside this repository, checked

`Trinity S3AI — Ternary Network Floats`, §8.1, reports a width defect: a first
realisation declared 32-bit buses where the format needs 20 and 7, and cost
"1,179 LUTs, or three DSP48 blocks, against 219 LUTs and none once the buses
match".

The wide module is `build/gft_mul8/gft_mul.v` (`OFFSET_MAX = 80`, every port
`[31:0]`, `prod = (MANT_ONE + a_mant) * (MANT_ONE + b_mant)`). Re-measured on
yosys 0.65, reading the last stat block only:

| configuration | LUT | DSP48 |
|---|---:|---:|
| DSP forbidden | **1179** | 0 |
| DSP allowed | 119 | **3** |

**Both figures in the paper reproduce exactly.** The paper's author read the last
stat block; the broken extraction was this repository's, not the paper's. For
comparison, the broken method gives 3537 LUT and 9 DSP48 on the same run.

The narrow variant the paper compares against — "219 LUTs and none" — could not
be located in the tree in that form, so **that half is unverified**. It is not
disputed; there is simply nothing here to run.
