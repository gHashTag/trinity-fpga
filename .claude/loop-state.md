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
  back to GEN_SPEC only for logs without the line. decode self-test 11/11.

## READY (next work, in order)

1. Commit + push fire 3's output (record doc, two board logs via `git add -f`,
   skills, loop-state, loop research) — branch `claude/peaceful-noether-dperdx`,
   English commits; 8955ea793 and c24d25b7a are also still unpushed.
2. Next-loop options live in `.claude/loop/research.md` (receipt batching /
   Ethernet path / corpus round 2); pick one only with the owner awake, or let
   the next fire start with the cheap one (receipt-batching spec draft).
3. End-of-fire report + three collaboration options; self-critique and anomaly
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
