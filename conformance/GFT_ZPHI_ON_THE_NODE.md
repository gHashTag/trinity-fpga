# GFTernary weights on Z[phi] activations, on the existing node cell

The TNF paper's weight format is GFTernary, t*phi with t in {-1, 0, +1}, and
its claim is that a layer's linear path is exact in Z[phi] without a
multiplier: applying a weight to a + b*phi is the Fibonacci step
t*(b, a + b). The TRI-NET node on the AX7203 computes signed 32-trit
ternary dots. That is enough to run the claim on silicon, with no new RTL:

    sum_i t_i*phi*(a_i + b_i*phi) = W.b + (W.a + W.b)*phi

W.a and W.b are ternary-by-integer dots. With int8-range a_i and b_i, each is
6 balanced-ternary digit planes, 12 node jobs per 32-wide chunk. Harness:
`gft_zphi_ax7203.py`. It reuses `tern_tc_layer_ax7203.run()` unchanged for
every per-answer check.

**Oracle.** Plain Z[phi] multiplication (a, b)(c, d) = (ac + bd, ad + bc + bd)
of (0, t_i) and (a_i, b_i), summed. It uses neither the Fibonacci shortcut nor
the digit split. Each output is two rows: R (rational part) and A (phi part
minus rational part). Both rows are bit-exact exactly when the output
assembled from the board's answers equals the oracle in Z[phi].

**Not shown.** No TNF accumulator runs here: TNF rounding has no RTL. The digit
recombination and the phi assembly (one add per output) are host arithmetic.
The node's part is the ternary dots. That is the paper's multiplier-free part,
and the only part this silicon can speak to without a reflash.

## Self-test (no board), 2026-09-27

`python3 gft_zphi_ax7203.py --self-test`: PASS. It checks:

- Z[phi] multiply against a 60-digit decimal phi on 2,000 random pairs;
- the Fibonacci step for every t and a, b in [-20, 20];
- an honest reference cell: 24/24 rows, 2,664/2,664 receipts;
- negative controls, each of which must fail:
  - an oracle with phi^2 = 1 (12/24 rows: the phi rows fail);
  - weights taken as t instead of t*phi (0/24);
  - the host dropping digit plane 3^0 (0/24);
  - a validly signed wrong answer (rejected as 'lie');
  - a cell signing with another key (0 receipts).

## RTL co-simulation (no board), 2026-09-27

The real `fpga/portable/trinet_node_core.v` and
`fpga/openxc7-synth/trinet_siphash24.v`, unchanged, under Icarus Verilog
through `formal/tern_tc_layer_rtl_tb.v` (BAUD_DIV=8). Setup: synthetic weights
(seed 0x7C02), layer 0 wk, public test key set over the wire.

| jobs | rows bit-exact | receipts verified |
|---|---|---|
| 7,680 | 128/128 | 7680/7680 |

Stream hashes (sha256): requests `2a976cd5...91e6f6`, responses
`fb4e7c80...c1d428`.

    python3 conformance/gft_zphi_ax7203.py --synthetic --mats wk --layers 0 \
        --setkey --keys test --emit-requests req.hex
    iverilog -g2012 -o tb formal/tern_tc_layer_rtl_tb.v \
        fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v
    vvp -n tb +req=req.hex +resp=resp.hex        # ~70 s
    python3 conformance/gft_zphi_ax7203.py --synthetic --mats wk --layers 0 \
        --setkey --keys test --responses resp.hex

## Board run: pre-registered before it ran

- **Command:**

      python3 gft_zphi_ax7203.py --setkey --port /dev/cu.usbserial-1130 \
          --baud 1144744 --keys ../trinet-keys.txt \
          --model ~/igla-coder-gpu/c_infer/model.bin

- **Input:** trained `model.bin` (sha256 prefix `3102abdf35057924`), layer 0,
  all 7 ternary matrices, 2,816 outputs, one Z[phi] vector (seed 0x2F1),
  window 24 (the default).
- **Expected:** 403,200 jobs, `receipts verified (tag) : 403200/403200`,
  `rows bit-exact : 5632/5632`, about 86 s.
- **Rules:**
  - The run happens once, and its result is recorded whatever it is.
  - One repeat is allowed, and only if it fails before the first job (port busy,
    node silent). If there is a repeat, both runs are recorded.
  - A UART slip here counts against window 24. It does not count against the
    Z[phi] claim, and it is recorded as a fail.
- **Log:** `board_runs/gft_zphi_l0.log`.

## Board run: result, 2026-09-27 03:32 UTC: PASS

Run once, as pre-registered. Setup: port `/dev/cu.usbserial-1130` behind the
same USB hub, 1,144,744 baud, no power cycle since the window-64 control.
Harness blob `00b4f04c`, importing `tern_tc_layer_ax7203.py` blob `01f85f04`
(that change touched comments only; the self-test was re-run on it and passed).
`--setkey` got 0x03 (key already held since 02:10). Every tag then verified
under the key file, so the key is ours.

| | expected | board |
|---|---|---|
| jobs | 403,200 | 403,200 of 403,200 sent, window 24 |
| receipts | 403200/403200 | `receipts verified (tag) : 403200/403200 under node 0x5452494e` |
| rows | 5632/5632 | `rows bit-exact : 5632/5632`, 14 of 14 matrix-parts `[ok]` |
| rejected | none | none |
| time | ~86 s | 85.35 s (4,724 answers/s); longest host pause 13.4 ms |

**What this shows.** For the 7 ternary matrices of layer 0 of the trained model
(2,816 outputs), GFTernary weights t*phi applied to one Z[phi] vector give,
from answers computed and signed by the node, exactly the Z[phi] values of the
plain-multiplication oracle. The weight step needed no multiplier. The node
did ternary dots only, and the host did one add per output.

**What it does not show.**

- It is not the TNF accumulator: nothing was rounded.
- It is not a speed result: same link ceiling as tern_tc, see
  `TERN_TC_WEAK_POINTS.md` point 2.
- The receipts carry the limits in weak point 4 (symmetric key, not bound to
  the FPGA).
- The activations are synthetic.

Log: `board_runs/gft_zphi_l0.log` (1,827 bytes, 0 key hits). The board was not
reflashed and openocd was not started.
