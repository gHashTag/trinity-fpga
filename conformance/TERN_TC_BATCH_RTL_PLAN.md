# RTL plan for the batch ops: SETX and DOT6 in trinet_node_core.v

This is the plan a future RTL session executes, not a change to the RTL. The
design side of the batch protocol is complete — spec
(`specs/trinet/tern_tc_batch_ax7203.t27`, `tri fpga-specs` 17/17), generated
params, `BatchCell` reference model, batch runner with rehearsal pair (fires
6–8) — and this document is the bridge from that design to synthesis. Nothing
here edits Verilog, synthesises, builds a bitstream or touches the board.
Where this plan and the spec disagree, the spec wins.

Line numbers below refer to `fpga/portable/trinet_node_core.v` at commit
`e45e8269c` (351 lines).

## What stays untouched — and why that is the point

**The UART receiver (lines 74–110) and the frame parser (lines 112–158) do not
change at all.** Both new ops ride standard 24-byte request frames, which is
the property the spec bought at the price of a longer upload: the AA-55 hunt,
the 22-byte body capture, and the flush-resync proof survive verbatim, and
`conformance/frame_alignment_check.py` keeps its meaning. The parser already
captures everything the new ops need into `op_r`, `nonce_b`, `w_b`, `x_b` —
the ops are a re-reading of those registers:

| body byte(s) | captured as | SETX reads | DOT6 reads |
|---|---|---|---|
| 0 | `op_r` | 0x03 | 0x04 |
| 1–4 | `nonce_b[0..3]` | nonce | nonce |
| 5–12 | `w_b[0..7]` | `plane`=w_b[0], `chunk`=w_b[1], x8 low 6 B = w_b[2..7] | w8 (exactly today's w field) |
| 13–20 | `x_b[0..7]` | x8 high 2 B = x_b[0..1] | `chunk`=x_b[0], `mask`=x_b[1] |

The SETX x chunk therefore spans the register boundary:
`x8_bus = {x_b[1:0], w_b[7:2]}`. That split is correct per the parser's byte
map but is exactly the kind of off-by-one the co-simulation below exists to
catch — if the first byte difference lands in a SETX answer, look here first.

**The key store (lines 194–232) is untouched.** SETX and DOT6 sign under
`key_latched` exactly as MAC32 does; an unkeyed node returns real ys with
status 0x04 and the host refuses credit, same as today.

**The MAC32 and SETKEY paths are untouched, bit for bit.** Every receipt the
shipped harness can verify must verify identically after the edit. The
drift control is mechanical: `tern_tc_retransmit_rtl_cosim.py` (400 jobs,
MAC32 + setkey only) must still pass, unchanged, on the edited core.

## The three additions

### 1. The x RAM

Parameter `C_MAX` (default 27, the widest pass). Depth `PLANES × C_MAX` =
162 words of 64 bits (10,368 bits) — one SETX frame uploads one 8-byte chunk,
which is exactly one word, so the write side is a single-word store at
`addr = plane*C_MAX + chunk`. One write port (SETX path), one read port
(DOT6 path), inferred synchronous RAM in the plain-Verilog template — no
vendor macro.

Two consequences that must be handled honestly:

- **The header claim changes.** Line 17 advertises "no inferred RAM". After
  this edit that line is false unless rewritten: the claim becomes "no vendor
  macro; inferred RAM only, in the standard template every family's
  synthesiser recognises". The rewrite is part of the edit, not an optional
  tidy-up — a stale portability boast in the file's own header is worse than
  the RAM. `docs/TRI_NET_PORTABILITY.md` gets the same treatment.
- **Out-of-range addressing** (plane ≥ 6 or chunk ≥ C_MAX): the spec leaves
  it to the RTL and the model raises as a modeling assertion. The decision
  here: the RTL neither raises nor refuses — the address arithmetic is full
  width and the RAM's address port truncates, so out-of-range accesses alias.
  This is cryptographically sound for this protocol: the SETX tag MACs the
  *received* x8 (it never claims where they landed) and the DOT6 tag MACs
  *what the RAM returned* (checked against the host's belief), so a bogus
  address can only harm the host that issued it. The runner never issues
  one. Flagged for the owner's eyes anyway: it is a protocol-behaviour
  decision the spec delegated.

### 2. The six-dot datapath

The existing combinational dot network (lines 160–192) is reused unchanged;
its x operand gets a mux: `(op_r == OP_DOT6) ? ram_q : x_bus`. A small
per-op sequencer walks plane 0..5 over six clocks: each cycle reads the RAM
at `p*C_MAX + chunk`, dots it against the same `w_bus`, and latches
`ys_r[p] = mask[p] ? dot_result : 0` while shifting the 48 read bytes into
the preimage register. Alternative — six parallel copies of the dot network —
buys nothing: the 73-byte tag takes ~46 clocks anyway (below), and the wire
dominates both by five orders of magnitude. Take the mux.

### 3. The 73-byte tag and the 24-byte answer

A **second** `trinet_siphash24` instance with `MSG_BYTES = 73`; the MAC32
instance keeps `MSG_BYTES = 26` untouched. A shared variable-length engine
would put the proven MAC32 path at risk to save an area nobody will miss.
The module already documents its packing ("byte 0 in bits [7:0]",
little-endian), and the byte-exact authority for the layout is
`tern_tc_batch_model.dot6_preimage`:
`op(1) nonce(4) w8(8) chunk(1) mask(1) x48(48, RAM reads in plane order)
ys(6) node(4) = 73 B`. The x48 is the same bytes the dots consumed that
frame, so RAM drift cannot hide from the tag — the model's self-test pins
both directions.

Cycle cost: 73 B = 10 blocks × (absorb + 2 rounds + xor) + 4 finalisation
rounds ≈ 46 clocks, against MAC32's ~22 — both noise next to one 24-byte
answer at 1.14 Mbaud (~210 µs of line time).

The answer builder (lines 290–348) grows: `tx_buf[0:23]`, a `resp_len`
register (19 or 24, set per op at load time) so the completion compare
becomes `tx_idx == resp_len - 1`; `tx_idx` is already 5 bits and holds 24.
The DOT6 load order is `parse_dot6`'s: `A5, ys[0..5], status, nonce LE,
node LE, tag LE`. SETX reuses the existing 19-byte builder with
`y_reg <= chunk` (the receipt echoes the chunk index; the model's
`setx_preimage` MACs y = chunk). `result_ready` muxes the two engines'
`done`.

## The testbench

Follow `tern_tc_retransmit_rtl_cosim.py`'s four-step pattern; new script
`conformance/tern_tc_batch_rtl_cosim.py`:

1. **Model run.** One pass of the runner's rehearsal (start with the smaller
   wq pass, 220 frames; `rehearsal_passes` and `run_pass` are importable)
   through `HuntingBatchCell` under `RxLoss`/`TxLoss`, with a `Recorder`
   link capturing the exact request bytes that reached the cell —
   retransmits under fresh nonces and flush zeros included.
2. **RTL run.** `setkey` frame + recorded stream + zero padding to whole
   frames, through `formal/tern_tc_layer_rtl_tb.v` with the edited
   `trinet_node_core.v` and `trinet_siphash24.v`, `iverilog -g2012`, vvp
   `+req= +resp=`. **One TB change is required:** line 113's completion
   condition hard-codes 19 response bytes per frame (`n_resp < frames*19`),
   and the mixed 19/24 stream breaks it. Generalise to a `+expect=N` plusarg
   (the cosim computes `n_setx*19 + n_dot6*24` from the recorded stream);
   default `frames*19` keeps every existing invocation byte-identical. The
   TB is otherwise op-agnostic (send task + centre-sampled RX decoder) and
   is reused, not forked.
3. **Equality.** A fresh unkeyed `HuntingBatchCell` fed the same bytes must
   produce a byte-for-byte identical answer stream. The runner's decisions
   depend only on answer bytes, so equality carries the rehearsal outcome
   from the model to the RTL.
4. **Negative controls.** (a) `BatchCell` without the hunting mixin — 24-byte
   blind framing — must differ on the same lossy stream, or the stream
   exercises nothing. (b) `tern_tc_retransmit_rtl_cosim.py` rerun unchanged:
   the MAC32/SETKEY paths did not drift.

Sim time is the same order as the existing cosim (its 400 jobs ≈ 9.6 k
request bytes; the wq pass is ≈ 5.3 k plus retransmits) — minutes at
`TB_BAUD_DIV 8`, no board, test key only.

**Status (fire 12, 2026-09-29): both halves exist and are pre-validated.**
The TB generalisation (`+expect=N`, default `frames*19`) is in, with its
drift control green: `tern_tc_retransmit_rtl_cosim.py --jobs 200` PASS on
the edited TB, byte counts identical to before. The cosim script exists and
its red side is recorded: against the current core the model run is green
(wq 16/16 rows, 6 retransmits, 1 resync; 62 SETX + 162 DOT6 frames reached
the cell), the equality fails at answer byte 30 — tag byte 0 of SETX #1;
the y/status/nonce/node bytes can coincide, the 20-B vs 26-B preimage
cannot — and the core's 4275 answer bytes (225 frames × 19) against the
model's 5085 (62×19 + 162×24 + 19 setkey) is the missing-ops signature.
`--passes both` is red the same way (818 frames × 19 out, 18 517 owed).
The RTL session's remaining testbench work is therefore only: run
`tri fpga-batch-cosim` (default wq, then `--passes both`) after the core
edit and expect PASS, and rerun the retransmit cosim unchanged.

**The phantom-frame finding (why the cosim has a precondition).** Under
request-byte loss the hunting parser re-assembles misaligned bytes into
*phantom* op frames — valid op byte, garbage fields. If a phantom's
plane/chunk lands outside the model's RAM the model's assertion drops it
(no answer) while the aliasing decision below makes the RTL answer it:
the two answer streams can then never be byte-equal, and no amount of
correct RTL makes this cosim green. The cosim therefore walks its own
model answer stream first (every parsed frame must own an answer of the
right length, A5 and nonce echo) and FAILS with that diagnosis instead of
reporting a mystery diff; its drop positions are chosen so both variants
are adjudicable, and the walk re-verifies that property on every run
rather than trusting the choice. This couples the aliasing decision to
the cosim contract — see Risks.

## What `tri fpga-cost` must answer before synthesis

The command exists (`tri fpga-cost --top T --src F… [--param K=V1,V2]`; four
`synth_xilinx` flag sets; full `stat` logs land in `/tmp/fpga-cost-<top>/`).
Run it on the current core first (baseline), then on the edited core:

```
tri fpga-cost --top trinet_node_core \
    --src fpga/openxc7-synth/trinet_siphash24.v fpga/portable/trinet_node_core.v
```

1. **The RAM infers.** `RAMB36E1`/`RAMB18E1` count goes 0 → ≥ 1 (162×64 fits
   one RAMB36) rather than ~10 k flops. If it lands in FFs, the inference
   template is wrong, not the design.
2. **The delta is small and named.** LUT/FF/CARRY4 growth of the x-operand
   mux, the second sip instance (roughly a doubling of siphash area — still
   small against the node) and the wider answer builder, per flag set.
3. **DSP stays zero** in all four logs — the zero-multiplier discipline
   survives the edit.
4. Timing is explicitly *not* cost's question; that is nextpnr's on the real
   build (`fpga/openxc7-synth/build_trinet_node.py`, top
   `trinet_node_v2_ax7203`). Record, don't gate, here.

The printed row shows LUT/FF/C4/DSP only; read `RAMB*` from the `/tmp` logs
by hand, or make the two-line `board.py` change to print it — that session's
call.

## The pre-registration the board run will cite (skeleton)

- **Before any flash, all three green:** `tri fpga-batch-rehearsal`
  (26 checks), the new `tern_tc_batch_rtl_cosim.py`, and the unchanged
  `tern_tc_retransmit_rtl_cosim.py` (drift control). Plus `tri fpga-cost`
  answers 1–3 above, recorded with the logs' paths.
- **Bitstream identity:** commit sha of the RTL edit, bitstream sha from
  `build_trinet_node.py`, node id, fresh key fingerprint (never the key).
- **Run shape:** the rehearsal pair's pass sizes on the real UART; frame
  counts `n_setx`/`n_dot6` per pass pre-computed from the pass dimensions;
  ceilings from the spec (`BATCH_RETRANSMITS_MAX`, resync ceiling) — success
  is every row bit-exact vs the int8 oracle, transport counters within
  ceilings, `tri fpga-keycheck` 0 hits.
- **Reflash needs the owner's quoted «да» and a fresh `--setkey`** (SRAM
  wipes) — unchanged doctrine.
- **Speed stays unclaimed:** 235 s is the model's link arithmetic until a
  real run exists; the pre-registration pins the run's own ceilings, it does
  not inherit the projection.

## Risks and open edges

- The split-capture decode (`x8 = {x_b[1:0], w_b[7:2]}`) is the likeliest
  first-bug; the cosim's first-diff index is designed to point at it.
- The out-of-range aliasing decision is made here and flagged; the owner can
  overrule it into a guarded no-op before RTL is written. The phantom-frame
  finding above couples this decision to the cosim: byte-exact equality under
  loss requires model and RTL to agree on out-of-range frames. Three
  consistent end-states, any one of which closes the gap — the choice is the
  owner's, before RTL is written:
  1. the model adopts aliasing too — spec edit, the assertion becomes the
     same truncation — and every stream becomes adjudicable;
  2. the RTL refuses out-of-range frames (guarded no-op, no answer), so
     model-drop == RTL-no-answer — every stream adjudicable, at the cost of
     an extra guard the current plan doesn't carry;
  3. the cosim stays restricted to adjudicable streams (today's state: both
     variants configured adjudicable, and the walk re-proves it on every
     run rather than trusting the configuration).
- BRAM vs distributed RAM at 162×64 is a measurement outcome, not a choice;
  both close on an XC7A200T.
- The portability header rewrite is mandatory, not cosmetic.
