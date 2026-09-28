# 7-token generation with the t27-tuned model, AX7203 node: record

Pre-registered in `specs/trinet/tern_tc_generate_t27_ax7203.t27` (sha256
`6cd04860…`) and `specs/trinet/tern_tc_reopen_t27_ax7203.t27` (sha256
`648451ffab507442`), committed before any board run of them, together with this
document's predecessors in `TERN_TC_GENERATE.md` and `TERN_TC_REOPEN.md`. The
board runner is `conformance/tern_tc_generate_reopen_t27_ax7203.py`, the CPU
arm is `conformance/tern_tc_generate_t27_ax7203.py`, and their parameters are
generated from the specs by `conformance/tern_tc_generate_t27_from_spec.mjs`
and `conformance/tern_tc_reopen_t27_from_spec.mjs`; `tri fpga-specs` checks all
of them for drift.

## Why this run

Every board arm before this one ran the tern_tc model as shipped: the TC02
weights the training pipeline exported. This is the first arm whose weights
were changed locally, and the change is the project's own subject matter — the
model was fine-tuned on a corpus built from the t27 language's own items.

- **Base.** TC02, 9,076,800 ternary parameters (6 layers, d_model 320, d_ff
  864, vocab 8192).
- **Fine-tune.** 337 steps on the FIM corpus tokenized with the project's own
  8K tokenizer, 2026-09-28, one rented GPU pod, total cost $0.58. Validation
  bpb 0.756 → **0.611**.
- **Export.** TC02 binary, sha256
  `3d8397ef4e388d0cadd1725f64d45ddd4ca0811cf8fbedc4a6a3b2fe92cd45cc`,
  `~/igla-coder-gpu/c_infer/t27_tuned/model.bin`. The generation spec pins this
  sha and refuses any other model file.

It is also the first arm whose length the model, not the host, chooses: the
t27-tuned model emits EOT (id 0) at token 7 on this arm's prompt. The host
asked for 128 tokens and stopped at 7 with byte-identical ids — pinned by a
spec test and logged in `cpu_runs/gen_tokens_7_t27_counts.log`, because a
runner that prints "8 tokens" in its pinned help text while running 7 needs the
length's provenance in the record, not in a comment.

## What changes, and what does not

Only the model bytes and the constants derived from them change. Everything
else is imported unchanged and pinned by the same shas as the 8-token reopen
run: link `tern_tc_reopen.py` `4bfd81b3…`, protocol `tern_tc_retransmit.py`
`eda9f8bc…`, harness `tern_tc_layer_ax7203.py` `8a9a5f6e…`, node RTL
`trinet_node_core.v` `920a0842…`, and both pinned runners.

- **The thin-arm wrappers.** `tern_tc_generate_t27_ax7203.py` and
  `tern_tc_generate_reopen_t27_ax7203.py` do not copy the runners. Each
  installs its generated parameters under the module names the pinned runner
  reads (`tern_tc_generate_params`, `tern_tc_reopen_params`) and imports the
  unchanged pinned file. The reopen wrapper hands the pinned runner 7 tokens of
  t27-tuned weights while the runner believes it is running its own
  8-token parameters.
- **Numbers that moved with the model.** `JOBS_EXPECTED` 6,712,896 (from
  7,682,304), skipped 1,754,304, rows 118,272, calls 168 (from 192; 24 calls
  per token × 7). `MIN_MARGIN_MILLI` 210 int (logit margin 0.2108, token 2,
  id 397) and 190 c.
- **Numbers that did not.** Every transport constant: window 24, request 24
  bytes, response 19 bytes, baud 1,144,744, node id, retransmit ceiling 256,
  resync ceiling 32, reopen ceiling 4, reopen waits 2, 4, 8, 16 s, limit 3600 s.

## The C_REF repin

`tc_infer.c` — the C reference for the CPU float path — gained five
portability header lines upstream (igla-coder-gpu `52be443`) after T33/T34
pinned its older bytes, with zero arithmetic change. C_REF is a reference of
record, never read at run time: `--mode c` is the runner's own Python float sum
in tc_infer.c's order. The pin doctrine for files of record now accepts an
on-disk match **or** bytes reachable from the reference repo's git history
(`gitBlobSha` in the three generation generators). Files read at run time —
HARNESS, MAC32, MODEL — stay strict working-tree pins. The T35 specs pin the
current shas; `tri fpga-specs` is 16/16 clean.

## Checks without the board

None of these used the board or the key file.

| check | command | result |
|---|---|---|
| CPU arm self-test | `python3 tern_tc_generate_t27_ax7203.py --self-test` | PASS |
| reopen arm self-test | `python3 tern_tc_generate_reopen_t27_ax7203.py --self-test` | PASS |
| CPU integer, 7 tokens | `cpu_runs/gen_tokens_7_t27_cpu_int.log` | ids equal `CPU_INT_IDS`; jobs 6712896, skipped 1754304, rows 118272, calls 168, margin 210 milli |
| CPU float (c order), 7 tokens | `cpu_runs/gen_tokens_7_t27_cpu_c.log` | same ids; margin 190 milli |
| CPU integer, 128 tokens | `cpu_runs/gen_tokens_128_t27_cpu_int.log` | stops at 7 — EOT; byte-identical ids and counts |
| CPU float, 128 tokens | `cpu_runs/gen_tokens_128_t27_cpu_c.log` | stops at 7; same ids |
| counts driver | `cpu_runs/gen_tokens_7_t27_counts.log` | all four runs and both equality checks in one log, exit 0 |
| specs | `tri fpga-specs` | 16/16 compile, tests and drift checks pass |

## Rehearsal

One pair through `tri fpga-rehearse`, spec `648451ffab507442`, logs
`rehearsal_runs/gen_tokens_7_t27_reopen_refcell_{1,2}.log`, both REHEARSAL OK.

- Both runs: 7 tokens, ids `204 264 397 226 21 277 0` = `CPU_INT_IDS`;
  6,712,896/6,712,896 reference-cell receipts; 118,272/118,272 rows bit-exact;
  calls 168/168.
- Transport: retransmitted 103 (ceiling 256), resyncs 6 (ceiling 32), lost
  103, unverified 2, foreign frames 1, late answers 0. Link: reopens 2
  (ceiling 4), flushes 6, waits `[2, 4]` s — one reopen per scheduled stall,
  none for the ordinary losses, the same pattern as the 8-token rehearsal.
- `events kept : 109 (cap 512); lost 103 + resyncs 6 = 109`. The two runs'
  event lines were identical once times were masked. Key hits 0.

**Four of the five scheduled losses fire, not five.** The schedule is
`RX_HOLE_AT [19008, 137468535, 57000000]`, `TX_DROP_AT [120000010,
144000023]` plus two stalls. The second rx hole, at answer byte 137,468,535,
lies past this run's answer stream (6,712,896 answers × 19 bytes = 127,545,024
bytes, shorter than the 8-token run the schedule was sized for), so it never
happens.
The runner's generic RESULT line says "5 scheduled losses recovered" — it
prints the schedule's length, not the count that fired. The spec pins the fact
with a test (`RX_HOLE_AT[1] > JOBS_EXPECTED * RESP_LEN`), and this paragraph is
the plain statement of it: **4 of 5 fired, all 4 recovered.**

## Board run

**PASS, 0 reopens.** One attempt, `board_runs/gen_tokens_7_t27_reopen.log`,
17:13:09Z to 17:36:44Z on 2026-09-28. No flash: the node was loaded and keyed,
the same bitstream the 8-token reopen run used. The owner's yes for it:
«гоняй все сам и улучшай» (2026-09-28, before the run).

```
receipts verified (tag) : 6712896/6712896 under node 0x5452494e
rows bit-exact          : 118272/118272  (int8 activations from the model's own forward pass)
transport               : retransmitted jobs 0 (ceiling 256), resyncs 0 (ceiling 32), lost 0, unverified 0, foreign frames 0, late answers 0, bytes skipped while scanning 0
link                    : reopens 0 (ceiling 4), flushes seen 0, waits [] s
events kept             : 0 (cap 512); lost 0 + resyncs 0 = 0
elapsed                 : 1414.5 s of 3600 (4749 answers/s in run())
longest host pause      : 37.8 ms
ids board  : 204 264 397 226 21 277 0
CPU_INT_IDS: 204 264 397 226 21 277 0
```

What it says:

- All 168 calls ran. Every one of the 6,712,896 jobs was credited by exactly
  one answer whose MAC32 tag verified under the node key — the first board run
  where the weights that produced the answers are the locally fine-tuned ones,
  and the receipt chain cannot tell the difference, because the claim it proves
  (every ternary dot product computed on the node) does not depend on which
  weights were streamed.
- The setkey step found the node already keyed; the receipts verified under
  that key, so it was ours.
- `tri fpga-decode gen_tokens_7_t27_reopen.log --tokenizer
  artifacts/tokenizers/data8k_tokenizer.json` decodes the ids to
  `'\n    return 0;\n<|endoftext|>'` — the same text the CPU paths produce.
- A receipt shows the answer was MACed under the node key. It does not by
  itself prove the FPGA computed it (see the skill's trap list).

What it does not say:

- **Whether a reopen clears a stop.** No stop happened: 0 losses, 0 resyncs,
  0 reopens. The hypothesis stays tested only in the rehearsal, as before.
- **Not a model-quality claim.** bpb 0.611 on the validation split is the
  fine-tune's number; this arm's output is one syntactically clean line of C
  (`return 0;`) that the model chose to end. One line is not a program, and the
  before/after demo in the loop notes shows the model writing structurally
  right, factually wrong t27 elsewhere. The run proves the delivery of the
  fine-tuned weights' answers, not their usefulness.
- **Not a speed claim.** 4749 answers/s is the link rate; 23.6 minutes for 7
  tokens over a 1.14 Mbaud UART with 19 receipt bytes per job.
- **One clean run does not make the link lossless** (see `UART_LOSS_DIAG.md`'s
  bound, 1.83 events per 10^6 jobs at 95 %, which allows several events in a
  run of this size).

Command:

```
tri fpga-run gen_tokens_7_t27_reopen --limit 3800 -- python3 -u tern_tc_generate_reopen_t27_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt
```

The run started after `tri fpga-quiet` said the host was quiet. Beside it,
`tri fpga-watch-clients gen_tokens_7_t27_reopen` sampled the CP2102N's IOKit
user clients every 30 s: **11 clients in all 48 samples** (min 11, max 11,
first 11, last 11) — flat through the whole run, and no stop to explain.
