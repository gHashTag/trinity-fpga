# The paper's number formats on the AX7203: measured, recorded, missing (2026-09-27)

The owner asked how the formats in the GoldenFloat hardware paper
(`research/goldenfloat-hw-conformance/GOLDENFLOAT_HW_CONFORMANCE_v0.2.md`)
behave on this board. Short answer:

- **Today the board can run only one kind of arithmetic:** the TRI-NET node's
  ternary dot product. Two formats were measured through it today, ternary and
  Z[φ] (GFTernary × Z[φ]), plus int8 activations. All three pass with signed
  receipts.
- **None of the paper's 27 Tier-E cells** (13 decode, 7 GF ADD, 7 GF MUL) can
  be re-measured without reflashing. One has been since, with the owner's yes:
  GF8 ADD, all 65,536 pairs, `HW RESULT: 65536/65536 bit-exact (fails=0)`
  (section 7). Their board results are recorded only as
  quotes in issue comments on gHashTag/trinity-fpga#199. No raw UART log for
  any of them is in a repository on this Mac, and only one of their bitstreams
  is: GF8 ADD.
- **TNF and BNF have never been on a board.** Their LUT and Fmax figures are
  post-route numbers. (Written before section 8. Since 06:08 UTC, one TNF16
  definition has a board run: section 8. BNF still has none, and neither do
  the other three TNF16 definitions.)

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
| compute ADD 7 | GF4, 6, 8, 12, 16, 20, 24 | 256 to 512 vectors per cell, fails=0 | GF8 bitstream only; GF8 re-measured exhaustively on 2026-09-27 (section 7) |
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

### Result, 04:44 UTC (measured)

**PASS.** `board_runs/gf8_add_exhaustive_154839.log` ends with `HW RESULT:
65536/65536 bit-exact (fails=0)` and `# exit=0`.

- **Load.** `board_runs/gf8_add_flash.log`: IDCODE 0x13636093, "loaded file
  ... in 778s", exit 0, 04:26:37 to 04:39:59 UTC.
- **Run.** One attempt, 04:40:22 to 04:44:37 UTC, 254 s, no `MISMATCH` line.
- **What this adds to the record.** Section 3 has 4,096 pairs from 2026-08-01
  as a quoted line. This run covers every input pair, and its raw log is in the
  repository.
- **Link.** 65,536 pairs at 7 bytes out and 4 bytes back went through with no
  `hw=None`. So 154,839 baud against divider 434 on CFGMCLK held for 720,896
  bytes. The run does not measure the clock: any rate the design tolerates
  would pass.
- **Rate.** At 3.9 ms per pair, the run was 5.5 times slower than the wire
  (0.71 ms per pair). Stop-and-wait over USB sets that pace, not the design.
- **Cost.** The GF8 load replaced the TRI-NET node. Until the node is reloaded
  and re-keyed, no receipt run (section 1) is possible on this board.

## 8. Pre-registered: TNF16 add and mul, every request (written before the run)

The owner, 2026-09-27: «так у на TNF лучший формат !!!», then «сделай его
сразу». TNF has never run on a board (section 4). This is one load and one run.
The owner types the sudo password for the load.

- **Spec, the one source:** `specs/trinet/tnf16_on_board_ax7203.t27`, sha256
  `703b35c0…6889`. It holds the format, the wire, the vector counts, the pass
  line and the guard bits. `conformance/tnf16_board_from_spec.mjs` compiles it
  with the t27 compiler (wasm `bb39b9a5…`), evaluates its 8 test blocks
  (54 asserts, 0 failures), and writes `fpga/tnet/tnf16_board_params.v` and
  `conformance/tnf16_board_params.py`. `--check` reports drift.
- **Format:** `conformance/tnf_ref.py` `TNFFormat(4, 11)`, ladder v2-spec, the
  format the pinned vectors were generated from. The word has 19 bits: sign,
  a 7-bit offset and 11 mantissa bits.
- **RTL:**
  - `fpga/tnet/tnf16_core.v` is a six-stage core, one request per clock. The
    adder keeps 3 guard bits plus a sticky bit.
  - `fpga/vivado/tnf16_board_ax7203.v` is the board top. Its UART is the
    TRI-NET node's, the same divider 60 on the same CFGMCLK.
- **Bitstream:**
  - Build command: `tri fpga-build --top tnf16_board_ax7203 --src
    fpga/tnet/tnf16_board_params.v fpga/tnet/tnf16_core.v
    fpga/vivado/tnf16_board_ax7203.v --no-node-params --nosrl`.
  - File sha256 `1820b114…370b`. Payload `6d4e0dd3…fd47`, the same in two
    builds. `artifacts/bitstreams/tnf16_board_ax7203.manifest.json` records
    the input hashes, the tools and the yosys script.
  - Post-route size is 838 LUTX. Fmax is 126.87 MHz against CFGMCLK's
    65.6–68.7 MHz.
  - Without `--nosrl`, yosys made 19 SRL16E, and router1 did not finish in two
    runs of more than 13 minutes. The builder now stops on SRL cells unless one
    of the two flags is given.
- **Command,** from `conformance/`: `tri fpga-run tnf16_board_ax7203 --limit
  1800 -- python3 tnf16_board_ax7203.py --port /dev/cu.usbserial-1130`. The
  host runs at 1,144,744 baud (1,142,857 on the wire) with window 24.
- **Vectors:** 1,035,886 requests, sha256 `2b1ea80b…2c38`. The host prints
  this and `tnf16_board_vectors.py --write` produces it.
  - 1,038 pinned rows from `tnf16_v2-spec_tnf-vectors-3.vec`.
  - 34,848 edge pairs: 132 codes crossed, for each op.
  - 500,000 uniform random requests.
  - 500,000 near random requests: add near cancellation; mul near underflow,
    unity and overflow.
  - Expected words come from `tnf_ref.py`.
- **PASS** means the log has the line `TNF16 RESULT: 1035886/1035886
  bit-exact (fails=0, lost=0)` and exit 0. Anything else is a FAIL and is
  recorded as it stands. If the run is stopped at the 1,800 s limit, it is
  recorded as incomplete.
- **Telling link from arithmetic.** Every response echoes the request's SEQ.
  - A wrong word counts as a fail, and the run goes on.
  - A short, unframed or out-of-sequence response stops the run with a
    `! LINK:` line. Every request not answered by then counts as lost.
  - So `fails` counts arithmetic and `lost` counts the link.
- **One attempt.** A second run is allowed only if the first fails before its
  first response (port busy, no answer). Both logs are then kept.
- **Before the board (simulated):**
  - **Core RTL (Icarus):** all 1,035,886 requests bit-exact. Latency is 6.
    Idle inputs carried junk, and 10/10 unknown opcodes were flagged.
  - **Python model** of the same datapath: 1,035,886/1,035,886.
  - **UART top from the pins:** 401 frames pass at 0, −43,000 and
    +1,875 ppm, the ends of the CFGMCLK band. The bench fails at −50,000.
  - **Host self-test:** every one of six injected faults is caught.
  - **Gate level:** the yosys netlist was simulated with yosys's
    `xilinx/cells_sim.v`. The yosys command matches the builder's (in the
    manifest). This is before place and route.
    - Core: 1,035,886/1,035,886 bit-exact, in 7 parallel chunks whose
      concatenation has the vector sha above. Latency is 6 and 7/7 bad
      opcodes were flagged.
    - Whole top from the UART pins: 401 frames, 2,005/2,005 response bytes,
      at 0 ppm.
  - **The checks can fail** (controls):
    - one expected word flipped gives `fails=1`;
    - the zero-significand bug fixed during this work gives FAIL;
    - 2 guard bits instead of 3 give 1,358 fails in both the model and the RTL.
- **Link margin (derived).** The slow end of the band is −43,333 ppm, and the
  bench passes at −43,000 and fails at −50,000. The margin at that end is
  thin, and a slow chip would show up as `lost`. The same receiver on this
  chip carried 403,200/403,200 node jobs at this rate.
- **Duration.** 1,035,886 requests of 10 bytes take 91 s on the wire. That is
  the floor for this run, not a prediction of how long it will take.
- **What a PASS says and does not say.**
  - It says this RTL computes the reference TNF16 add and mul bit-exact on
    this board for every listed vector.
  - It says nothing about TNF against other formats. The TNF paper stays
    closed until TNF beats MXFP4 on the block axis.
  - 838 LUTX includes a UART, a parser and six pipeline stages cut for a slow
    clock, so it is not a TNF cost figure.
- **Four TNF16 definitions (found while writing the spec):**
  - t27 `specs/numeric/tnf16.t27`: 4 trits as 2-bit codes, M=11, 20 bits.
  - `tnf_ref.py` v2-spec: 19 bits. This is the one on the board.
  - `tnf16_ref.py` v1-research: M=9.
  - `bnf_decode.v` `tnf16_decode`: M=8, 16 bits. This is the RTL behind the
    TNF16 row of `fpga/tnet/MATRIX.md` on main (514 LUT, 74.37 MHz), so that
    row does not describe this format.
  - The t27 file's header still says "9-bit precision" beside M = 11.
- **Cost.** The load replaces the GF8 design. The TRI-NET node stays off until
  it is reloaded and re-keyed.

### Result, 06:08 UTC (measured)

**PASS.** `board_runs/tnf16_board_ax7203.log` ends with `TNF16 RESULT:
1035886/1035886 bit-exact (fails=0, lost=0)`, which is the spec's `PASS_LINE`,
and `# exit=0`.

- **Load.** `board_runs/tnf16_flash.log`:
  - bit sha256 `1820b114…370b`, the pre-registered file;
  - IDCODE 0x13636093;
  - "loaded file ... in 778s";
  - exit 0, 05:52:47 to 06:06:06 UTC.
- **Run.** One attempt, 06:06:20 to 06:08:33 UTC.
  - The log names the spec sha `703b35c0…6889` and the vector sha
    `2b1ea80b…2c38`, both the pre-registered ones.
  - Every one of the 8 groups (pinned, edge, uniform, near; add and mul) is
    complete.
  - No `!` line.
- **Link.** 10,358,860 bytes went to the board and 5,179,430 came back, with
  window 24, the UART behind the hub, and nothing lost.
  - The requests took 102.4 s. The wire floor is 90.6 s, so the run went at
    88 % of the wire rate: 10,118 answers per second.
  - The host spent 30 s building the expected words before the first request.
- **What this adds.** Before this run, TNF was on a board nowhere (section 4).
  Now one format has a raw log: `tnf_ref.py` `TNFFormat(4, 11)`, v2-spec, add
  and mul, round-to-nearest-even with this spec's underflow rule. It matches
  the Python reference word for word on this board, in the RTL committed at
  `aa4511d6d`.
- **What it does not add.** It does not show TNF beats any other format, and
  838 LUTX is not a TNF cost (see above). It says nothing about the other three
  TNF16 definitions. It does not measure the clock: any CFGMCLK the UART
  tolerates would pass.
- **Cost.** The TRI-NET node is off the board. No receipt run (section 1) is
  possible until it is reloaded and re-keyed.
