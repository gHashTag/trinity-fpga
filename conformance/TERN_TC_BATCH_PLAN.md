# Batched wire protocol for tern_tc: design plan (no board work)

This is a design document, not a pre-registration and not a result. It answers
weak point #1 of `.claude/loop/research.md` — receipt bandwidth — with the
measured numbers of the 7-token t27 run (`board_runs/gen_tokens_7_t27_reopen.log`,
2026-09-28, record in `TERN_TC_GENERATE_T27.md`). Nothing here ran on the board,
nothing here changed the RTL, and every projection below is model arithmetic,
not a measurement.

## The measured budget

6,712,896 jobs in 1414.5 s. The link is full-duplex at 1,142,857 B/s per
direction (8N1, wire rate; the host asks 1,144,744 and the adapter rounds).

| stream | bytes | seconds alone | share of wall |
|---|---|---|---|
| requests (24 B × jobs) | 161,109,504 | 1409.7 | **99.7 %** |
| answers (19 B × jobs) | 127,545,024 | 1116.0 | 78.9 % |
| wall, measured | — | 1414.5 | — |

The run is request-bound: the request stream alone accounts for the wall clock
to within the host pauses. The link ceiling at this baud is 4761.9 jobs/s
(24 B per request); the run sustained 4749 — 99.7 % of it. **Any speedup must
shrink the request stream; shrinking answers alone shortens nothing.**

## Frame anatomy

Request, 24 B (`tern_tc_layer_ax7203.py:request`, parser in
`fpga/portable/trinet_node_core.v` lines 134–152):

| bytes | field | note |
|---|---|---|
| 2 | magic `AA 55` | frame hunt |
| 1 | op | 0x01 MAC32, 0x02 SETKEY |
| 4 | nonce | little-endian; first try `FIRST_JOB_NONCE+i`, retries from a separate space |
| 8 | w | 32 trits, 2 bits each |
| 8 | x | 32 trits, 2 bits each |
| 1 | pad `00` | — |

Answer, 19 B (`parse`):

| bytes | field | note |
|---|---|---|
| 1 | magic `A5` | |
| 1 | y | signed dot, range [-32, +32] |
| 1 | status | |
| 4 | nonce | echoed |
| 4 | node id | `0x5452494E` |
| 8 | tag | SipHash-2-4 over the 26-byte preimage (op, nonce, w, x, y, node) |

Payload vs overhead per job: requests carry 16 B of operands in 24 B
(8 B overhead); answers carry 1 B of result in 19 B (18 B overhead, of which
the 8 B tag is the point of the protocol).

## What the node can and cannot do today

The RTL is stateless per frame: it hunts `AA 55`, collects 22 body bytes,
MACs, answers, forgets. The only state that survives a frame is the key. This
is what makes the link robust (24 zero bytes resync it; a lost request byte
cannot corrupt the next frame's parse) and it is also why **every option below
that changes the byte count is an RTL change** — there is no host-only batching
lever. The runner's zero-x-chunk skip (`SKIP_ZERO_X_CHUNKS`, 1,754,304 of
8,467,200 chunks already skipped in this run) is the only redundancy removal
that needs no RTL, and it is already in.

## The redundancy the request stream carries

Per matrix pass (R rows, in_dim D, C = D/32 chunks, one activation vector,
6 digit planes): jobs = R × 6 × C. For a fixed row and chunk, the **same w
bytes are sent 6 times**, once per plane. For a fixed plane and chunk, the
**same x bytes are sent R times** (up to 864).

| pass | frames now | frames with x pinned | bytes now | bytes with x pinned |
|---|---|---|---|---|
| wq (320×320) | 19,200 | 3,200 | 460,800 | 77,280 |
| gate (864×320) | 51,840 | 8,640 | 1,244,160 | 207,840 |
| down (320×864) | 51,840 | 8,640 | 1,244,160 | 208,656 |

The x-pin upload (6 × C × 8 B per pass, 480–1296 B) is the "bytes with x
pinned" column's small tail; the frame count drops by exactly the plane count,
6×, on every pass.

## The option ladder

**L0 — host-only: nothing.** Both streams are fixed by the frame parser and
the baud is at the adapter's measured ceiling. Stated plainly so nobody hunts
for a host-side trick that cannot exist.

**L1 — batch receipts (answers only; RTL + protocol change).** K jobs share
one tag: answer frame becomes `A5 | status | nonce4 | node4 | K y-bytes |
tag8`, tag over the whole batch's operands and answers in order. Per-job
answer cost (18+K)/K B: K=8 → 3.25 B, K=24 → 1.75 B (127.5 MB → 11.7 MB).
**Alone this shortens nothing** — the wall is the request stream. It matters
only composed with L2, or as link headroom (the answer direction drops from
79 % to ~10 % duty, so answer-byte loss events and resyncs become rarer).

**L2 — x-pinned dot runs (requests; RTL + protocol change). This is the
speed option.** New op SETX uploads the 6 planes of one activation vector
into node RAM (≤ 1296 B; BRAM or distributed, `tri fpga-cost` decides); a DOT
frame reuses the pinned x, keeps the same 24-B shape (x field unused or a
plane mask), and returns up to 6 y-bytes — one per plane — in one answer.
Frame count drops 6× on every pass; the run projects to 1,118,816 frames,
26.9 MB, **235 s (6.0× from the model)**, with the answer stream at 24 B per
frame (18 + 6 y) perfectly balanced against it. The MAC datapath is untouched:
the same combinational 32-trit dot, applied 6 times per frame, at a frame rate
6× lower than the runs already shipped at this clock. Whether the x RAM and
the wider answer frame close timing is `tri fpga-cost`'s question to answer on
the real synthesis, not this plan's claim. Zero-plane
chunks keep today's skip semantics; a plane mask in the frame says which of
the 6 dots to compute and return.

**L3 — nonce elision (drop 4 B/request by counter sync).** Requires node
nonce state, breaks resync-by-24-zero-bytes, saves 17 % of a stream that L2
has already cut 6×. Not worth its risk; recorded here so it is not re-derived.

## What a batched receipt proves — and what it gives up

A tag over (op, nonce, w₁x₁ … w_Kx_K, y₁…y_K, node) still binds every operand
it covers to every answer it covers, under the same key; the per-run claim
"every ternary dot product was computed on the node" survives L1 and L2
intact. What changes:

- **Matching granularity.** Today a lost answer byte costs one job's re-ask.
  A batch makes the re-ask unit K jobs. With the measured loss bound
  (1.83 events / 10^6 jobs, 95 % Poisson, `UART_LOSS_DIAG.md`) a 6.7M-job run
  expects ~12 answer-loss events; at K=24 that re-asks ~295 jobs total —
  noise against the 256-retransmit ceiling (each batch retry is one
  retransmit, 12 of 256).
- **Operand binding under L2.** The tag's preimage today contains the x bytes
  themselves. With x pinned, the DOT frame's preimage must bind the pinned
  values — e.g. the SETX answer returns a tag over the uploaded planes and
  each DOT preimage carries a digest of what is pinned. This is the one
  cryptographic design decision the spec must settle before any RTL.

## Implementation path, when the owner picks it

Spec-first, like every arm: `specs/trinet/tern_tc_batch_ax7203.t27` (op codes,
frame layouts, K, the preimage rule, the projections above as pinned tests)
→ `conformance/tern_tc_batch_from_spec.mjs` generator → a `BatchCell`
reference model extending `h.RefCell` (the whole protocol is testable with no
board, as `tern_tc_retransmit.py`'s negative controls already are) → rehearsal
pair through `tri fpga-rehearse` → RTL change in `trinet_node_core.v` →
`tri fpga-cost` on the x RAM → new bitstream → **reflash, which needs the
owner's quoted «да»** and a fresh key (`--setkey`), since SRAM wipes.

**Update 2026-09-29:** the spec and its generator now exist (the first two
steps, 17/17 in `tri fpga-specs`). The spec revises two things in this plan:
SETX rides standard 24-byte chunk frames instead of one long upload — the
parser's AA-55 hunt and the flush-resync proof survive unchanged, at 1440–3888 B
per pass instead of 480–1296 B — and the preimage rule is settled: the DOT6 tag
MACs the 48 bytes of pinned x **read from RAM for that frame's dots**, so a
receipt still covers exactly what the datapath consumed. The spec's tests are
the executable form of this plan's arithmetic; where the two disagree, the
spec wins.

## What this document does not say

- No board run, no bitstream build, no RTL edit was made. Every speed number
  above is arithmetic on the T35 log, labelled as such.
- L2's 235 s is the model's number for the link alone; setup, keycheck and
  host pauses sit outside it, and a real run gets its own pre-registration
  with its own ceilings before anything is claimed.
- Nothing here is a throughput claim about the model or the project; it is a
  wire-budget claim about one UART link. The competitor table in
  `.claude/loop/research.md` stays as written.
