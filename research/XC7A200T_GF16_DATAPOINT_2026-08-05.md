# Prepared correction material — XC7A200T GF16 data point + board reconciliation

> For arXiv:2606.05017 (GoldenFloat), open question **§1.2 "which board did 323 MHz
> come from"**. **Prepared material, NOT a submission** — replacing an arXiv entry
> needs the author's credentials (ARXIV_V2_CORRECTION_PACKAGE §11). Every number
> below was produced 2026-08-05 by an actual local openXC7 run + on-silicon
> conformance, not from memory or a state file.

## 1. The board discrepancy (three different parts cited for "the" GF16 result)

| Source | Part | Package |
|---|---|---|
| arXiv:2606.05017 abstract | XC7A**35T** | Arty |
| `t27/docs/arxiv-submission/trinity-gf16.tex` body + table | XC7A**100T** | QMTECH FGG676 |
| **This work (2026-08-05)** | XC7A**200T** | ALINX AX7203 FBG484 |

The paper's own abstract and body disagree; this adds a third, independently
reproduced part. Recommendation: state the exact part+package once, and separate
the two *kinds* of frequency below.

## 2. The unstated distinction: bare-core combinational Fmax vs routed-wrapper Fmax

The paper's headline **323 MHz** is the **combinational** max-frequency of the bare
`gf16` core, measured against a ripple-counter probe clock (`trinity-gf16.tex`:
*"Max frequency for clock 'chain[19]': 323.31 MHz"*). That is a valid but specific
measurement — a purely combinational multiply has no register-to-register path, so
the "frequency" is `1 / (combinational delay)` exposed via a probe counter.

A **routed, clocked conformance design** on real silicon is a different number.

## 3. This work — reproduced openXC7 flow, part xc7a200tfbg484-2

- **Tooling:** `regymm/openxc7` Docker — `yosys synth_xilinx -flatten -abc9 -nocarry
  -nodsp -arch xc7 -top gf16_mul_ax7203`, then `nextpnr-xilinx` (placer sa, router1),
  `fasm2frames` + `xc7frames2bit`. Top = `gf16_mul_ax7203` (the UART conformance
  wrapper: `gf_mul_param #(EXP=6,MANT=9)` + STARTUPE2/CFGMCLK + UART FSM).
- **Resources (yosys estimate):** **541 LCs** for the wrapped top.
- **Timing (nextpnr):** **27.55 MHz** for clock `mclk` (CFGMCLK path), reported as
  FAIL against a 50 MHz target. openXC7/nextpnr static timing on xc7 is known to be
  conservative; the design nonetheless functions (see §4) because the datapath is
  **UART-paced at 160 kbaud**, far below any of these estimates.
- **Honest reading:** the wrapped, routed conformance datapath is ~27–28 MHz by
  static estimate — an order of magnitude below the bare-core 323 MHz combinational
  figure. Both are true; they measure different things. A paper table should not
  present the combinational number as the design's clock rate.

## 4. On-silicon conformance — bit-exact vs the golden oracle

Bitstream flashed to AX7203 SRAM (`sudo openocd -c "pld load 0 …"`, 778 s), read over
UART (`/dev/cu.usbserial-1130`, 160000 baud, frame `AA 55 [a16][b16][00] → A5 …`),
compared to `conformance/gf_ref.py`:

**GF16 mul — 5/5 exact:**
| a | b | HW | golden | meaning |
|---|---|---|---|---|
| 0x3F00 | 0x4000 | 0x4100 | 0x4100 | 1.5 × 2.0 = 3.0 |
| 0x4000 | 0x4000 | 0x4200 | 0x4200 | 2.0 × 2.0 = 4.0 |
| 0x3F00 | 0x3F00 | 0x4040 | 0x4040 | 1.5 × 1.5 = 2.25 |
| 0x4100 | 0x4000 | 0x4300 | 0x4300 | 3.0 × 2.0 = 6.0 |
| 0x3C00 | 0x4200 | 0x4000 | 0x4000 | 1.0 × 3.0 = 3.0 |

**GF8 add — 5/5 exact** (earlier `gf8_clean_ax7203.bit` on the same board): (0x10,0x90)=0,
(1,1)=2, (0x20,0x20)=48, (0x30,0x10)=52, (0x3c,0x40)=78 — all match golden.

Special values also confirmed on silicon: `gf16_mul(inf,0)=0x7E01` (NaN),
`gf16_mul(inf,2)=0x7E00` (inf) — exp field all-ones as specified.

## 5. Suggested paper edits (for the author to apply with arXiv credentials)

1. **§1.2 / FPGA table:** name the exact part+package; add a column or note
   separating **bare-core combinational Fmax** (323 MHz, probe clock) from
   **routed clocked-design Fmax** (report the real routed number).
2. Add this **XC7A200T-FBG484 openXC7 row**: 541 LCs, routed ~27.55 MHz (mclk),
   functionally verified on silicon, GF16 5/5 + GF8 5/5 vs golden.
3. State the conformance was read **on real silicon over UART**, with the golden
   oracle named — strengthens the "bit-exact" claim beyond simulation.

## 6b. Prior art already in the repos — align, do NOT duplicate

A branch survey (2026-08-05) shows this data point slots into existing, unlanded work:
- **`trinity-papers-ru/paper1-goldenfloat/main_ru.tex` already has `\section{sec:hw-ax7203}`**
  targeting **XC7A200T-2FBG484I ALINX AX7203**, and already notes *"part of the
  multiplier does not route on this Artix-7 (routing failure)"* — which **corroborates
  the 27.55 MHz / routing-margin finding here**. This work supplies the missing piece:
  **on-silicon UART conformance readback vs the golden oracle** (GF16 5/5, GF8 5/5).
- **`trinity-fpga/docs/arxiv_v2_table.tex`** already has the **bare per-op** XC7A200T
  yosys+abc9 LUT numbers (GF16 mul 132 LUT, gf_mul 294 LUT/1 DSP). The **541 LCs**
  here is the **wrapped** `gf16_mul_ax7203` top (core + UART FSM + STARTUPE2) — a
  different, complementary figure. Label them distinctly.
- **Merge prerequisite:** the standardisation on ALINX AX7203 + removal of the
  "fabricated TTSKY26b dies" wording is **PR #17 = commit `925bdf6d`** in
  `trinity-papers-ru`, which **is NOT merged to `main`**. The board reconciliation
  and abstract fix are only mutually consistent once that lands.
- The RTL/codegen fixes the paper's SSOT should reflect live on **unmerged t27
  branches**: `fix/gen-verilog-array-lowering` (`701d79b3`), `fix/r7-rust-wrapping-ops`
  (`377d9a27`), `fix/gen-verilog-typealias`, `fix/gf16-conformance-vectors` (corrects
  5 stale GF16 vectors), `fix/gf-fpga-audit` (GF16 rounding). None on master.

## 6. Limits (state, don't hide)

- SRAM flash is **volatile** (JTAG `pld load`), not SPI-boot.
- nextpnr openXC7 timing is a static estimate and likely pessimistic; the 27.55 MHz
  is not a measured toggle rate — it is the tool's worst-path estimate.
- Single board; the AL321 JTAG cable is one, so a multi-board timing sweep was not run.
