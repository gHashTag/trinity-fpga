# tern_tc on the node cell: what is verified, and by what

2026-09-26. Companion to `tern_tc_layer_ax7203.py` and `formal/tern_tc_layer_rtl_tb.v`.

## Correction to commit 1f131fd

The first `tern_tc_layer_ax7203.py` printed `receipts authenticated : 284160/284160
under node0's key`. It never compared a tag. `pyflakes` on that file:

    'trinet_mac32_conformance_ax7203.siphash24' imported but unused
    local variable 'pre' is assigned to but never used
    undefined name 'c_dummy'

It counted `status == 0x01` as authentication, ignored the nonce echo, and
compared only per-row sums. Negative control: fed a software cell that signs with
a key the host does not hold, it printed `receipts authenticated 160/160` and
PASS.

| claim from the 2026-09-27 board run | status |
|---|---|
| 28,416 / 28,416 row dots bit-exact (wq/wo/gate/up, 6 layers) | **stands**: the y values were compared per row against the oracle |
| 320 / 320 rows, 3,200 receipts, random 320x320 (`trinet_matvec_demo.py`) | **stands**: that harness does compare tags and nonces |
| 284,160 / 284,160 receipts authenticated under node0's key | **withdrawn** until the board reruns the fixed harness |

## What the fixed harness checks

Per response: status 0x01, nonce issued by this run and answered once, node id
equal to the first answer's, SipHash-2-4 tag recomputed under the key, y equal to
that chunk's dot product. Per row: every chunk accepted, and the chunk sum equal
to the row dot computed from the model's int8 weights directly (not from the
packed wire bytes). `--self-test` shows each check failing on a cell built to
break it: wrong key, a validly signed wrong answer, a flipped tag bit, an
unissued nonce, another node id, a dropped response, an unkeyed node.

## Booked as new hardware, needs none

- **w_down** (864-wide input): 864 = 27 x 32, so 27 jobs per row on the same cell.
- **wk, wv** (320-wide input): were skipped, not blocked.
- **int8 activations** (Stage B.3): q = sum 3^k d_k with d_k in {-1,0,+1} over six
  digits covers [-364, 364], so w.q = sum 3^k (w.d_k): six ternary jobs per
  chunk, recombined on the host. `--act int8`.

All 42 ternary matrices (6,451,200 weights) therefore run on the existing
bitstream: 403,200 jobs for two ternary x-vectors, about 90 s at the 4,560 jobs/s
measured on 2026-09-27 (derived).

## RTL co-simulation (no board)

`fpga/portable/trinet_node_core.v` and `fpga/openxc7-synth/trinet_siphash24.v`,
unchanged, under Icarus Verilog 12.0, UART at bit level (BAUD_DIV=8), node
unkeyed at reset and keyed over the wire by op 0x02, exactly as on the board.
Weights: random ternary in tern_tc's exact shapes (`--synthetic`, seed 0x7C02,
59.7% nonzero), because the trained `model.bin` was not in this environment.

| run | jobs | rows bit-exact | receipts verified |
|---|---|---|---|
| layer 0, all 7 matrices (`--all --layers 0`) | 67,200 | 5,632 / 5,632 | 67,200 / 67,200 |
| layer 5 w_down, int8 activations (`--mats down --layers 5 --act int8 --n_x 1`) | 51,840 | 320 / 320 | 51,840 / 51,840 |
| layer 0 wk, no setkey frame (control) | 640 | 0 / 64 | 0 / 640, all status 0x04 |
| layer 0 wk, verified under a different key (control) | 1,280 | 0 / 128 | 0 / 1,280 |

Stream hashes (sha256): layer 0 requests `2379d8f2...5619f`, responses
`f4ca4909...5890e`; w_down int8 requests `bcf0b51f...74b95`, responses
`e6443bf1...99add`.

Reproduce:

    python3 conformance/tern_tc_layer_ax7203.py --synthetic --all --layers 0 \
        --setkey --keys test --emit-requests req.hex
    iverilog -g2012 -o tb formal/tern_tc_layer_rtl_tb.v \
        fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v
    vvp -n tb +req=req.hex +resp=resp.hex          # ~20 min for 67,200 jobs
    python3 conformance/tern_tc_layer_ax7203.py --synthetic --all --layers 0 \
        --setkey --keys test --responses resp.hex

## Board rerun (the owner's machine)

    cd ~/trinity-fpga/conformance
    python3 tern_tc_layer_ax7203.py --self-test
    python3 tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-130 \
        --baud 1144744 --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

`--setkey` installs node0's key and checks the ack tag. After a power cycle it
is required; if the board already holds a key the ack is 0x03, and the receipts
then show whether it is the right one. Needs `pyserial`.

## Not claimed

A forward pass (embeddings, norms, attention, softmax and head do not run on the
board); any token rate or power figure; public verifiability (SipHash is a
shared-key MAC: it authenticates the node to the key holder and does not stop an
operator forging their own receipts).
