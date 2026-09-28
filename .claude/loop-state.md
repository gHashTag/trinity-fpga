# Loop state — t27-coder improvement cycle (started 2026-09-28 ~16:00Z)

This file coordinates the 15-minute cron loop (job 25699f12). Every fire MUST
read this first, follow the LOCKS, do the next READY item, update this file,
and never restart anything marked IN-PROGRESS or DONE.

## LOCKS (do not touch while IN-PROGRESS)

| phase | status | notes |
|---|---|---|
| T35 spec + wrappers authoring | DONE | committed 8955ea793 (fire 2); specs/generators/params/wrappers/CPU logs |
| T35 rehearsal pair | DONE | PASS x2, committed c24d25b7a; ids equal CPU_INT_IDS, 2 reopens, key hits 0 |
| T35 board run | DONE, PASS | 2026-09-28T17:13–17:36Z; 6712896/6712896 receipts, ids == CPU_INT_IDS, 0 reopens; record conformance/TERN_TC_GENERATE_T27.md; no live board work remains |

**UART lock:** before any board command, check `lsof /dev/cu.usbserial-110`.
If a `tri fpga-run` or runner python process holds it, DO NOTHING to the board —
only read logs and post-process. Never start a second board run while one is
live; the live run's log path will be recorded in the table above at launch.

## DONE (do not redo)

- tern_tc fine-tuned on 8K-tokenized t27 FIM corpus: 337 steps, val bpb 0.756 →
  0.611. TC02 export sha256 `3d8397ef4e388d0cadd1725f64d45ddd4ca0811cf8fbedc4a6a3b2fe92cd45cc`,
  local copy `~/igla-coder-gpu/c_infer/t27_tuned/model.bin`, volume copy
  `/workspace/runs/tern_tc_t27/`. Pod `tct27` (4ag51eby80mgg2) STOPPED, total
  cost $0.58, balance $74.68. Do not create new GPU pods without a new training
  need; corpus copies: `/workspace/ft_t27_8k` and local `/tmp/ft_t27_8k`.
- Local demo (before/after): t27-tuned model writes structurally real t27
  (`test name { assert ...; }`), wrong facts, greedy repeat loop; Python partly
  forgotten. Driver: `/tmp/t27_prompt_demo_tuned.py` (MODEL points at the new bin).
- T35 discovery: N_TOKENS is 7, not 32. The t27-tuned model emits EOT (id 0) at
  token 7: ids `204 264 397 226 21 277 0` = `'\n    return 0;\n<|endoftext|>'`,
  the first arm whose length the model, not the host, chooses. Asked for 128
  tokens the host still stops at 7 (pre-registered in the spec, logged in
  `conformance/cpu_runs/gen_tokens_7_t27_counts.log`). JOBS 6712896, skipped
  1754304, rows 118272, calls 168, margin 210 milli int / 190 c.
- C_REF pin drift fixed (fire 1-2): igla-coder-gpu 52be443 added two
  portability header lines to tc_infer.c after T33/T34 pinned the old bytes.
  Doctrine: C_REF is a reference of record, never read at run time — the pin is
  satisfied by on-disk match OR bytes reachable from the reference repo's git
  history (gitBlobSha in the three generation generators). HARNESS/MAC32/MODEL
  stay strict. `tri fpga-specs` 16/16 clean after the fix.
- T35 pre-registration committed (8955ea793): both specs (generation sha
  6cd04860…, reopen sha 648451ff…), both generators, params (generation
  2180507d…, reopen 76ae75a2…), both wrappers (self-tests PASS), five CPU logs.
  4 of 5 scheduled rehearsal losses fire (rx hole at 137468535 lies past the
  127545024-byte answer stream — pinned by a spec test, not hidden).
- T35 BOARD RUN PASS (fire 3, 2026-09-28T17:13:09Z–17:36:44Z):
  `gen_tokens_7_t27_reopen.log`. receipts 6712896/6712896 under node
  0x5452494e; rows 118272/118272 bit-exact; transport all zero (0 retransmits,
  0 resyncs, 0 reopens); 4749 answers/s; ids `204 264 397 226 21 277 0` ==
  CPU_INT_IDS; decode `'\n    return 0;\n<|endoftext|>'`. USB clients flat 11
  in all 48 samples. keycheck 0 hits. Record: conformance/TERN_TC_GENERATE_T27.md.
- tri CLI new command (fire 3): `tri fpga-runlog [NAME] [--tail N] [--watch S]`
  — one-command progress read of a live/finished run, log-grammar parser with
  self-test, in board.py `runlog`; dispatch line in ~/.local/bin/tri.
- decode anomaly fixed (fire 3): `tri fpga-decode` had GEN_SPEC hardcoded, so
  decoding the T35 log cross-checked the BASE model sha and printed it as if
  the run had used it. Now decode reads the log's own `spec … sha256 …` header
  line (reopen specs resolve via GENERATE_SPEC_FILE), notes any drift, falls
  back to GEN_SPEC only for logs without the line. decode self-test 16/16
  (decode_spec resolution itself now covered: reopen-log chain, own-spec,
  drift-named, missing-spec fallback, no-spec-line fallback).
- Batched wire protocol designed (fire 4): `conformance/TERN_TC_BATCH_PLAN.md`
  — measured wire budget from the T35 log (requests 161.1 MB = 99.7 % of the
  1414.5 s wall; answers 127.5 MB = 79 %; 4749 of 4762 jobs/s ceiling), exact
  frame tables (24 B request / 19 B answer / 26-B tag preimage), the 6×
  per-pass request redundancy (w chunk sent once per digit plane), and the
  option ladder: L0 host-only = nothing (proved, the parser is stateless per
  frame), L1 batch receipts (answers only, no wall gain alone), L2 x-pinned
  dot runs (6× fewer frames, model 235 s vs 1414.5 s), L3 nonce elision
  (rejected). All of L1/L2 are RTL changes — research.md's earlier "RTL
  unchanged" guess retracted in place. Design only: no RTL edit, no bitstream,
  no board work; projections are model arithmetic, labelled as such.
- Fire 4 output committed and pushed (c06816a49): batch plan, research fix,
  loop-state. `tri fpga-budget` (fire 5) later printed the same budget with the
  spec's BAUD (1,144,744) instead of the adapter's wire rate: 99.5 % / 4,769.8
  ceiling — same verdict, and the ~0.2 % rounding is now named in the output.
- Fire 5 audit triage: 4 anomalies → 4 causes. (1) `*.clients_tail.log`
  handoff-watcher logs falsely demanded `# exit=` — the checker now accepts
  `# end` alone for them (they end at the run's end and have no exit of their
  own); re-audit clean. (2) Stale `loop` claim lock — `--heal` could not
  reclaim a claim lock (only a UART lock), cleared via claim+release. (3)+(4)
  The two igla-coder-gpu anomalies (unpushed commits, uncommitted records) are
  a LIVE sibling session's active workstream (tc_fast sampling speedup, commits
  minutes old, LEDGER.md +228) — left entirely to it; this loop never commits
  or pushes there while that session is alive.
- tri CLI new command (fire 5): `tri fpga-budget [NAME] | --self-test` — wire
  budget of a finished run (streams, shares of wall, jobs/s vs ceiling,
  request-bound/answer-bound verdict). Constants come from the log-cited spec:
  `decode_spec` gained a `need` parameter (resolution stops at the first chain
  spec pinning the wanted constants; reopen specs pin REQ_LEN/RESP_LEN/BAUD
  themselves, so a reopen log's budget no longer refuses). decode self-test
  16→17, budget self-test 7/7; live on both reopen logs (t27: request-bound
  99.5 %, gen_tokens_8_reopen: request-bound 98.7 %). Dispatch + help lines in
  ~/.local/bin/tri (runlog's missing help line added too); SKILL.md section.
- L2 batch protocol spec written (fire 6): `specs/trinet/tern_tc_batch_ax7203.t27`
  + `conformance/tern_tc_batch_from_spec.mjs` + generated
  `conformance/tern_tc_batch_params.py`; `tri fpga-specs` 16→17 clean. Design
  only — no RTL, no runner, no board. Two design advances over the plan:
  (1) SETX rides standard 24-B chunk frames (one x chunk per frame), so the
  node's AA-55 hunt, the 22-B body and the flush-resync proof survive
  unchanged — price 1440–3888 B upload per pass vs the plan's 480–1296 B
  payload, per-pass saving 5.89× (>5× pinned); (2) the preimage rule settled:
  DOT6's tag MACs the 48 B of pinned x READ FROM RAM for that frame's six
  dots (preimage 73 B), so a receipt still covers exactly what the datapath
  consumed, RAM drift included. The compiler caught two of my own arithmetic
  errors in the draft (PREIMAGE_DOT6 74→73; 6×L2-per-pass-bytes is NOT <
  now-bytes with upload overhead — honest pin is 5×). Generator readbacks:
  constants from the reopen spec text, op codes from the harness + MAC32
  source (0x03/0x04 must be absent from both), the AA-55/22-B RTL shape, and
  the plan's projection anchors. TERN_TC_BATCH_PLAN.md got an update note:
  first two implementation steps exist; where plan and spec disagree, the
  spec wins. Option A is now a ready-to-pick: next steps would be the
  BatchCell reference model and rehearsal pair — both still no-board work.
- BatchCell reference model written (fire 7): `conformance/tern_tc_batch_model.py`
  — BatchCell subclasses the harness's RefCell (OP_MAC32/OP_SETKEY inherited
  untouched) with OP_SETX and OP_DOT6 per the spec; BatchHost is the host half
  against the link interface (the same host code will drive the real node
  unchanged). Constants come only from `tern_tc_batch_params.py`. 24 self-test
  checks PASS (`tri fpga-batch`, new tri dispatch + help line; SKILL.md
  section). The preimage rule is demonstrated both ways: a corrupted RAM write
  passes its SETX receipt and is caught by DOT6 ('tag'); RAM drift is caught
  by the tag even when the dot cannot see it ('tag' vs 'damage', the pair
  pinned with two crafted w vectors); plus lie/damage/nonce/wrong_key/drop/
  replay negatives, mask semantics, the mask-0 readback probe, unkeyed/setkey
  flows, and a mini end-to-end pass (8 rows × 320: every row dot bit-exact vs
  the int8 oracle, 140 batched frames vs 480 today). Still design only — no
  RTL, no runner, no board.
- RTL testbench plan written (fire 9): `conformance/TERN_TC_BATCH_RTL_PLAN.md` —
  the plan a future RTL session executes, read from the real sources
  (trinet_node_core.v at e45e8269c, tern_tc_batch_model.py,
  tern_tc_retransmit_rtl_cosim.py, formal/tern_tc_layer_rtl_tb.v,
  build_trinet_node.py, board.py's cost). Core findings the plan pins: the
  UART RX and the frame parser change ZERO lines (both ops re-read the
  existing w_b/x_b capture; SETX's x8 spans the register boundary as
  {x_b[1:0], w_b[7:2]} — named as the likeliest first bug); three additions
  only — a 162x64 inferred x RAM (one SETX frame = one word), the six-dot
  datapath as a mux + 6-cycle walk reusing the existing dot network, and a
  SECOND trinet_siphash24 instance at MSG_BYTES=73 (MAC32's 26-B engine
  untouched; ~46 clocks vs ~22, both noise vs 210 us of line time). The
  answer builder grows to 24 B behind a resp_len register. The cosim follows
  the retransmit cosim's four steps (Recorder-wrapped runner pass -> TB ->
  byte-equal HuntingBatchCell -> negative controls); the TB needs exactly one
  change — line 113 hard-codes 19 B/frame, generalised to +expect=N with the
  19xB default byte-identical. Out-of-range addressing decided: truncate-and-
  alias (receipts never lie about what they MAC; self-harm only) — flagged
  for the owner. The portability header's "no inferred RAM" line must be
  rewritten when the RAM lands. fpga-cost questions fixed: RAM infers
  (RAMB36E1 0 -> >=1), small named LUT/FF delta, DSP stays 0; timing is
  nextpnr's question, not cost's. Pre-registration skeleton included (three
  greens before any flash; reflash still needs the owner's «да» + fresh
  setkey; 235 s stays a model number). Design only — board, pods, RTL
  untouched.
- fpga-cost baseline of the current core recorded (fire 10, measurement
  only): `tri fpga-cost --top trinet_node_core --src
  fpga/openxc7-synth/trinet_siphash24.v fpga/portable/trinet_node_core.v`
  at commit e45e8269c, native yosys 0.67, 37-48 s per run —
  builder LUT 2010 / FF 1082 / C4 0, abc9+carry LUT 1358 / C4 81,
  abc,nocarry LUT 1998, abc+carry LUT 1389; DSP 0 and B36 0 B18 0 in every
  flag set (the core has no RAM today — the "before" column of the RTL
  plan's question 1). Verified twice: hand-grep of the /tmp stat logs equals
  the printed rows, and the run after the tool edit below reproduced the
  same numbers. `tri fpga-cost` now prints BRAM (B36/B18) in its row
  (board.py cost; tri help line updated; SKILL.md notes it: an inferred RAM
  is proven by the RAMB count rising, not by compiling — FF inflation means
  the template is wrong). Logs in /tmp/fpga-cost-trinet_node_core/.
- Batch runner written (fire 8): `conformance/tern_tc_batch_runner.py` — whole
  passes pipelined through BatchCell the way tern_tc_retransmit.py drove
  RefCell (one window, one nonce space, retries under fresh nonces, per-row
  recombination vs the int8 oracle). 26 self-test checks PASS
  (`tri fpga-batch-rehearsal`, new dispatch + help; SKILL.md section). The
  runner's own two findings: (1) the answer stream is length-ambiguous — 19-B
  SETX and 24-B DOT6 answers share the A5 magic with no length field; the
  runner shapes each read by which nonce position names an issued nonce and
  lets the tag break ties, and ties are NOT rare: 8 natural y-nonce
  collisions in the honest 814-frame rehearsal (~1% of DOT6 frames), every
  one settled by tag, while a fixed-length parse would false-stop on each
  ('status' from the y byte). The self-test also crafts one deterministically.
  (2) retries must stay inside their pass — a retry after the next pass's
  SETX would read overwritten RAM, fail its tag and burn the receipt space;
  run_pass runs to completion per pass, one Budget shared across passes.
  Also pinned: recovery over RxLoss/TxLoss and the RTL hunting parser
  (HuntingParser mixin; out-of-range garbage frames drop — the model raises,
  the spec leaves the real behaviour to the RTL), zero-plane skip (identical
  rows, R fewer DOT6 frames per all-zero chunk), every hard stop kept
  (lie/duplicate/status stop; wrong_key/ram_drift exhaust). Design only —
  board, pods, RTL untouched. Option A now has spec + params + model +
  runner; the RTL and the reflash remain.
- Batch cosim pre-built red + TB generalisation (fire 12): option A's
  testbench half now EXISTS ahead of the RTL edit, test-first.
  `formal/tern_tc_layer_rtl_tb.v` gained `+expect=N` (default frames*19,
  byte-identical to the old hard-code — proven by the retransmit cosim
  `--jobs 200` PASS with identical byte counts after the edit).
  `conformance/tern_tc_batch_rtl_cosim.py` (dispatch: `tri fpga-batch-cosim`,
  `--passes wq|both`, `--keep`) follows the retransmit cosim's four steps:
  recorded lossy rehearsal stream → TB under iverilog → byte-equal fresh
  HuntingBatchCell → blind-framing negative control. Red side validated on
  both variants: model green (wq 16/16 rows, 6 retransmits, 1 resync,
  62 SETX + 162 DOT6; both 32/32 rows), RTL differs from answer byte 30
  (tag byte 0 of SETX #1 — 20-B vs 26-B preimage) and emits 19 B per frame
  (wq 4275 vs 5085 owed; both 15542 vs 18517). THE FINDING: after a tx drop
  the hunting parser can re-assemble a *phantom* op frame whose plane/chunk
  lands out of range — the model's assertion drops it, the plan's
  truncate-and-alias RTL would answer it, so those streams can never be
  byte-equal. Not a cosim bug: a real semantic gap caught before any RTL.
  The cosim carries `walk_answers` (every parsed frame must own its answer:
  length, A5, nonce echo) and refuses non-adjudicable streams with that
  diagnosis instead of a mystery diff; both variants are configured
  adjudicable (`both` = first drop +6) and the walk re-proves it every run.
  Three resolutions pinned in the plan's Risks — model adopts aliasing /
  RTL guarded no-op / adjudicable-only cosim — owner's pick, before RTL.
  Regressions green: batch 24/24, rehearsal 26/26, keycheck 0 hits.
  Board, pods, RTL design untouched (TB is test fixture, explicitly allowed).

## READY (next work, in order)

1. Fire 4 committed (c06816a49) and fire 5's cheap item (fpga-budget) is done.
   The remaining options all need the owner awake: A (implement the batch
   protocol — RTL change + reflash, owner's «да»), B (Ethernet receipt path),
   C (corpus round 2 — spends pod money). Until the owner picks, a fire can
   only: keep the anomaly scan running (`tri fpga-audit`, keycheck,
   `tri fpga-specs`), or do pure-design work in the same spirit (no board, no
   pods, no RTL). Do not start A/B/C alone.
2. The no-hardware queue for option A is EMPTY as of fire 12 — spec, params,
   model, runner, RTL plan, fpga-cost baseline (fires 6-10) AND the
   testbench half (fire 12: TB `+expect=N` + the pre-built-red cosim `tri
   fpga-batch-cosim`). An RTL session that starts after the owner's «да» is
   now purely: core edit per TERN_TC_BATCH_RTL_PLAN.md, then `tri
   fpga-batch-cosim` (wq, `--passes both`) expecting PASS + the retransmit
   cosim unchanged. The owner also owes one pick before RTL: which of the
   three phantom-frame resolutions in the plan's Risks (model adopts
   aliasing / RTL guarded no-op / adjudicable-only cosim). Until then a fire
   is audit-only: `tri fpga-loopcheck` (fire 11 packaged the whole sweep —
   git + specs + keycheck + audit + one verdict line; exit 1 with exactly
   the two igla-coder-gpu anomalies is the known floor, anything beyond is
   new) — do not invent make-work; an audit-only fire is an honest fire.
   The only cheap extra if the owner stays asleep for many fires: re-check
   `.claude/loop/research.md` competitor movement (read-only, rare, last
   refreshed fire 8).
3. Never commit or push igla-coder-gpu while its live session works (see DONE,
   fire 5 triage); document anything found there in this file instead.
4. End-of-fire report + three collaboration options; self-critique and anomaly
   scan; append fire log line.

## Standing rules (every fire)

- Never touch the 20 fleet pods (all EXITED; leave them).
- RunPod key `/tmp/rpk2.txt`: never print, only masked; values file→env inside
  one Bash call. Token stays.
- Board logs are committed only after `tri fpga-keycheck` passes (0 key hits).
- English for all repo code/docs/commits; Russian only in chat.
- Self-check each fire: `git status` should contain only this cycle's files;
  `tri fpga-specs` after any spec edit; if something is broken, fix the root
  cause (never skip tests, never delete past evidence).
- End of every fire: append a short line to `## Fire log` below.

## Fire log

- fire 1: loop scheduled (25699f12); state file created; T35 CPU computation
  started; T34 pattern files read.
- fire 2 (2026-09-29): T35 N_TOKENS discovered = 7 (EOT); both specs written
  and green; C_REF drift root-caused (igla-coder-gpu 52be443) and fixed via the
  reference-of-record doctrine; generators + params + wrappers done, self-tests
  PASS, 16/16 specs clean, five CPU logs, pre-registration committed 8955ea793;
  rehearsal pair launched in background (bh7e4oe9h). Ready item names corrected
  to gen_tokens_7_t27 / --limit 3800.
- fire 3 (2026-09-29 ~00:40 local): rehearsal pair verified PASS and committed
  (c24d25b7a); board run launched after quiet+watch-clients, watched to
  completion with the new `tri fpga-runlog --watch` — PASS, all numbers equal
  the pre-registration; decode + keycheck + record doc
  conformance/TERN_TC_GENERATE_T27.md done; competitor/weak-points research
  written to .claude/loop/research.md; fpga-runlog added to tri (self-test
  green); decode GEN_SPEC hardcoding fixed (self-test 11/11); skills updated
  (gpu-finetune new, t27-spec pin doctrine, ax7203-board-loop runlog section).
- fire 4 (2026-09-29): batch wire plan written
  (conformance/TERN_TC_BATCH_PLAN.md) from the sources, not assumptions —
  frame tables from tern_tc_layer_ax7203.py / trinet_mac32_conformance, window
  mechanics from tern_tc_retransmit.py, stateless parser confirmed in
  trinet_node_core.v; request-bound fact measured (99.7 %); research.md option
  A corrected (RTL change, not "RTL unchanged"); skill got the request-bound
  line; READY rewritten — A/B/C all need the owner, pure-design or audit-only
  until then.
- fire 5 (2026-09-29): fire 4 committed+pushed (c06816a49); audit triaged —
  clients_tail checker fixed (handoff logs end at `# end`), stale claim lock
  cleared, igla-coder-gpu anomalies identified as a live sibling session and
  left to it; `tri fpga-budget` built (decode_spec `need` parameter, self-tests
  decode 17/17 + budget 7/7, live request-bound verdicts on both reopen logs,
  tri dispatch + help, SKILL.md). Board untouched, pods untouched, RTL
  untouched.
- fire 6 (2026-09-29): the L2 batch protocol became an executable design —
  specs/trinet/tern_tc_batch_ax7203.t27 (69 consts, 9 tests, 67 asserts, 0
  failures) + conformance/tern_tc_batch_from_spec.mjs (sha pins, reopen-spec
  readbacks, op-code freeness guards, RTL shape guards, plan anchors) +
  generated tern_tc_batch_params.py; `tri fpga-specs` 17/17. Plan updated with
  the spec's two revisions (SETX chunk frames; RAM-read preimage) and repinned.
  The compiler caught three draft mistakes (DOT6 preimage 74→73, no parens in
  .t27 asserts, the false 6×-with-upload claim → honest 5× pin). Design only:
  board, pods, RTL untouched. READY rewritten: BatchCell reference model is the
  next no-hardware item.
- fire 7 (2026-09-29): BatchCell reference model shipped
  (conformance/tern_tc_batch_model.py, 24 checks PASS) + `tri fpga-batch`
  dispatch/help + SKILL.md section; loop-state updated. Three draft-test
  mistakes caught by the first self-test run (inverted mask indices, damage-vs-
  tag class mixup, wrong_key refusing at SETX). Preimage rule demonstrated
  both ways. Board, pods, RTL untouched.
- fire 8 (2026-09-29): batch runner shipped
  (conformance/tern_tc_batch_runner.py, 26 checks PASS) + `tri
  fpga-batch-rehearsal` + SKILL.md section. Two findings worth keeping: the
  answer stream is length-ambiguous and ties are common (8 natural y-nonce
  collisions in the honest 814-frame rehearsal, ~1% of DOT6 frames —
  shape-by-issued-nonce + tag-tiebreak is a requirement, not polish), and
  retries must stay inside their pass or they read the next pass's x RAM.
  One real bug found by the first run (issued[] gave a job index where a job
  was expected) plus two draft mistakes caught on review (a leftover buffer
  for bytes the link itself holds, a hand-rolled replay fault the model
  already ships). research.md competitor table refreshed (TeLLMe + the
  nicholi.ai $130-board engine; claim-guard rejected my first wording of
  "Multiply-Free" <!-- claim-guard: ignore-line --> as a title-shaped claim — reworded to attribute the
  multiplier-freedom to the network). Board, pods, RTL untouched.
- fire 9 (2026-09-29): RTL testbench plan shipped
  (conformance/TERN_TC_BATCH_RTL_PLAN.md), written from the real sources —
  the parser needs zero changes (SETX/DOT6 re-read w_b/x_b; x8 spans the
  boundary as {x_b[1:0], w_b[7:2]}), three additions only (162x64 x RAM,
  muxed six-dot walk, second siphash at 73 B), the cosim pattern reuses the
  retransmit cosim + formal/tern_tc_layer_rtl_tb.v with one generalisation
  (+expect=N for mixed 19/24-B answers). READY's queue for option A is now
  empty except the fpga-cost baseline measurement (next fire's default).
  Board, pods, RTL untouched.
- fire 10 (2026-09-29): fpga-cost baseline recorded (LUT 1358-2010 / FF
  1082 / C4 0-81 / DSP 0 / B36 0 B18 0, all four flag sets, native yosys
  0.67, 37-48 s) — the "before" column of the RTL plan's cost question,
  verified twice (hand-grep = printed rows = post-edit rerun). tri fpga-cost
  now prints BRAM B36/B18 (board.py + help + SKILL.md). READY's no-hardware
  queue for option A is now empty; next fires default to audit-only until
  the owner picks A/B/C. Board, pods, RTL untouched.
- fire 11 (2026-09-29): audit-only fire. Regression sweep green (batch model
  24/24, runner 26/26, spec generator check PASS, cron 25699f12 alive). The
  sweep itself is now a tool: `tri fpga-loopcheck` (board.py cmd_loopcheck +
  tri dispatch + help + SKILL.md note) runs git status (informational; the
  cron lock is recognised) + specs + keycheck + audit and prints one greppable
  verdict line; exit is the OR of the three real components. First live run
  reproduced the individual commands exactly: specs 17/17, keycheck 72 files
  0 hits, audit 56 logs with only the two known igla-coder-gpu anomalies —
  exit 1 is the known floor while the sibling session lives, not a new
  finding; anything beyond those two lines is new and gets read first.
  Board, pods, RTL untouched.
- fire 12 (2026-09-29): option A's testbench half built test-first.
  `formal/tern_tc_layer_rtl_tb.v` `+expect=N` (default frames*19
  byte-identical; retransmit cosim --jobs 200 PASS post-edit) +
  `conformance/tern_tc_batch_rtl_cosim.py` (`tri fpga-batch-cosim`), red
  validated on wq and both: model green, RTL differs from byte 30, 19
  B/frame vs the mixed 19/24 stream owed. FINDING: phantom out-of-range
  op-frames after a tx drop are model-dropped but alias-RTL-answered —
  byte equality impossible on such streams; cosim gained walk_answers (loud
  refusal, both variants configured adjudicable) and the plan's Risks now
  pin the three resolutions for the owner's pre-RTL pick. Regressions:
  batch 24/24, rehearsal 26/26, keycheck 0 hits. Board, pods, RTL design
  untouched.
- fire 13 (2026-09-29): audit-only + the sanctioned research re-check
  (first since fire 8). Loopcheck floor unchanged (specs 17/17, keycheck 72
  files 0 hits, exactly the two igla anomalies, ahead stayed 16 — sibling
  idle this window). research.md: two wedge-adjacent entrants added
  (TensorCommitments arXiv 2602.12630 — pairing-based verify, 12 ms,
  software/GPU; Animica AICF 7.1.1 — ML-DSA-65-signed API receipts,
  software gateway) — the "verifiable inference" vocabulary is heating but
  every entry is a software layer; still nobody receipts on the silicon,
  wedge intact, claim now scoped "on-hardware receipts" against zkML
  collision. Options section refreshed to post-fire-12 reality (A =
  phantom pick + core edit + reflash only). Board, pods, RTL untouched.
