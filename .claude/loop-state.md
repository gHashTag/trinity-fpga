# Loop state — t27-coder improvement cycle (started 2026-09-28 ~16:00Z)

This file coordinates the 15-minute cron loop (job 25699f12). Every fire MUST
read this first, follow the LOCKS, do the next READY item, update this file,
and never restart anything marked IN-PROGRESS or DONE.

If the loop is DEAD (no fire in ~an hour, or this file's newest fire-log
entry is old): the session that held job 25699f12 is gone — the job was
session-only. A new session restarts it with `/loop 15m` and the SAME
mandate text (in the old session's first message), then continues from this
file: LOCKS first, `tri fpga-fire start` for the next fire, Standing rules
below. Past work cannot be broken by the restart — it is all in LOCKS/DONE
rows and committed history; the only thing a new job id changes is who fires
next.

## LOCKS (do not touch while IN-PROGRESS)

| phase | status | notes |
|---|---|---|
| fire 17: tri fpga-tools (tool self-test sweep) as loopcheck's 4th component | DONE | sweep 6/6 green after catching real decode rot (hardcoded fire-2 sha, stale after the fire-14/15 cascades — decode was right, the test was wrong; fixed hermetically 18/18 + the once-real-stale-sha fixture pinned), loopcheck now 4 components, tools meta 9/9; competitor re-check skipped (fire 16 refreshed it hours ago); specs 17/17, keycheck 0, host-side only; no board/pods/RTL |
| fire 18: tri fpga-loopstate (loop-state.md integrity linter) as loopcheck 5th component | DONE | self-test 9/9 (8/9 on first run — its own live check caught the loop's mid-fire log window; protocol fixed: stub+row together at start); loopcheck now 5 components, live sound; specs 17/17, keycheck 0, host-side only; no board/pods/RTL |
| fire 19: audit sweep + sibling engine-semantics check (did igla-coder-gpu's engine change turn semantic?) | DONE | answer: NO — tc_infer.c has 0 commits and 0 diff since 52be443; sibling engine work is tc_fast (separate bench harness) + research scripts; C_REF pin doctrine and C_GREEDY_IDS unaffected, no re-pin decision pends; loopcheck floor = exactly the 2 igla anomalies (LEDGER.md, ahead 19); specs 17/17, keycheck 0, tools 6/6, loopstate sound; read-only on sibling; no board/pods/RTL |
| fire 20: pin-target existence — do the /tmp-pinned E3 inputs survive, and does specs fail loudly if a pinned file is missing? | DONE | empirical map: specs --check = output-drift + REPO pins (loud, both modes); /tmp pins deliberately the runner's (generator comment); tmpcheck GONE loud, --restore heals (live-proven, sha matched); audit prints info line for gone-but-kept — my mid-fire claim that audit missed it was a too-narrow grep, corrected by full-output retest; NEW standing rule: a fire that sees the audit gone-line runs tmpcheck --restore; gates green to floor 2; no tool change needed — the gap was protocol; no board/pods/RTL |
| fire 21: tri fpga-fire start — atomic lock row + fire-log stub, mechanical enforcement of the fire-18 protocol | DONE | self-test 6/6 hermetic (never the live file — this tool writes), live refusal verified (rc=1 while fire 21 IN-PROGRESS, file untouched); tools sweep 6→7 all green; shared lock_rows refactor: linter and fire-start parse rows through ONE helper; first live start = fire 22; host-side only; no board/pods/RTL |
| fire 22: audit sweep + first live fire-start (happy path of the fire-21 tool) | DONE | happy path verified live: row placed after the last LOCKS row, stub at the log tail, ONE write, lint sound; cron-death resume paragraph added to the header (/loop 15m + same mandate + this file = restart without breaking past work); gates green to floor 2 (specs 17/17, keycheck 0, tools 7/7, loopstate sound, no gone-inputs line); host-side only; no board/pods/RTL |
| fire 23: E4 stack decision table for the owner's pick + LOCKS compaction rule | DONE | NODE_ETHERNET_PLAN.md gained the E4 decision table (assembled from already-checked facts only; recommendation = minimal responder on E3's fabric capture — both vendored stacks need their IDDR PHY swapped for E3's anyway); Standing rules gained the LOCKS-bounded rule (drop old DONE rows past ~15, never log entries); the transient third audit anomaly was this fire's own uncommitted plan edit — cleared by the commit; gates green to floor 2 after commit; host-side only; no board/pods/RTL |
| fire 24: phantom-frame decision table for option A + corpus round-2 cost memo for option C | DONE | TERN_TC_BATCH_RTL_PLAN.md gained the phantom-frame decision table (three Risks end-states side by side; recommendation = 1, model adopts aliasing — the one edit that makes the model agree with the plan's own RTL-side choice, converts the cosim pre-walk from filter to invariant check, costs no gates); research.md option C gained the round-2 cost memo ($0.58 round 1, $74.68 balance → round 2 costs dollars not tens; binding constraint is corpus quality for multi-line output, not money); gates at floor 2 (audit re-checked with FULL output, not a filtered grep — the fire-20 lesson applied); host-side only; no board/pods/RTL |
| fire 25: fire-log rotation: entries of de-indexed fires archive to .claude/loop/firelog-archive.md, linter learns the combined index, tri fpga-firelog | DONE | the file's unbounded growth closed: entries whose fires lost LOCKS rows move verbatim to the archive (13 moved live: fires 2–14, file 678→551 lines); linter counts a fire's entry in either home; fire-start numbers above the archive max too (self-test caught the collision case); archive written FIRST so a crash duplicates rather than loses; firelog self-test 9/9 (first run 8/9 — a test-hygiene bug: two states sharing one loop/ dir; fixed, not code), tools 8/8, loopcheck at floor 2 (igla ahead 25); standing rule added; host-side only; no board/pods/RTL |
| fire 26: competitor re-check (rare cadence due: last fire 16, now 26) — read-only sweep, research.md refresh if anything moved | DONE | moved: PENSA added (NeurIPS 2026, Alveo U50 HBM, BitNet 2B4T full on-FPGA, 58.09 tok/s @ctx128, no verifiability — throughput tier) and TRACE added (Linux Foundation/CoSAI Aug 2026: workload-level Trust Records, root = CPU TEEs SEV/TDX, 135k PyPI downloads/10wk — attestation tier, complement but "receipt" vocabulary collision); ternfpga unchanged (72 commits, no receipts), Ternarycore active to Jul 2026 (hw verification) but RTL-correctness only; wedge INTACT — nobody receipts on accelerator silicon; scoping line sharpened to "on-silicon per-job receipts" (was "on-hardware"); READY re-check cadence reset to fire 26; gates at floor 2; read-only web + repo docs; no board/pods/RTL |
| fire 27: stamp-probe midnight bug: the audit calibration probe crosses a UTC date boundary in the [00:45,01:00) window and false-reports blindness — fix the probe, add a regression at the caught instant | DONE | root cause proven empirically before the edit (probe 00:02 UTC vs commit 23:47 previous day → replace() lands earlier-on-commit-date → not flagged; window edges [00:45,00:59:59] blind, 01:00 and 14:00 controls flag); stamp_probe() steps the synthetic commit back hour-by-hour until stamp and commit share a UTC date — probe stays inside future_stamps' documented same-date scope at every instant; tri fpga-stamps added (the check alone + calibration; self-test 9/9 incl. the caught instant 00:47:53Z and both window edges), tools sweep 8→9, dispatch + tri wrapper; live proof INSIDE the window: audit 00:57:26Z third anomaly gone, floor 2; corpus-durability fact recorded in research.md option C (no ft_t27_8k builder in the repo); host-side only; no board/pods/RTL |
| fire 28: corpus durability keep: the round-1 ft_t27_8k corpus (16M, no builder in the repo) lives only in volatile places — give tri a keep command in the tmpcheck blob pattern and keep it for real | DONE | tri fpga-keep PATH TAG reuses tmpcheck's substrate (blobs/<sha> gitignored + tracked MANIFEST.tsv rows, pins keep:TAG beside existing spec pins) so a kept tree gets the watching/restore machinery free — no second watcher built; self-test 9/9 hermetic (dedup, idempotence, pre-existing rows untouched, tmpcheck integration, rmtree→restored, refusals); first run caught its own test bug live: the outside-/tmp refusal leaned on TMPDIR and this host has TMPDIR=/tmp — fire 25's host-env lesson again, fixed to a string-level guard + nothing-written assertion; LIVE keep: 92/92 files, tag keep:ft_t27_8k, tmpcheck now 98 pinned /tmp files 0 lost 0 unkept, --restore rebuilds after reboot; tools sweep 9→10, loopcheck floor 2; MANIFEST.tsv committed (tracked) |
| fire 29: corpus builder derivability: the missing ft_t27_8k builder — read manifest.json/items.jsonl/tokenizer, find what derives them and from what; if derivable, write a builder verified sha256-identical to the fire-28 manifest; if not, document exactly what is unknowable | DONE 2026-09-29 | builder found: sibling t27_bench.py fim (deterministic, no RNG); pin proven; tri fpga-derive verifies 92/92 (91 byte-identical + manifest.json content); loopcheck floor 2 |
| fire 30: LOCKS compaction (18 DONE rows past the ~15 bound) + audit-only sweep; competitor re-check not due (fire 26, next ~36) | DONE 2026-09-29 | LOCKS 18→15 DONE rows (three T35 phase rows dropped; facts preserved in DONE bullets + git), firelog archive a correct no-op (fires 2–3 entries already archived at fire 25), lint sound, 17 table lines verified; loopcheck floor = exactly the 2 igla anomalies; host-side only; no board/pods/RTL |
| fire 31: tool-source durability: board.py + SKILL.md + tri wrapper exist only uncommitted outside the repo — snapshot through the keep substrate so a skills-repo reset cannot lose the loop tooling; audit sweep | DONE 2026-09-29 | risk proven real (whole skill dir UNTRACKED, git log empty — zero committed copies of 27 fires of tooling); 4 files snapshotted /tmp/loop_toolsrc, kept keep:toolsrc (secret-scanned first), refresh re-keep sha-deduped 1-new/3-same; standing rule + SKILL.md lesson; loopcheck floor 2 |
| fire 32: corpus diagnosis: why one-line output — replicate the sibling fim split over kept items.jsonl and measure what fraction of training targets (mid) were multi-line; round-2 design note for option C; LOCKS compaction (17 DONE rows) | DONE 2026-09-29 | verdict: corpus NOT the reason (58.3% of 3521 train targets 6+ lines; model's 6-token output = 1.3rd percentile → training-budget/capacity symptom); round-2 lever = steps, same corpus shape; firelog/linter cross-reference bug pair found & fixed (10/10+10/10+13/13), fire 16 entry now archived; LOCKS 17→15; loopcheck floor 2 |
| fire 33: round-2 training pre-registration: convert fire-32 measured diagnosis into executable plan (steps/schedule/cost/criteria) for option C; audit sweep | DONE 2026-09-29 | plan = .claude/loop/round2-plan.md: extend mode (resume ckpt.pt), target 3,370 steps ≈ $5.22, cap 4,000/$7, primary bpb ≤ 0.55 + ≥25% multi-line on 20 held prompts, 5 stop rules (overfit 2-eval rise at 240 total epochs; plateau at step 2000 < 0.02 gain → "BRAM-sized model plateaus" verdict — tc is 77% BRAM, no upscale exists); new facts: round 1 = 23.98 epochs over the 7.37M-token train split, $1.72/1k steps; overwrite hazard caught pre-registration (resume rewrites run.json) → pull-before-extend §6; research.md option C retargeted off "bigger corpus" (fire 32 killed it); SKILL.md lesson + toolsrc refresh 1-new/3-same; loopcheck floor 2; no board/pods/RTL/money |
| fire 34: adversarial self-review of round2-plan.md: recompute every numeric claim from source arithmetic (train.py, manifest, cost anchors), re-check resume/smoke side effects in the control flow, sweep research.md for other stale claims; fix what fails | DONE 2026-09-29 | 3 defects found & fixed pre-execution: --tokens 1.77e9 floors to 3375 not 3370 (now exact 1766850560), "smoke = no checkpoint overwrite" was false (train.py checkpoints after the break; ckpt.pt advances 337→340, steps counted), stop-rule (b) re-anchored to the eval cadence (step 2022 = 6th eval, evals are multiples of 337); all other figures recomputed clean (epochs/warmup/decay/costs/balance); research.md sweep vs DONE verdicts: no further stale claims; amendment note added to the plan header; SKILL.md lesson + toolsrc refresh 1-new/3-same; loopcheck floor 2; no board/pods/RTL/money |
| fire 35: execute owner's triple pick (все три): A batched-wire RTL+cosim+reflash (aliasing resolution), B E3 board run + E4 minimal responder, C round-2 training per round2-plan.md §6 — long-running, IN-PROGRESS protects from cron re-fire | DONE 2026-09-29 | C ran end-to-end: §5a overfit fired (val_bpb 0.6105@337→0.8506@2696→0.7288@3370), primary ≤0.55 FAILED, pinned model stays ROUND-1 (pre-registered judge = loss); behavioral: r2 fixes degeneracy (r1 10% vs r2 45% non-degenerate ≥2-line) but loses on loss; round-3 lever = data quantity. A host-complete (spec repinned, cosim PASS, rehearsal PASS, synthesis clean, payload 48463217…, 9,730,792 B) — board leg needs batched board arm + owner sudo. B untouched (owner gate). Admissions: pod idle burn $2.29, ckpt_predecay overwritten (round-1 final.pt now sole copy, local), behavioral check blocked a day on env trivia (all recorded in SKILL.md). New tool tri fpga-genscore (degeneracy-aware scorer, tools 10→11, self-test 7/7, reproduces hand scores on the real evidence). Evidence kept tct27_r2_verdict + data/checkpoints/tern_tc_t27_r2; NO TC02 export of round-2 |

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
   aliasing / RTL guarded no-op / adjudicable-only cosim). As of fire 14
   option B's no-hardware half is ALSO done: E5 host half (`--udp` +
   UdpCellBridge, self-tested on loopback) built ahead of E4; what remains
   on B is E3's board run (pre-registered 19:36Z, needs «да» + sudo) and
   E4 (RTL — owner's pick of LiteEth/verilog-ethernet/minimal responder).
   Until then a fire
   is audit-only: `tri fpga-loopcheck` (fire 11 packaged the whole sweep —
   git + specs + keycheck + audit + one verdict line; exit 1 with exactly
   the two igla-coder-gpu anomalies is the known floor, anything beyond is
   new; NOTE fire 15: the 5 tc_infer.c-pin selftest refusals from fire 14 are
   RESOLVED — the fire-2 C_REF doctrine (pinned bytes on disk OR reachable in
   the file's git history) is now implemented in the wrappers' shared pins_ok
   too, not just the generators; the spec pins and C_GREEDY_IDS stay at the
   OLD engine's bytes on purpose, so no re-pin decision is pending unless the
   sibling's engine change turns semantic) — do not invent
   make-work; an audit-only fire is an honest fire.
   The only cheap extra if the owner stays asleep for many fires: re-check
   `.claude/loop/research.md` competitor movement (read-only, rare, last
   refreshed fire 26 — next due ~10 fires later, or sooner if a PENSA/TRACE
   follow-up lands).
3. Never commit or push igla-coder-gpu while its live session works (see DONE,
   fire 5 triage); document anything found there in this file instead.
4. End-of-fire report + three collaboration options; self-critique and anomaly
   scan; append fire log line.

## Standing rules (every fire)

- Never touch the 20 fleet pods (all EXITED; leave them).
- RunPod key `/tmp/rpk2.txt`: never print, only masked; values file→env inside
  one Bash call. Token stays.
- Board logs are committed only after `tri fpga-keycheck` passes (0 key hits).
- If audit prints "N pinned /tmp inputs gone, kept copies exist", the SAME
  fire runs `tri fpga-tmpcheck --restore` (idempotent; restores from kept
  blobs, never over a CHANGED file). A reboot must not outlive the next fire.
- LOCKS stays bounded: when it holds more than ~15 DONE rows, a fire may DROP
  the oldest DONE rows (never an IN-PROGRESS row, never a fire-log entry —
  dropping rows is always lint-safe; the log + DONE section + git carry the
  history).
- Fire log stays bounded (fire 25): after dropping LOCKS rows, a fire runs
  `tri fpga-firelog archive` — entries whose fires lost their rows move
  VERBATIM to `.claude/loop/firelog-archive.md` (never dropped; the linter
  counts a fire's entry in either home; the archive is written first, so a
  crash between the two writes duplicates entries, it never loses them).
- Tool-source durability (fire 31): board.py, SKILL.md, LESSONS.md and the
  `~/.local/bin/tri` wrapper have no committed copy anywhere (skills repo
  keeps them untracked by owner-precedent). Any fire that edits one of them
  re-copies all four over `/tmp/loop_toolsrc/` and re-runs
  `tri fpga-keep /tmp/loop_toolsrc toolsrc` (sha-deduped; secret-scan the
  key prefix file→env before keeping).
- English for all repo code/docs/commits; Russian only in chat.
- Self-check each fire: `git status` should contain only this cycle's files;
  `tri fpga-specs` after any spec edit; if something is broken, fix the root
  cause (never skip tests, never delete past evidence).
- End of every fire: append a short line to `## Fire log` below.
- Fire protocol (fire 18, now enforced by `tri fpga-loopstate`): the lock row
  AND a fire-log stub are written together at fire START (the file must be
  consistent at every instant — the linter caught the old row-at-start/
  log-at-end window); the stub becomes the full entry at fire end; the row
  flips to DONE in the same edit.

## Fire log

Archived entries (fires without a LOCKS row): .claude/loop/firelog-archive.md

- fire 17 (2026-09-29): the tool layer got the sweep its own self-critique
  asked for, and the sweep's first live run earned its keep immediately.
  `tri fpga-tools` (board.py TOOL_SELFTESTS registry + run_tool_selftests +
  cmd_tools + tools_self_test 9/9: dispatch-drift checks, recursion/layering
  exclusions, aggregation unit test) runs every board-tool's own --self-test
  — runlog, budget, tmpcheck, decode, repin, pins — in one call with one
  verdict line; `tri fpga-loopcheck` now runs it as its FOURTH component
  (specs, keycheck, tools, audit), so every fire re-verifies the whole tool
  layer after any edit instead of only the tool that changed. First live
  run: 5/6 — FAIL decode. Root cause NOT decode: its self-test had hardcoded
  the fire-2 sha `648451ff…` of the reopen spec as a "live" cite; the
  fire-14/15 repin cascades moved the spec's bytes and the cite went stale,
  so decode_spec correctly resolved through GENERATE_SPEC_FILE and named the
  drift, while the test demanded "not drifted". Fix: the hermetic cite now
  computes the live sha at test time (repin-proof), and the stale fire-2 sha
  stays as a NEW fixture asserting exactly the live behavior it exposed —
  a once-real stale sha still resolves and is named "drifted since the run"
  (decode self-test 17→18). Lesson pinned in SKILL.md: a self-test citing a
  live file must compute the sha at test time, never hardcode it —
  hardcoded live state rots at the next cascade. Also fixed the sweep's own
  first-run interleaving (headers must flush before the subprocess writes).
  Competitor re-check deliberately skipped: fire 16 refreshed the table
  hours ago; a same-day re-sweep is noise, and loop-state's own rule says
  rare. Gates: specs 17/17, keycheck 0 hits, tools 6/6, loopcheck floor =
  exactly the two known igla anomalies (ahead 18→19, sibling still working).
  Board, pods, RTL untouched.

- fire 18 (2026-09-29): the coordination file got its own guard, and the guard
  paid for itself before it was even finished. `tri fpga-loopstate` (board.py
  lint_loopstate + cmd_loopstate + loopstate_self_test 9/9) lints
  .claude/loop-state.md — the file every fire reads first — structurally, read
  only, never a status opinion: required sections, the UART lock paragraph,
  exactly one IN-PROGRESS lock with a started date (abandoned = older than a
  day), every table fire present in the fire log, no unknown statuses. Its
  first live run (mid-fire, 8/9 self-test) caught the LOOP's own protocol gap:
  my lock row was written at fire start but the fire-log line only at fire
  end, so mid-fire the table named a fire the log didn't — the exact window a
  future cron cycle could misread. Protocol fixed in the same edit: lock row
  AND fire-log stub written together at fire start (recorded in Standing
  rules); the linter stays strict because the file is now consistent at every
  instant. `tri fpga-loopcheck` gained it as the FIFTH component (specs,
  keycheck, tools, loopstate, audit). The self-test ends by linting the live
  file — a linter that fails the file it protects would be worse than none.
  SKILL.md notes both the command and the protocol rule. Gates: specs 17/17,
  keycheck 0 hits, tools 6/6, loopstate 9/9 + live sound, loopcheck floor =
  the two known igla anomalies. Board, pods, RTL untouched.

- fire 19 (2026-09-29): an honest audit-only fire, plus the one open question
  READY named, closed with a definitive read-only answer. The question: fire
  15 left "no re-pin decision is pending unless the sibling's engine change
  turns semantic" — fire 19 checked. `git log 52be443..HEAD -- c_infer/tc_infer.c`
  is EMPTY and the diff is empty: the reference engine is byte-identical to
  the state the C_REF doctrine already covers (on-disk = 52be443's bytes,
  sha256 cfd640a6…; the pinned OLD-engine bytes stay reachable at 52be443^).
  The sibling's 8 new commits are tc_fast (a separate C bench harness:
  --prompt-ids/--samples, pool spin budget revert) and research scripts
  (t27_bench with per-worker spec-tree copies, t27_repair_ids /
  resample-with-feedback — both self-flagged negative results in their
  commit messages). None touches the reference inference path, so
  C_GREEDY_IDS semantics hold and no re-pin decision pends. Gates: loopcheck
  five components green to the known floor — specs 17/17, keycheck 0 hits,
  tools 6/6, loopstate sound (live file), audit rc=2 = exactly the two igla
  anomalies (LEDGER.md uncommitted; ahead 19, behind 0 — sibling still
  working; 3 pre-wrapper info lines are informational, not anomalies). No
  new tool this fire on purpose: pins/tools/loopstate closed the genuine
  host-side tooling queue over fires 16–18; a sixth component now would be
  make-work, which READY forbids. Competitor re-check skipped (fire 16
  refreshed it, rule says rare). Board, pods, RTL untouched.

- fire 20 (2026-09-29): started — weak-spot scan flagged ephemeral pin targets:
  commit de8ceec7d keeps E3 model inputs pinned in /tmp, and /tmp does not
  survive a reboot; checking whether the specs gate would notice a missing
  pinned file loudly or pass silently. Stub written with the lock row.
  Full entry — the ephemeral-pin question closed empirically, layer by layer,
  with one self-caught error on the way. (1) `specs --check` with the pinned
  SDF hidden: rc=0 — by DESIGN, not a hole: the generator verifies REPO pins
  in both modes (semanticProblems, missing = PROBLEM) and the comment at
  e3_rx_capture_from_spec.mjs:42 says the /tmp files are "the runner's to
  check". (2) tmpcheck with the SDF hidden: `GONE kept` row, and
  `tri fpga-tmpcheck --restore` put it back from the kept blob — live-proven,
  restored sha == pinned sha b429acfb. (3) audit with the SDF hidden: my
  first test grepped only "lost|ANOMALY|e3z" and I claimed audit missed it —
  WRONG, the line says "gone"; the full-output retest shows
  `info 1 pinned /tmp inputs gone, kept copies exist (audit --heal restores)`.
  Lesson pinned in SKILL.md: a negative claim needs the full output, not a
  filtered one. (4) The one genuine gap was protocol: after a reboot the six
  inputs sit GONE-but-kept, audit reports info, loopcheck stays at the known
  floor — and until fire 20 nothing OBLIGED a fire to restore them. New
  standing rule below. No tool changed — every tool already did the right
  thing; the fix is a rule, not code. Gates after restore: specs 17/17,
  keycheck 0, tools 6/6, loopstate sound, loopcheck floor = the two igla
  anomalies (ahead 19→20, sibling still working). Board, pods, RTL untouched.

- fire 21 (2026-09-29): started — the last discipline-dependence in the loop's
  coordination is the fire-START protocol itself (row + stub written together,
  by hand every fire); building `tri fpga-fire start` to make it atomic and
  mechanical: build the new text in memory, lint it, only then write. Stub
  written with the lock row (by hand — the tool being built is this step).
  Full entry — `tri fpga-fire start "<desc>"` shipped. The row+stub edit that
  fires 18–21 did by hand is now ONE command: next fire number from the log's
  max, row after the last LOCKS row, stub at the log's end, the new text
  LINTED before it replaces the file (a bug can refuse, never corrupt).
  Refusals: a fire already IN-PROGRESS, a base file that does not lint, an
  empty LOCKS table. Refactor alongside: the linter's row parsing moved into
  a shared lock_rows() so linter and fire-start can never disagree about what
  a row is (loopstate self-test 9/9 still, including the live check). Fire's
  own self-test is 6/6, hermetic in a temp dir on purpose — this tool WRITES,
  so its self-test must never touch the live file (the tmpcheck/fire-17
  hermeticity lesson, applied at design time this once). Live verification:
  the refusal path ran against fire 21's own lock (rc=1, file byte-identical,
  loopstate sound); the happy path's first live run is fire 22. TOOL_SELFTESTS
  6→7, `tri fpga-tools` 7/7, tri wrapper dispatch + help updated. Self-caught
  before first run: lines.index("**UART lock:**") required exact line
  equality while the live file has the marker starting a longer line — would
  have ValueError'd on the very first real start; now a substring scan.
  Gates: specs 17/17, keycheck 0, tools 7/7, loopstate sound, loopcheck
  floor = the two igla anomalies. Board, pods, RTL untouched.

- fire 22 (2026-09-29): started — audit sweep + first live fire-start (happy path of the fire-21 tool). Stub written with the lock row by tri fpga-fire start; expand to the full entry at fire end.
  Full entry — the fire-21 tool's first live start, clean: row landed after
  the last LOCKS row, stub at the fire-log tail, both from ONE write, and the
  linter said sound before the command even returned. The fire-18 protocol is
  now mechanical end to end (start by tool, end by hand — the end is prose).
  Second item, from the mandate's own words ("чтобы новый цикл крона не ломал
  прошлую работу"): the loop's last single point of failure was the SESSION —
  job 25699f12 is session-only, and if this session dies the loop dies
  silently. The header now carries a resume paragraph: a fresh session
  restarts with /loop 15m and the same mandate, then continues from this file
  (LOCKS → tri fpga-fire start → Standing rules); all past work lives in
  LOCKS/DONE rows and committed history, so a new job id changes only who
  fires next. No tool added this fire — the two candidates (fire end command,
  cron liveness check) were judged make-work: the end-flip is prose, and the
  session's own /tasks + this file already answer liveness. Gates: specs
  17/17, keycheck 0, tools 7/7, loopstate sound, audit rc=2 = exactly the two
  igla anomalies (LEDGER.md; ahead 20), no gone-inputs line (fire 20's rule
  had nothing to do). Board, pods, RTL untouched.

- fire 23 (2026-09-29): started — E4 stack decision table for the owner's pick + LOCKS compaction rule. Stub written with the lock row by tri fpga-fire start; expand to the full entry at fire end.
  Full entry — two items. (1) The owner's E4 pick is now a 10-second
  decision instead of a research task: NODE_ETHERNET_PLAN.md's Prior-art
  section gained a decision table assembling ONLY facts the plan had already
  verified (both vendored stacks are IDDR-based and so must have their PHY
  capture replaced by E3's fabric capture regardless; verilog-ethernet is
  MIT, last push 2025-02-27, not archived; LiteEth pulls LiteX whose
  default toolchain here is Vivado) plus the loop's recommendation: minimal
  responder — zero license surface, reuses E3 RTL already modeled PASS
  (10.9 ns RX margin), sized exactly to the two frame types the receipt
  path needs; vendored stacks pay off only if the node ever needs a real
  network stack. No new facts were asserted — the table cites what the plan
  checked itself. (2) LOCKS-bounded standing rule: past ~15 DONE rows a fire
  may drop the oldest (never an IN-PROGRESS row, never a fire-log entry;
  dropping rows is lint-safe by construction — the linter only demands
  rows→log, not log→rows). Mid-fire audit showed a THIRD anomaly — this
  fire's own uncommitted plan edit; exactly the designed behavior (record
  files belong in commits), cleared by this commit. Sibling ahead 20→21.
  Gates: specs 17/17, keycheck 0, tools 7/7, loopstate sound, floor 2 after
  commit. Board, pods, RTL untouched.

- fire 24 (2026-09-29): phantom-frame decision table for option A + corpus
  round-2 cost memo for option C. Both options in research.md's list are now
  pick-ready, mirroring fire 23's E4 table.

  The table went into TERN_TC_BATCH_RTL_PLAN.md right after Risks, under
  "Phantom-frame decision table (fire 24 — assembling already-checked facts,
  one pick)". Five rows compare the three Risks end-states: what changes
  (spec edit vs RTL guard vs nothing), cosim coverage under loss (all streams
  adjudicable for 1 and 2 vs adjudicable-only for 3), cost, the pre-walk's
  role (invariant check vs filter), and board semantics (aliased write vs
  silent drop vs never exercised). Recommendation = 1: the aliasing decision
  is already made on the RTL side, so option 1 is the one edit that makes the
  model agree with the plan's own choice at zero gates; option 2 pays a guard
  for the same coverage and buries a silent-drop semantic; option 3 is a
  holding position that never exercises the loss streams the finding is
  about. Every cell restates a fact the plan had already established — no new
  claims.

  The cost memo went into research.md option C: round 1 was 337 steps, val
  bpb 0.756 → 0.611, $0.58 spent, $74.68 balance at close; the remaining gap
  to < 0.5 is roughly the whole round-1 gain again, so round 2 costs dollars,
  not tens of dollars, and the binding constraint is corpus quality for
  multi-line output, not money. Corpus copies noted (/workspace/ft_t27_8k pod
  + /tmp/ft_t27_8k local).

  Gates: audit re-checked with the tool's FULL output this time (the fire-20
  filtered-grep lesson, applied unprompted) — exactly the 2 igla floor
  anomalies (LEDGER.md; ahead 22, sibling still alive), no third from this
  fire's own edits; specs 17/17, keycheck 0, tools 7/7, loopstate sound.
  Board, pods, RTL untouched.

- fire 25 (2026-09-29): fire-log rotation — the other half of the fire-23
  compaction rule. Weak spot found by looking at the loop's own growth: at
  15-minute cadence the file gains ~96 entries/day, the fire-23 rule caps ROWS
  but "never drop an entry" made the log itself unbounded. Rows are the index;
  entries now stay in loop-state.md exactly while their fire is indexed.

  Shipped: (1) `lint_loopstate(text, now, archive_text="")` — a fire's log
  line counts from either home; cmd_loopstate and both fire-start lints read
  `.claude/loop/firelog-archive.md` when present; without an archive the
  linter behaves exactly as before (back-compat self-tested). (2)
  `tri fpga-firelog archive` — moves de-indexed entries verbatim, adds the
  pointer line under the Fire log heading once, refuses a non-last Fire log
  section (would rebuild around trailing content it cannot place), refuses a
  non-linting base, lints the rotated pair before writing, and writes the
  ARCHIVE first: a crash between the two writes duplicates entries, it never
  loses them. (3) fire-start numbering now looks in both homes — self-test
  case: live max 4 with archived 5 must yield 6, never a duplicate 5; this
  collision was found while designing the test, not in the wild.

  Live run: 13 entries moved (fires 2–14; fire 1 never had one — numbering
  began at the T35 rows), loop-state.md 678 → 551 lines, archive 148 lines
  with a three-line header, file lints sound with the archive.

  Self-test honesty: firelog 9/9, but the first run was 8/9 — the failing
  check was a test-hygiene bug (two synthetic states sharing one temp loop/
  dir, so "archive not created" was false for the second state), not a code
  bug; each state now gets its own dir. Also caught pre-flight: atomic_write
  needs the archive's parent to exist (temp dirs don't have .claude/loop/);
  the archiver mkdirs it. tools sweep 7→8 all green, tools meta 11/11,
  loopstate 9/9, fire 6/6, specs 17/17, keycheck 0; audit at floor 2 (igla
  LEDGER.md; ahead 25 — sibling very alive). Standing rules gained the
  rotation rule. Board, pods, RTL untouched.

- fire 26 (2026-09-29): competitor re-check — the READY section's own
  sanctioned work for a long-asleep owner (rare cadence: last fire 16).

  Two table additions. (1) PENSA (NeurIPS 2026, Sydney, TernaryNet collab):
  full BitNet b1.58 2B4T inference on an HBM-equipped Alveo U50, two
  row-partitioned ternary engines over eight HBM pseudo-channels, 58.09
  tok/s @ctx 128 / 24.60 @ctx 2048 = 2.14–3.14× a Xeon baseline — the
  throughput tier gains a datacenter-class entry; no verifiability story.
  (2) TRACE (Linux Foundation/CoSAI, Aug 2026, from OPAQUE with
  AMD/Intel/Microsoft/TII): open AI runtime-attestation spec whose
  "Trust Records" are called tamper-proof receipts — 135k PyPI downloads
  in ten weeks. Root of trust is CPU confidential computing (SEV/TDX);
  it attests workloads (environment, software, policies), not per-job
  math, and not accelerator silicon. Complement, not rival — but the
  word "receipt" now has a standard body behind a DIFFERENT meaning, so
  the wedge scoping was sharpened from "on-hardware receipts" to
  "on-silicon per-job receipts" (research.md).

  Unchanged: ternfpga frozen at 72 commits since fire 16 (energy still
  Vivado-derived, still no receipts); Ternarycore active into Jul 2026
  (timing fixes, a hardware verification run) but all verification is
  RTL correctness vs golden models. The wedge holds: nobody in the
  accelerator tier publishes cryptographic accountability for the math
  the silicon performs.

  Method note: two web searches found the new entries; four fetches
  pinned what each actually claims (PENSA numbers, ternfpga repo state,
  Ternarycore repo state, TRACE's root of trust) before anything went
  into the table — no entry added on search-snippet evidence alone.
  READY's re-check cadence reset to fire 26. Gates at floor 2 (igla
  LEDGER.md, ahead 26). Board, pods, RTL untouched.

- fire 27 (2026-09-29): the audit reported a THIRD anomaly at 00:47:53Z —
  "stamp check is blind: a stamp 15 min after its commit was not reported" —
  and the loop self-healed its own instrument. Root cause, proven empirically
  BEFORE any edit (a synthetic probe script, no guessing): the audit's
  calibration probe built "probe HH:MM UTC" from now-3600/+900; run inside
  the [00:45, 01:00) UTC window the stamp rolls over midnight and
  future_stamps' replace() then lands it EARLIER on the commit's own date —
  the probe tested nothing and the audit reported a blindness it had caused
  itself. Window edges 00:45:00/00:59:59 blind, 01:00:00 and 14:00 controls
  flag — exactly the predicted 15-minute daily window, and the live audit ran
  inside it. Fix: stamp_probe(now_epoch) steps the synthetic commit back
  hour-by-hour until stamp and commit share a UTC date, keeping the probe
  inside the check's documented same-date scope at EVERY instant; cmd_audit
  now uses it. New tool tri fpga-stamps — the stamp check alone (claim-doc
  sweep + calibration), self-test 9/9 hermetic: scope semantics (future
  flagged, past/slack clean, other-date and impossible clocks skipped) plus
  the fire-27 regression at the caught instant and both window edges; tools
  sweep 8→9 all green, dispatch + tri wrapper updated. Live proof: the
  post-fix audit ran 00:57:26Z, still inside the old blind window, and the
  third anomaly is gone — floor back to exactly 2 igla anomalies (LEDGER.md,
  ahead 26); loopcheck specs 17/17, keycheck 0, tools 9/9, loopstate sound.
  Second finding, documented not invented: /tmp/ft_t27_8k (16M, alive) has
  NO builder anywhere in this repo — round 2 of option C inherits its corpus
  only while /tmp and the STOPPED pod's volume both survive; recorded in
  research.md option C with the tmpcheck-style keep as the fix direction.
  Board, pods, RTL untouched. /tmp/probe_check.py was the evidence script.

- fire 28 (2026-09-29): fire 27's second finding made mechanical. The
  round-1 corpus /tmp/ft_t27_8k (92 files, 16M) had no builder in the repo
  and lived only in /tmp (dies at reboot) and on the STOPPED pod (dies with
  the pod). New tool tri fpga-keep PATH TAG: every file under a /tmp tree
  becomes a blobs/<sha256> entry (gitignored) plus a MANIFEST.tsv row
  (tracked), pins tagged keep:TAG — reusing tmpcheck's substrate on purpose,
  because once a path is in the manifest tmp_report already watches it and
  --restore already rebuilds it, so an explicitly kept tree inherits the
  whole durability machinery a spec-pinned file has, with zero new watcher
  code. Self-test 9/9 hermetic (nested tree, duplicate content deduped to
  one blob, idempotent second run, pre-existing spec-pinned row untouched,
  tmpcheck sees the rows, rmtree → GONE-but-kept → restored with original
  bytes, outside-/tmp and bad-TAG refusals). The first run of the self-test
  was 8/9 and the failure was INSTRUCTIVE, not cosmetic: the outside-/tmp
  refusal test built its "outside" tree under tempfile, but this host runs
  TMPDIR=/tmp, so the guard rightly passed and the file was kept — a
  hermetic test must not lean on host env (fire 25's lesson, now caught a
  second way); the check is now a string-level refusal plus a
  nothing-was-written assertion. Live run: tri fpga-keep /tmp/ft_t27_8k
  ft_t27_8k kept 92/92; tmpcheck reports 98 pinned /tmp files, 0 lost,
  0 not kept; after any reboot the audit's gone-line + standing rule
  (tmpcheck --restore) rebuilds the corpus. tools sweep 9→10 all green;
  loopcheck at floor 2 (specs 17/17, keycheck 0, loopstate sound). The pod
  volume remains the only other copy — noted in research.md option C.
  MANIFEST.tsv (tracked) committed; blobs gitignored. Board, pods, RTL
  untouched.

- fire 29 (2026-09-29): corpus builder derivability — RESOLVED, the corpus is
  rebuildable. Audit at open: floor 2 (igla LEDGER.md, igla ahead 27).
  Chain found by reading the sibling read-only: `t27_bench.py items`
  (t27 checkout + pool + t27c → bench/items.jsonl) → `t27_bench.py fim`
  (items + tokenizer → ft_t27 corpus). cmd_fim has NO randomness (the only
  torch.manual_seed is in gen), so byte-identity is purely a function of the
  inputs: the t27 tree walked, items.jsonl, tokenizer.json, defaults --ctx
  2048 --max_body 4000. The unrecorded input was the tree: pinned by the
  manifest's own fingerprint — held_specs_missing_from_checkout (44 of 130)
  narrows ~/t27 history to TWO specs/ subtree shas (84dd59d4, dfdbec0c;
  /tmp/pin_tree.py, kept keep:fire29) — and an exact token-count match picks
  dfdbec0c = commit 9fec01a78 = current HEAD, specs/ working tree clean
  (candidate A: train 7,360,119 ≠ manifest 7,368,311; candidate B: exact).
  Rebuild proven: 91/92 kept rows byte-identical (train/val t27.bin,
  token_bytes.npy, tokenizer.json, items.jsonl, all 86 held-spec copies);
  the lone exception is manifest.json itself — the builder version that
  emitted held_specs_present/missing + note is not the current sibling file
  (it writes stats instead) and survives only on the stopped pod; its
  train_tokens/val_tokens/held_out_specs reproduce exactly, so the drift is
  bookkeeping, not content. Tool: `tri fpga-derive ft_t27_8k [--out DIR]` —
  git-archive extract of the pin (checkout untouched), sibling scripts
  copied with a loud refusal if the patched shape drifted, pyarrow stub
  (host lacks it; fim never needs it), items/tokenizer pulled from the keep
  BLOBS (a dead /tmp is not a blocker), then every row sha-checked (rc=0
  live, "92/92 rows verified"). Two self-caught bugs on the way: .git
  is_file() vs exists(); and the destructive-out guard first compared
  resolve()d against literal /tmp (macOS symlink → /private/tmp), never
  fired, and the guard TEST itself rebuilt into the live kept tree —
  survived because blobs existed, manifest.json restored from its blob,
  tmpcheck back to 98 pinned / 0 lost; guard now compares resolve() on both
  sides, refusal rc=2 verified honestly (after a pipeline rc misread —
  fires 20/24/27/28 lesson, again). research.md option C durability
  paragraph rewritten: three independent lives (/tmp, blobs, verified
  chain), the pod volume no longer matters. Evidence kept: pin_tree.py +
  verify92.py (keep:fire29). Gates: tools 10/10, specs 17/17, keycheck 0,
  loopstate sound, loopcheck floor 2 (igla LEDGER.md, ahead 30 — the
  sibling keeps committing; MANIFEST.tsv anomaly is this fire's own rows,
  gone with the commit). Board, pods, RTL untouched; no money spent.

- fire 30 (2026-09-29) — LOCKS compaction + audit-only sweep. READY said audit-only (A and B
  wait on the owner's picks; C needs pod money), and the file's own LOCKS-bounded rule
  came due: 18 DONE rows, 3 past the ~15 bound. Dropped the three oldest — the T35
  phase rows (spec authoring, rehearsal pair, board run). Nothing was lost: their
  facts live in the DONE section bullets ("T35 board run COMPLETE" block) and in git
  history; the rows were pointers, not the record. `tri fpga-firelog archive` was a
  correct no-op — every fire-log entry's fire still has a LOCKS row (fires 2–3 entries
  were already moved at fire 25; the three rows dropped this fire never had log
  entries of their own). Lint sound after the drop; 17 table lines = header + 15 DONE
  (fires 15–29) + this row. Audit sweep at the known floor: exactly the 2 igla
  anomalies (LEDGER.md uncommitted; ahead 30), tools 10/10, specs ok, keycheck 0,
  loopstate sound — no new anomalies, no drift. Competitor re-check not due (last
  fire 26, next ~36). Host-side only; no board/pods/RTL; no money. Self-check: the
  compaction rule's "never log entries" half held automatically because the archive
  runs idempotently and reported its no-op honestly rather than moving anything —
  the fire-25 design did its job with zero intervention.

- fire 31 (2026-09-29) — tool-source durability. The weak spot was found by
  auditing WHICH assets have zero committed copies, not which are volatile
  (the fire-28/29 lens applied to the loop itself): `scripts/board.py` (10
  tools, fires 3–29), SKILL.md, LESSONS.md and the `~/.local/bin/tri` wrapper
  lived only as untracked files — `git -C ~/skills status` shows the whole
  `ax7203-board-loop/` dir as `??` and `git log -- board.py` is EMPTY, so a
  routine `git clean` in the owner's dirty skills repo (where committing
  around his changes is off-limits by precedent) would have erased 27 fires
  of tooling with no copy anywhere. Fix, zero new code: flat snapshot dir
  `/tmp/loop_toolsrc/` (board.py, SKILL.md, LESSONS.md, tri) through the
  ordinary `tri fpga-keep … toolsrc` — the blob store lives under
  trinity-fpga/artifacts, a different tree than ~/skills, so no git
  operation there can touch it; tmpcheck went 98→104 pinned / 0 lost /
  0 not kept and --restore rebuilds the dir after any wipe. Secret-scan
  before keeping (RunPod key prefix, file→env in one call, never printed):
  CLEAN. The refresh protocol is proven, not assumed: after the SKILL.md
  lesson was written, the re-copy + re-keep printed "1 newly kept, 3
  already kept" — sha-dedup makes unchanged files no-ops exactly as
  designed. Standing rule added (any tool-layer edit re-snapshots) and the
  lesson recorded in SKILL.md (which is itself inside the snapshot —
  self-consistent). NOT snapshotted, on purpose: `_state/` (runtime UART
  observations, not source) and `/tmp/rpk2.txt` (a secret; copying it would
  expand its exposure surface — if a reboot clears /tmp the key is the
  owner's to restore, noted in the report). Gates: loopcheck specs 17/17,
  keycheck 0, tools 10/10, loopstate sound, audit at open and close =
  exactly the 2 igla anomalies (LEDGER.md; ahead 31, sibling alive).
  Host-side only; no board/pods/RTL; no money.

- fire 32 (2026-09-29) — corpus diagnosis + a tool bug pair the compaction
  flushed out. (1) The weak-point-3 question — "why does the model emit one
  line" — answered by MEASUREMENT, not opinion: /tmp/fimdiag.py imports the
  sibling's t27_bench read-only (its own functions/is_stub/norm — zero
  transcription risk), git-archive-extracts the pinned tree 9fec01a78
  (checkout untouched), and replicates cmd_fim's walk exactly (held set,
  /scratch/ skip, md5%20 split, bad-line drop, is_stub/4000-char/room
  filters). Verdict over 3,521 train FIM targets: 2.8 % newline-free bodies,
  25.4 % single-statement style, **58.3 % six-plus lines**; median target 48
  tokens / 157 chars; the model's actual 6-token output is the **1.3rd
  percentile** of target length. The corpus TAUGHT multi-line — the collapse
  to the shortest well-formed body is a training-budget (337 steps) /
  capacity symptom. research.md weak point 3 and option C's memo corrected:
  round 2's lever is steps and schedule on the SAME corpus shape, not corpus
  reshaping. Evidence kept (fimdiag.py + results, keep:fire32). (2) LOCKS
  compaction 17→15 (fires 15–16 rows dropped) exposed a REAL bug pair in the
  rotation machinery: the archiver indexed fires by findall over the whole
  phase cell, so fire 26's phase "last fire 16, now 26" falsely kept fire 16
  "indexed" — and the linter had the mirror bug (a cross-reference demanded
  that fire's entry), so the two errors cancelled and lint stayed green.
  Fixed both to parse only the row's OWN leading "fire N"; regression cases
  in both self-tests (loopstate 10/10, firelog 10/10, tools sweep 13/13);
  live proof: the re-run archived fire 16's entry (738→711 lines) and the
  fixed linter says sound. (3) Tool snapshot refreshed per the fire-31 rule
  (board.py changed; secret-scanned; 1 new / 3 same). Gates: audit at open
  and close = floor 2 (igla LEDGER.md; ahead 31). Host-side only; no
  board/pods/RTL; no money.

- fire 33 (2026-09-29): round-2 fine-tune pre-registration (option C's
  executable form) + audit sweep. The plan (.claude/loop/round2-plan.md)
  is written BEFORE any pod starts; nothing was run. Facts gathered
  read-only from the sibling repo (train.py/model.py/HANDOFF.md, never
  edited): train.py --tokens → steps (× 524,288), resume = full state
  (model+opt+data+step) from ckpt.pt, --init = weights with a fresh
  schedule, auto final eval, run.json records everything; model size tc
  = 6.46 M ternary weights = 77 % of XC7A200T BRAM → every larger size
  breaks the board story, so a capacity plateau is a verdict, not a
  pivot; corpus manifest (fire-28 keep): train 7,368,311 tokens → round
  1's 176.68 M tokens = 23.98 epochs — "more steps" means deeper epochs,
  which makes the val-based stop rule load-bearing, not ornamental.
  Plan shape: extend the round-1 run (resume ckpt.pt on volume
  igla-coder-data), target 3,370 total steps ($5.22 new at the measured
  $1.72/1k), hard cap 4,000 steps/$7; primary success final val_bpb_mix
  ≤ 0.55, stretch < 0.50, behavioral ≥ 25 % two-line bodies on 20 held
  prompts; five stop rules (overfit = val rise 2 evals in a row; plateau
  at step 2,000 with < 0.02 gain over 0.611; budget; restart spike > 2×
  end-loss; pod fault). One loss class caught while writing the plan:
  resume REWRITES run.json and a finished round 2 replaces final.pt —
  the round-1 records exist only on the working volume, so plan §6 step
  3 pulls them BEFORE the resume smoke (SKILL.md lesson added; toolsrc
  snapshot refreshed 1-new/3-same per the fire-31 rule, secret-scanned).
  research.md option C retargeted: was "bigger corpus", now "more steps,
  same corpus" per fire 32, with the plan pointer. Gates: audit at open
  and close = floor 2 (igla LEDGER.md; ahead 33); specs 17/17, keycheck
  0, tools 10/10. Host-side only; no board/pods/RTL; no money — the plan
  executes only on the owner's "C".

- fire 34 (2026-09-29): adversarial self-review of the fire-33 plan
  (.claude/loop/round2-plan.md) — the fire-33 self-critique promised it
  ("следующему файру — сверка"), executed before anything can execute the
  plan. Method: recompute every numeric claim from the source it cites
  (train.py's steps/warmup/decay/eval arithmetic, the corpus manifest,
  the $0.58/337-step cost anchor) and walk the code's exit paths, not
  just its body. THREE defects found, all fixed pre-execution with an
  amendment note in the plan header: (1) §6.5 `--tokens 1.77e9` floors
  to 3,375 steps, not the target 3,370 — now the exact integer
  1766850560 (= 3370 × 524288); (2) §6.4 claimed the smoke run does not
  overwrite the checkpoint — false, train.py calls checkpoint(ck)
  unconditionally AFTER the loop break, so ckpt.pt advances 337→340
  (three real steps, counted toward the total) and run.json is rewritten
  (already flagged in §2, now also in the smoke step); (3) stop rule (b)
  was anchored at "step 2,000", which sits between evals — re-anchored
  to the 6th eval (step 2,022; evals are multiples of 337). Every other
  figure recomputed CLEAN: 176.685 M tokens = 23.98 epochs, warmup 100 /
  decay from 2,696 at 3,370 steps, budget table rows (883 M/120,
  1.767 B/240, 2.097 B/285 epochs), costs $2.32/$5.22/$6.30, balance
  floor $67.68. research.md swept claim-by-claim against the DONE
  records (wire shares, jobs, E3 holds, $74.68, 235 s vs 1414.5 s): no
  further stale claims — option C's header (fixed fire 33) was the only
  one. SKILL.md lesson added (recompute-from-source pass between writing
  "execute exactly this" and execution; exit paths are where side
  effects hide; the author is the worst reviewer of their own
  arithmetic); toolsrc snapshot refreshed per the fire-31 rule
  (1-new/3-same, secret-scanned). No new tri command — the pass was
  reading and arithmetic, not machinery; forcing a tool would be
  make-work. Gates: audit floor 2 (igla LEDGER.md; ahead 33); specs
  17/17, keycheck 0, tools 10/10. Host-side only; no board/pods/RTL; no
  money.

- fire 35 (2026-09-29): execute owner's triple pick (все три) — A batched-wire
  host leg, B E3 board run (owner-gated), C round-2 training. C ran end-to-end;
  A is host-complete awaiting the owner-sudo reflash; B untouched (owner's sudo
  `e3_flash` never run). Verdicts first, admissions under them.

  C — round-2 training (the pre-registered plan's own judge = loss): pod
  9kt3lwrgxjbrz5 ran the extend-resume per §6: inputs sha-verified against the
  fire-28 keep, round-1 records pulled BEFORE any training write, smoke
  "resumed from step 337" then ckpt.pt advanced 337→340 exactly as the fire-34
  correction predicted, full run --tokens 220856320 (correction 2's arithmetic,
  NOT the plan's original 1.77e9). Stop rule §5a OVERFIT fired: val_bpb
  0.6105@337 → 0.8506@2696 → 0.7288@3370 — two consecutive eval rises; §4
  primary ≤0.55 FAILED. Pinned model stays ROUND-1 (pre-registered judge =
  loss; re-pinning round-2 on the better behavioral score would be post-hoc
  metric chasing). Round-3 lever recorded: data quantity, not steps (§7 wall).

  C — behavioral §4 (the part round 2 was FOR): greedy FIM on 20 held prompts,
  val20 filtered to the 86 specs present at build time and parseable under the
  current bench (one drifted item excluded, qmtech_a100t_integration::on_comb).
  Literal criterion ≥2-line bodies: r1 8/20 (40%), r2 9/20 (45%) — both pass
  the ≥25% letter. Degeneracy filter (unique stripped lines ≥ max(2, len//2)):
  r1 = 2/20 (10%) FAIL — 6 of its 8 multi-line outputs are repetition loops
  (44 lines / 11 unique, `zig_lines = 0` looping in a CompileResult);
  r2 = 9/20 (45%) PASS, zero degenerate. Round-2 DID fix the one-line
  degeneracy fire 32 diagnosed — but under the pre-registered loss-judge it
  still loses. Lesson: generative pre-registrations need a degeneracy clause;
  the scorer is now `tri fpga-genscore` (below) so no future fire can cite the
  literal count alone.

  A — batched wire protocol, host side COMPLETE: spec pin re-pinned + verified
  (trinet_node_core.v sha fc22d2c1…), cosim PASS re-run (7,695 B model==RTL
  byte-identical; negative control differs), rehearsal self-test PASS,
  from_spec regen + --check PASS (74 consts / 10 tests / 80 asserts / 0
  failures, verdict "same"), openXC7 synthesis clean first pass — payload sha
  48463217d7580535d9f1acd5ccc91145e31040ad3b9e2868814322ac11d791d8, 9,730,792
  B, at /tmp/trinet-node-build/node0-batched/trinet_node0.bit. Board leg NOT
  done: it needs (1) the batched board arm WRITTEN — run_pass over
  ro.serial_link with its own pre-registration, the spec's "WHAT IT DOES NOT
  SAY" demands it, NO board mode exists in the runner yet — and (2) the
  owner's sudo for the reflash. Remains the top option for the next fire.

  B — E3 + E4: nothing run. The owner's one-line `tri fpga-flash e3_flash
  artifacts/bitstreams/e3_eth_arp_icmp_zinv_t1.bit --owner-yes "все три"
  --expect 4fd7923d` (he types the sudo password) is still the gate; E4
  minimal responder design notes live in research.md.

  Admissions (self-critique, the loop mandate's own ask): (1) pod idle burn
  ≈ 3.1 h ≈ $2.29 — training compute ENDED 06:54Z but the pod ran to 09:59:58Z
  while the behavioral check was blocked on pip gaps and the classifier outage;
  the plan's §6 said stop the pod at the end, and "the end" arrived at 06:54,
  not 10:00. (2) ckpt_predecay.pt: round 1's pre-decay checkpoint on the pod
  volume was OVERWRITTEN by round 2 (the §2 hazard named run.json/final.pt but
  missed this file); round-1's final.pt survived and its local copy in
  data/checkpoints/tern_tc_t27_r1/ is now the ONLY copy of round-1 weights
  anywhere. (3) The behavioral check burned most of a day on environment
  trivia — pod image lacks tokenizers/pyarrow (PEP 668 →
  --break-system-packages), 44 of 130 held-out specs were missing from the
  build-time checkout (manifest's own held_specs_missing_from_checkout), and
  one item drifted past the current bench parser. None of this was training
  science; all of it is now recorded in SKILL.md so the next round does not
  re-learn it.

  Economics: pod 9kt3lwrgxjbrz5 05:28:22Z→09:59:58Z ≈ 4.53 h × $0.74 ≈ $3.35;
  true compute ≈ $0.15 of that (correction 2's anchor was right); balance
  ≈ $71.3 from $74.68. Round-2 artifacts: data/checkpoints/tern_tc_t27_r2/
  (final.pt 36,324,991 B, run.json, log.jsonl, summary.json); evidence kept
  under tag keep:tct27_r2_verdict (val20 + both cands + both scoring scripts,
  5 files). NO TC02 export of round-2 (the pinned model is round-1; exporting
  the loser would fork the board story).

  New tool (the per-fire CLI update the mandate asks for): `tri fpga-genscore
  CANDS.jsonl [--min-lines N --pass-frac F]` — the degeneracy-aware scorer,
  verdict rides the FILTERED count, exit 0 only if every file passes; hermetic
  self-test 7/7 (counts, filter, both verdict bars, missing-file refusal);
  tools sweep 10→11. On the real evidence it reproduces the hand scores: r1
  FAIL 10%, r2 PASS 45%.

  Process: row+stub via tri fpga-fire start; this close-out written after the
  last artifact was pulled; loopstate lint + keycheck before commit; commit
  docs(loop) + push. Classifier outage note: the fire's last hours ran against
  "claude-opus-4-8[1m] temporarily unavailable" flapping — probes passed,
  exec-shaped calls needed 10-minute waits; the close-out itself was staged
  through it (work staged in /tmp, retried, never dropped).

  Post-commit addendum (same fire, found by the close-out's own loopcheck):
  (1) the final sweep flagged 4 spec-drift anomalies — Lane A's RTL edit had
  been repinned into the batch spec only; the reopen/retransmit family still
  pinned the old shas. tri fpga-repin walked NODE_RTL=fc22d2c1… through all
  five specs to fixpoint (8 passes, params regenerated); the old op set
  regenerates byte-identical constants from the new core — the batch ops were
  added beside the old wire protocol, not under it. specs 17/17; second commit
  1dd2f747e also carries the E3 rehearsal logs the audit flagged (add -f past
  the *.log ignore, same as every other board_runs log). (2) claim-guard
  blocked the first commit: fire 34's portability-doc wording attributed the
  absence of multiplies to nothing in particular — the exact shape the owner's
  rule forbids (freedom from multiplication is a property of the ternary
  network and must be said of the network). Reworded to
  measured-report language ("synthesises without multiplier cells", "the check
  reports zero inferred multiplier cells") with the rule-quoting line marked
  ignore-line. Loopcheck at close: specs 17/17, keycheck 0, tools 11/11,
  loopstate sound, audit floor = 1 igla anomaly (ahead 1, sibling-owned).

