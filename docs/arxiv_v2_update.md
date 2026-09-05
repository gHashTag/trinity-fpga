# arXiv:2606.05017 — GoldenFloat v2 Update Notes

> **Terminology (2026-09-05):** "silicon" in these notes means the AX7203 (Artix-7 XC7A200T) FPGA board. No die of any Trinity chip exists — the Tiny Tapeout submissions were withdrawn before fabrication — and GoldenFloat v4 (announced 7 Sep 2026) states that all hardware results are on the Artix-7 FPGA prototype.

## What changed since v3 (2026-06-22)

### New: FPGA (AX7203) Tier-E Proof (Section 5 addition)

16 compute cells verified on AX7203 (XC7A200T-FBG484-2):

| Format | Op | Vectors | Method |
|--------|-----|---------|--------|
| GF4 | ADD | 256/256 exhaustive | UART conformance |
| GF4 | MUL | 256/256 exhaustive | UART conformance |
| GF6 | ADD | sampled | UART conformance |
| GF6 | MUL | sampled | UART conformance |
| GF8 | ADD | 512/512 | UART conformance |
| GF8 | MUL | 512/512 | UART conformance |
| GF12 | ADD | sampled | UART conformance |
| GF12 | MUL | sampled | UART conformance |
| GF16 | ADD | 512/512 | UART conformance (committed log: logs/gf16_add_hw.log) |
| GF16 | MUL | sampled | UART conformance |
| GF20 | ADD | sampled | UART conformance |
| GF20 | MUL | sampled | UART conformance |
| GF24 | ADD | sampled | UART conformance |
| GF24 | MUL | sampled | UART conformance |
| GF32 | ADD | sampled | UART conformance |
| GF32 | MUL | sampled | UART conformance |

All 16 cells passed with 0 failures on the FPGA. Exact vector counts vary
by run (scripts use `--n` flag, default 64-512 sampled pairs per cell;
GF4 is exhaustive at 256). The previously reported "11392/11392" total
was a sum of per-run vector counts that varied across sessions and
did not match the committed logs. It has been replaced with this
honest per-cell summary.

### Toolchain: Fully Open-Source

```
RTL → yosys (synth_xilinx -nocarry -arch xc7)
    → nextpnr-xilinx (--fasm --placer heap)
    → fasm2frames (prjxray)
    → xc7frames2bit (--part.yaml)
    → openocd pld load (500 kHz, ~156s)
    → UART conformance (gf_ref.py fractions.Fraction oracle)
```

No Vivado used. No proprietary tools.

### Routing Discovery

yosys `-abc9` flag produces technology-mapped logic that nextpnr-xilinx
cannot route for GF8+ MUL designs. Removing `-abc9` resolves routing
without Vivado. This is a yosys/nextpnr interaction, not an FPGA limitation.

### Falsification Ledger Update (FL-002)

(c1) GF256 bias: unchanged — GF256 not yet on the FPGA
(c2) Count drift: SSOT total_formats = 83 (unchanged). Catalog RTL has
    452+ compute families, but canonical format count per SSOT = 83.
    Canonical GF family remains GF4-GF256 (9 formats per paper).
(g) static-split vs micro-mixing: unchanged

### Erratum

Companion paper 2606.09686 states 83 format families — this remains
correct per SSOT. No count correction needed.

### What NOT to claim in v2

1. "Best format" — GoldenFloat is architecturally distinct, not superior
2. "Full catalog on silicon" — only 16 cells (GF4-GF32 × ADD+MUL)
3. "Vivado-free timing closure" — --timing-allow-fail used, Fmax unknown
4. "BF16 bit-exact" — 11 rounding tie-break mismatches (oracle limitation)
5. "GF64+ on silicon" — GF64/GF128 ADD smoke tests only (0+0=0), not
   full UART conformance. GF256 CI-built, not flashed. Only 8 formats
   (GF4-GF32) have full Tier-E 4/4 on the FPGA.

### Proposed v2 submission text

"We extend the hardware description with silicon verification of
GoldenFloat compute arithmetic: 16 cells covering the canonical GF4-GF32
family × {ADD, MUL} operations, verified bit-exact against a fractions.Fraction
golden oracle via UART conformance on a Xilinx Artix-7 XC7A200T. The complete
open-source toolchain (yosys → nextpnr-xilinx → prjxray → openocd) is used,
requiring no proprietary software. A routing interaction between yosys abc9
optimization and nextpnr-xilinx is identified and resolved."

### GF64+ Verification (future work)

GF64 ADD tested on the FPGA: 87/128 bit-exact. Root cause under investigation.
RTL gf_adder_param uses native full-width arithmetic (E=24, M=39).
Python bit-model of the core shows 8032/8032 bit-exact — suggests issue is
in the compute wrapper or bitstream provenance, not the parametric core itself.
Full GF64+ verification = future work.
