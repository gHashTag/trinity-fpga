# The paper's number formats on the AX7203: measured, recorded, missing (2026-09-27)

The owner asked how the formats in the GoldenFloat hardware paper
(`research/goldenfloat-hw-conformance/GOLDENFLOAT_HW_CONFORMANCE_v0.2.md`)
behave on this board. Short answer:

- **Today the board can run only one kind of arithmetic:** the TRI-NET node's
  ternary dot product. Two formats were measured through it today, ternary and
  Z[φ] (GFTernary × Z[φ]), plus int8 activations. All three pass with signed
  receipts.
- **None of the paper's 27 Tier-E cells** (13 decode, 7 GF ADD, 7 GF MUL) can
  be re-measured without reflashing. Their board results are recorded only as
  quotes in issue comments on gHashTag/trinity-fpga#199. No raw UART log for
  any of them is in a repository on this Mac, and only one of their bitstreams
  is: GF8 ADD.
- **TNF and BNF have never been on a board.** Their LUT and Fmax figures are
  post-route numbers.

Tags: **measured** = a board log in `conformance/board_runs/`, run today.
**recorded** = quoted in an issue comment or a repo file, not re-run.
**derived** = arithmetic from the numbers cited. Comment ids below refer to
`https://github.com/gHashTag/trinity-fpga/issues/199#issuecomment-<id>`.

## 1. Measured today on this board (measured)

All four runs used node 0x5452494e over the CP2102N at 1,142,857 baud on the
wire, with window 24 (8 for the int8 run).

| activations × weights | run | receipts | rows | log |
|---|---|---|---|---|
| ternary × ternary, all 42 matrices | 02:43 UTC | `receipts verified (tag) : 403200/403200` | 33792/33792 | `tern_tc_all_w24.log` |
| same, window 26 | 03:37 UTC | `receipts verified (tag) : 403200/403200` | 33792/33792 | `tern_tc_all_w26.log` |
| Z[φ] (int8 components) × ternary, layer 0 | 03:32 UTC | `receipts verified (tag) : 403200/403200` | 5632/5632 | `gft_zphi_l0.log` |
| int8 × ternary, `down` matrix | 02:29 UTC | `receipts verified (tag) : 51840/51840` | 320/320 | `tern_tc_down_int8_w8.log` |

The failures on the same node were link failures: W30 (149986/403200), W64
(6679/403200), and the int8 run at the then-default window 64 (9886/51840).
They are not arithmetic failures (`TERN_TC_WEAK_POINTS.md`). The node
computes exact integer dot products. A Z[φ] value a + bφ is two such products
combined on the host, so the format only changes what the host sends.

## 2. The paper's 27 Tier-E cells (recorded)

Paper v0.2, section 4, line 59: 13 decode, 7 ADD and 7 MUL, all on the AX7203
(IDCODE 0x13636093), June 28 to July 2.

| column | cells | recorded result | evidence on disk |
|---|---|---|---|
| decode-HW 13 | bf16, int8, nf4, fp8_e4m3, posit8, fp8_e5m2, fp4_e2m1, int4, fp6_e2m3, fp6_e3m2, lns8, tf32, binary16 | N/N per cell (binary16 65536/65536, exhaustive; bf16 and tf32 only 8/8) | none |
| compute ADD 7 | GF4, 6, 8, 12, 16, 20, 24 | 256 to 512 vectors per cell, fails=0 | GF8 bitstream only |
| compute MUL 7 | GF4, 6, 8, 12, 16, 20, 24 | 256 to 480 vectors per cell, fails=0 | none |

The one bitstream is `artifacts/bitstreams/gf8_clean_ax7203.bit` from
99431418. Its sha256 `47d8a076…e369` matches comment 4826403273 (checked).

The paper claims "a full reproducible evidence chain (CI build → bitstream
SHA-256 → JTAG flash → UART verify)" for each cell. On this Mac, the last link
of that chain exists only as a line quoted inside a comment.

## 3. Other formats with a board record (recorded)

- **GF32 ADD and MUL:** 240/240 (comments of 2026-07-13). This is the 16-cell
  GF4–GF32 set in retraction 4959097382.
- **GF64 ADD:** smoke `0+0` passed, then **FAIL, 359/512 (70.1 %)**
  (4965993162, checked). **GF128:** smoke only.
- **Not bit-exact, or too thin to count:**
  - BF16 ADD 245/256, with 11 rounding ties (4957037580);
  - lns16 decode 472/576 (4881130168);
  - a 5-decoder mux top 32/40 (4911803703);
  - the GF16+ quire, two test points (4983936091).
- **Several dozen further decode formats,** from int16 up to binary128,
  posit64 and takum64: N/N per cell, all posted from 2026-07-01 to 07-08.
  Several vector counts changed between runs of the same cell, for example
  GF20 decode 2048 and then 242.
- **Latest format load on this board with a quoted UART line:** 2026-08-01.
  GF8 ADD gave 4096/4096 (5151975389), and GFTernary MUL gave 16/16
  (5151891547), scored against an FP32 proxy. t27 records GF-T designs
  "on a live AX7203" on 08-07/08, but gHashTag/t27#4789 says those bitstreams
  and logs are in no repo.

## 4. Never on this board

- **TNF and BNF.** `fpga/tnet/MATRIX.md` gives BNF16 519 LUT at 71.05 MHz and
  TNF16 514 LUT at 74.37 MHz (lines 115–116). Its heading says "подтверждённая
  кремнием" (confirmed on silicon), but line 124 says the numbers were measured
  after synthesis. These are post-route figures, not a board load. The same
  file's first table gives TNF16 as 495 LUT at 71.90 MHz (line 24). That fits
  the paper staying closed until TNF beats MXFP4 on the block axis.
- **GF48 to GF1024:** simulation only, by their own
  `conformance/README_gf*_bitexact.md`.
- **The `gft_*` operator waves W973–W990 (2026-08-21/22) were another board.**
  They were read over JTAG from part `xc7a200tfbg676-1`
  (`research/arxiv_tnf/measurements/bitstream_w973.json`, checked). This
  board is FBG484. `~/t27/specs/boards/wukong_v1.t27` names that bench a QMTech
  Wukong.

## 5. Records that disagree

1. **The Tier-E total has five values:**
   - 27/83 in the paper;
   - 71/83, then 21/83 compute, in `fpga/CATALOG_MATRIX_83.md` lines 31 and
     87 (checked);
   - "71/83 was WRONG" in the EPIC body;
   - decode-HW 4/83 and compute-HW 2/83 in
     `~/t27/docs/metrics/NUMERIC_FORMATS_83_METRICS.md`.
2. **The 16-cell total "11392/11392"** was called "unaffected, verified
   correct" in 4959097382 on 07-13. It was then retracted as fabricated in
   4968388589 on 07-14 (checked). The per-cell comments stand; the total
   does not.
3. **SUB:** the paper calls SUB 7/7 "prepared", while `CATALOG_MATRIX_83.md`
   line 87 says ADD, MUL and SUB were "measured on AX7203 (2026-07-01)".
4. **Host frame regression:** from 6f3001b1 (07-17) to 64c3459f (08-01) the
   GF compute hosts did not send their operands. Board runs in that window
   measured `gf_add(0,0)`.

## 6. Re-measuring the paper on this board (derived; each flash needs the owner's yes)

- **Cost.** One cell is one bitstream. A JTAG load at 100 kHz takes about
  778 s (`NODE_TOOLCHAIN_RESTORE.md`), so 27 cells is about 5.8 h of loads.
  Each load replaces the node, which then has to be reloaded and re-keyed. One
  bitstream carrying several format cores behind a selector byte would take a
  single load. The record has one such top, and it scored 32/40.
- **Link rate.** The GF8 design (`fpga/vivado/gf8_clean_ax7203.v`) clocks its
  UART from CFGMCLK with divider 434. On this board CFGMCLK is bounded to
  65.6–68.7 MHz (`TERN_TC_WEAK_POINTS.md`, point 6). That puts the design's
  rate at 151,152–158,295 baud. The host default is 160,000, which is 1.1 %
  to 5.9 % fast. A re-run could therefore fail on the link, not on the
  arithmetic.
  - Pre-register 154,839 baud, which is exact on the CP2102N (N=155, per
    `tri fpga-wire`) and sits at the middle of the bound.
  - If that fails, sweep the rate before reading anything into the result.
- **Ready without the board:** `conformance/gf8_add_conformance_ax7203.py
  --self-test` passes today: 65536 pairs, 0 inconsistencies.

## 7. Pre-registered: GF8 ADD at 154,839 baud (written before the run)

The owner said yes to this flash and run on 2026-09-27: «да, прошей GF8 ADD и
запусти на 154839».

- **Bitstream:** `artifacts/bitstreams/gf8_clean_ax7203.bit`, sha256
  `47d8a076…e369`. The load is logged in `board_runs/gf8_add_flash.log`.
- **Command,** from `conformance/`: `tri fpga-run gf8_add_exhaustive_154839
  --limit 1800 -- python3 gf8_add_conformance_ax7203.py --port
  /dev/cu.usbserial-1130 --baud 154839 --exhaustive`.
- **Vectors:** all 256 × 256 = 65,536 pairs, checked against `gf_ref.py`
  (GF8 = 1S+3E+4M, bias 3, HAS_INF 0). The run recorded on 2026-08-01 used
  4,096 pairs. Exhaustive covers every input.
- **PASS** means the log has the line `HW RESULT: 65536/65536 bit-exact
  (fails=0)` and exit 0. Anything else is a FAIL and is recorded as it stands.
  If the run is stopped at the 1,800 s limit, it is recorded as incomplete.
- **Telling link from arithmetic.** The host sends no sequence number, so a
  lost byte shows up as `hw=None` in the mismatch lines. A `None` points at
  the link. A wrong value that is not `None` points at the arithmetic.
- **One attempt.** A second run is allowed only if the first fails before its
  first pair (port busy, no answer to pair 1). Both logs are then kept.
