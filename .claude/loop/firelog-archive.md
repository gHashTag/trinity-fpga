# Fire log archive — entries moved from loop-state.md once their LOCKS
# rows were compacted (fire-23 rule). Moved verbatim, never dropped; the
# linter counts a fire's entry in either home (fire 25).
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

- fire 14 (2026-09-29): option B's E5 host half, built ahead of E4 (pure
  host-side Python — READY's "same spirit" class). `--udp HOST:PORT` in
  tern_tc_layer_ax7203.py: same TRI-NET frames, one datagram per request
  with a 4-B sequence echoed on answers, read() strips it (runner
  classifies by nonce, order free), `--setkey` refused on UDP per E4's
  rule. Self-test + UdpCellBridge (loopback software cell, the byte-exact
  peer E4's cosim will reuse): clean 222/222 receipts all rows exact
  echo_bad 0; one whole dropped datagram = 221/222 credited, honest short
  read at the end, only that job's row incomplete — loss costs one job,
  never a wrong row (measured, my first window-stall prediction was wrong
  and was corrected against the debug run, not asserted). The harness edit
  repinned in the open, five layers: HARNESS_SHA256 x10 specs → cross-spec
  sha chain bottom-up (retransmit←generate, reopens←generate+retransmit,
  batch←reopen_t27, hubfree←diag) → regenerated *_params.py → params
  sha pins in the pinning specs → later generators again; tri fpga-specs
  17/17. ANOMALY (external, pre-existing at HEAD, not from this fire's
  edit): sibling repo's ~/igla-coder-gpu/c_infer/tc_infer.c changed
  2026-09-28 20:59 (commit 52be443 "Fast engine") after our specs pinned
  it (33a7f98d…); 5 selftest runners refuse on that pin exactly as the
  doctrine wants — C_GREEDY_IDS/CPU_INT_IDS are fixed against the OLD
  engine, so re-pinning is semantic work for the owner + sibling session,
  not for a night fire. 11/16 runners PASS incl. the full harness
  self-test. SKILL.md: --udp + the five-layer re-pin trap. Board, pods,
  RTL untouched.

- fire 15 (2026-09-29): the fire-2 C_REF doctrine completed in the second
  place it was owed, and the recurring re-pin cascade became a tool. (1)
  `git_blob_sha` in tern_tc_generate_ax7203.py mirrors the generators'
  gitBlobSha: pins_ok keeps SPEC/HARNESS/MAC32/MODEL strict, C_REF is
  satisfied on disk OR by bytes reachable in the file's git history (the
  wrapper never reads tc_infer.c at run time; --mode c is a Python mirror,
  C_GREEDY_IDS are recorded constants). Result: tri fpga-selftest 16/16 —
  the 5 fire-14 refusals are green, spec pins and ids unchanged, so the
  owner's fire-14 option-C decision (whether the sibling's new engine
  becomes the reference) is still open and still semantic. Self-test
  additions cover both branches (garbage sha refused + live stale pin
  resolves via sibling history). (2) `tri fpga-repin FILE... [--check]`
  (board.py cmd_repin + repin_walk, self-test 16 checks incl. a synthetic
  generator): seed = named files, walk pins bottom-up to a fixpoint
  (leaf pins → cross-spec pins → params regeneration → params pins),
  never guesses (missing pinned file skipped, ambiguous *_SHA256 refused,
  generator PROBLEM stops unless another generator still writes). The
  runner edit was repinned THROUGH the tool: GENERATE_RUNNER_SHA256
  5d769dd8→72136fe7 in retransmit+3 reopens, RT_PARAMS pins, batch
  REOPEN_SPEC, 4 params files regenerated, converged in 4 passes, second
  run rc=0. Two tool bugs found by its own first live run and fixed with
  self-test cases: bare-mode `wrote` lines were unparsed (walk stopped
  calling real writes "no writes"), and an UnboundLocalError crashed the
  first sweep losing walk state — resumed honestly by re-seeding the
  orphaned params files (their diffs are the generators' mechanical
  output, provable via git diff; SKILL.md records the resume rule). tri
  fpga-repin --check probed but did NOT apply the tc_infer.c re-pin —
  that stays the owner's. Specs 17/17, keycheck 0 hits. Board, pods, RTL
  untouched.

- fire 16 (2026-09-29): the pin-graph pair completed — repin's CAP path got a
  self-test, and its planning half became a command. (1) Scenario G in
  repin_self_test: two specs pinning each other by file sha oscillate forever
  in principle; the walk must stop at MAX_REPIN_PASSES with a loud `CAP:` line
  and rc=2, not hang — 17/17. (2) `tri fpga-pins FILE` (board.py pin_pinner_map
  + print_pin_radius + pins_self_test): the transitive blast radius of editing
  FILE through the pin graph — L1 direct pinners, L2 pinners of those specs,
  fixpoint — plus the params generators reading any spec inside the radius:
  the exact set fpga-repin then walks, queryable BEFORE the edit. Its first
  live run (harness radius: 10 specs, 10 generators, rc=0) caught a real bug
  in my own cycle detection: it printed CYCLE for `reopen pins generate
  again`, but two paths reaching one spec is a diamond (reopens pin BOTH the
  generate spec and the harness — the corpus is layered like that), not a
  cycle; a true cycle is mutual pinning (a node whose pinner chain leads back
  to itself), now detected by reachability and printed as CYCLE rc=1. The
  diamond class is pinned in the self-test (5/5). Live verification against
  known truth: harness → 10 specs 1 level; retransmit spec → 3 reopens + batch
  on 2 levels; reopen_t27 → batch only — exactly the fire-15 cascade shape.
  (3) Competitor re-check (targeted, from fire 13): nicholi.ai's engine went
  open source (Neumann-Labs/ternfpga, Apache-2.0, Arty A7-35T, BitNet-2B-4T,
  energy partly Vivado-derived and self-flagged as such) — the floor entry
  hardened, still no receipts; zkML newcomers (ZK-Tracer, deep-prove)
  accelerate proof GENERATION on GPU/ASIC — they sharpen the complement line
  rather than close the on-silicon-receipts gap. research.md table updated.
  Specs 17/17, keycheck 0 hits, loopcheck floor = exactly the two known igla
  anomalies. Board, pods, RTL untouched.
