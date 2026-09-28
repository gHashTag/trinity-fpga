# 32-token generation with retransmit and port reopen, AX7203 node: record

Pre-registered in `specs/trinet/tern_tc_generate_long_ax7203.t27` (sha256
`29582b77a101390e…`) and `specs/trinet/tern_tc_reopen_long_ax7203.t27` (sha256
`cc5a949140240993…`) before any run of them, committed with this document. The
first spec fixes what the run must produce; the second fixes the harness that
carries it. The board arm's runner is
`conformance/tern_tc_generate_reopen_long_ax7203.py`. Its parameters are
generated from the specs by `conformance/tern_tc_generate_long_from_spec.mjs`
and `conformance/tern_tc_reopen_long_from_spec.mjs`, and `tri fpga-specs`
checks them for drift. The link is `conformance/tern_tc_reopen.py`, unchanged.

This is T34: longer generation, with the CPU paths compared. It is a new claim
with its own record, not a second attempt at the 8-token one; the 8-token
reopen run in `TERN_TC_REOPEN.md` stays **PASS** and nothing of it is
re-litigated.

## Why this run

Every generation run so far was 8 tokens, with a CPU reference that also ended
at token 8. T34 asks for longer generation with a CPU comparison: 32 tokens on
the board, the CPU paths compared at 32 and 128.

- 32 tokens is 30,762,752 jobs and 584,492,288 answer bytes: 4x the answers of
  any board run so far, and 1.32x the hub-free loss-free evidence itself
  (23,385,600 answers, `UART_LOSS_HUBFREE.md`). The window-24 diagnostic
  (`UART_LOSS_DIAG.md`) bounds the loss rate at 1.83 per 10^6 jobs (95 %),
  which allows up to about 56 transport events in a run of this size. So the
  board arm runs through the reopen link, the only harness that has survived a
  lost byte: the retransmit-only run stopped in call 145 of 192 on exactly
  that.
- Past token 8 no CPU reference existed until now. The generation spec fixes
  one to 32 tokens and records the continuation to 128, so a wrong accepted
  sum on the board can no longer hide behind "no reference beyond here".

## The CPU comparison, fixed before the run

Five runs, no board, no key file. The first four go through the wrapper
`conformance/tern_tc_generate_long_ax7203.py`, so the pinned 8-token runner
computes them with the long parameters installed. The fifth counts the totals
the runner's `--cpu` mode does not print.

| log | path | result |
|---|---|---|
| `cpu_runs/gen_tokens_32_cpu_int.log` | `python3 tern_tc_generate_long_ax7203.py --cpu` | 32 ids, exit 0; ids equal the spec's `CPU_INT_IDS` id for id |
| `cpu_runs/gen_tokens_32_cpu_c.log` | `python3 tern_tc_generate_long_ax7203.py --mode c` | 32 ids, exit 0; ids equal `CPU_INT_IDS` id for id (the float order of `tc_infer.c` changes no token) |
| `cpu_runs/gen_tokens_128_cpu_int.log` | `python3 tern_tc_generate_long_ax7203.py --cpu --tokens 128` | 128 ids, exit 0; tokens 0-31 equal `CPU_INT_IDS`, tokens 16-127 the period-8 loop |
| `cpu_runs/gen_tokens_128_cpu_c.log` | `python3 tern_tc_generate_long_ax7203.py --mode c --tokens 128` | 128 ids, exit 0; same structure, equal to the int path |
| `cpu_runs/gen_tokens_long_counts.log` | the counting helper over `CpuDots` | int 32: jobs 30,762,752, skipped 7,944,448, rows 540,672, calls 768, smallest margin 24 milli; int 128: jobs 122,788,544, skipped 32,040,256, rows 2,162,688, calls 3,072, margin 24 milli; `c32 == int32` True |

- The first 8 ids equal the 8-token spec's `C_GREEDY_IDS` and `CPU_INT_IDS`;
  tokens 8-15 continue them; the last check of that log asserts both.
- **The repeat loop.** From token 16 the greedy path repeats `1516 740 306 317
  705 779 317 85` with period 8, through token 127 on both CPU orders. A
  9M-parameter model degenerates under greedy sampling; that is the model's
  own behavior, recorded here rather than hidden. The 8K tokenizer pinned in
  `artifacts/tokenizers/` is for reading the ids, not a claim about what they
  spell. 32 tokens on the board cover the crossover into the loop and two full
  periods of it.
- **Jobs per token are not constant.** Which digit planes are all zero depends
  on the activations, so the counts are counted, not extrapolated:
  30,762,752 is not 32 x 960,288 (the 8-token arm's average). A full token
  costs 1,209,600 jobs; 30,762,752 + 7,944,448 skipped digit planes equal
  exactly 32 x 1,209,600, an invariant the spec asserts.

## What changes, and what does not

Only the length changes, through the long generation spec's parameters:
`N_TOKENS` 32, the counts above, and `LIMIT_S` 13500. The 8-token arm's 3600 s
ceiling is 4x too small for 4x the tokens; the change is stated in both specs,
not hidden. At the measured 4712 answers/s the run needs about 6529 s; the
limit holds every reopen-arm ceiling spent at the 2500/s floor with room to
spare. Every link, protocol, ceiling, window and key-handling byte is the
8-token reopen run's, imported unchanged and pinned by sha256 in the reopen
spec: both runners, the harness, the node RTL, the retransmit protocol, the
reopen link, the model and the activations.

- **The wrappers are thin arms, not copies.**
  `tern_tc_generate_long_ax7203.py` and
  `tern_tc_generate_reopen_long_ax7203.py` install the long parameter modules
  under the names the pinned runners read, then import the unchanged runners.
  Every `--self-test`, preflight, `--refcell` and board byte runs pinned code.
- **The rehearsal stalls keep the 8-token offsets.** The reopen mechanism
  clears position-independent byte counters, so keeping the schedule means the
  new thing the rehearsal tests is length: an answer-stream stall near answer
  5,754,002 (byte 109,326,049) and a request-stream stall 5 bytes into
  request 2,000,000. After the reopen at answer 5,754,002 the run must
  continue to 30,762,752 and stay bit-exact.
- **What is never retried.** Everything the 8-token reopen record lists:
  `MAX_ATTEMPTS` nonces per job, a reopen past `MAX_REOPENS` (4), and every
  receipt lie.

## Prediction

**Board.**

- Token ids equal the long generation spec's `CPU_INT_IDS`.
- Every one of 30,762,752 jobs is credited by exactly one answer whose tag
  verifies under the node key; 540,672 of 540,672 rows bit-exact.
- The ceilings hold: retransmits ≤ 256, resyncs ≤ 32, reopens ≤ 4, elapsed ≤
  13,500 s.

The runner prints `receipts verified (tag) : N/N` only then. One wrong
accepted sum could change a token after token 8, where no CPU reference
existed until this spec fixed one; the run aborts at the first rejected
receipt or inexact row instead, and then no token from it is cited.

**What each outcome says.**

| outcome | what it says |
|---|---|
| PASS, 0 reopens | 32 tokens finished. The chain holds to 4x the length of any earlier run. |
| PASS, 1 or more reopens | Those reopens cleared those stops, at 4x the length. |
| FAIL with `ReopenExhausted`, or a job past its attempts after a reopen | A reopen at these waits does not clear the stop. |
| FAIL for any other reason | Recorded as it is; it says nothing about the hypothesis. |

**Rehearsal (no board).** The whole 32-token run through the reference cell
behind the RTL's frame parser, with the retransmit spec's five losses plus the
two stalls above, must end REHEARSAL OK with the same ids and counts, at least
one retransmit per scheduled loss, and exactly 2 reopens: one per stall, none
for the ordinary losses.

**What it does not say.** It does not find which side stalls or loses. It does
not say the UART is lossless. It is not speed (about 109 minutes at the
measured rate) and not text quality (the ids repeat; the CPU comparison
section says why). One run of 32 tokens from one start token, greedy.

## Checks without the board

None of these used the board or the key file; they use the harness's test key.

| check | command | result |
|---|---|---|
| generate arm | `python3 tern_tc_generate_long_ax7203.py --self-test` | PASS: preflight exact equality on the long parameters — ids, jobs 30,762,752, skipped 7,944,448, rows 540,672, calls 768, margin 0.0241; `--mode c` ids equal the int ids id for id; reference cell 23296/23296; each of the six injected faults (lie, damage, nonce, impersonate, wrong_key, drop) stops the run |
| reopen arm | `python3 tern_tc_generate_reopen_long_ax7203.py --self-test` | PASS: the generation pins hold on the long parameters; the reopen link's own suite (2.0 s); four BoardDots cases with losses and stalls, each 23296/23296 with waits `[2]` and every event kept; a cap of 4 keeps only 4 of 50 events (the all-kept check can fail); a dead stall, a lie and an impersonation after a reopen each stop the run |
| specs | `tri fpga-specs` | compiles; 14/14 clean; the two new generators report 48 consts / 11 tests / 61 asserts and 59 consts / 9 tests / 28 asserts, 0 failures; params not drifted |
| selftest | `tri fpga-selftest` | 14 run, 0 bad; both long wrappers are found by the flag scan and run the pinned code with the long parameters (7.1 s, 10.2 s) |
| CPU comparison | the five logs above | ids equal the spec id for id; int and c agree at 32 and 128; the 128 continuation extends the period-8 loop through token 127 |

## Rehearsal

One pair, through `tri fpga-rehearse`, which runs the same `--refcell` command
twice at once and compares the event lines with times masked. Neither used the
board or the key file. Committed before the board run.

**Pair, reopen spec `cc5a949140240993`.**
`rehearsal_runs/gen_tokens_32_reopen_refcell_{1,2}.log`, 11:13:43Z to
11:43:42Z on 2026-09-28.

- Both runs: REHEARSAL OK. Token ids equal `CPU_INT_IDS`. 768/768 calls,
  30,762,752 of 30,762,752 jobs credited, 540,672/540,672 rows bit-exact.
- Transport: 106 retransmits (ceiling 256), 7 resyncs (ceiling 32), 2 reopens
  (ceiling 4).
  - Reopen 1, request-stream stall, call 51: flush 3 came after 0 bytes since
    flush 2; the link closed the port, waited 2 s, opened it again.
  - Reopen 2, answer-stream stall, call 145: flush 6 came after the silent
    flush 5; wait 4 s.
  - The stalls sit at the same calls as the 8-token rehearsal's, as keeping
    the offsets implies. The five ordinary losses caused resyncs or
    retransmits, never a reopen.
- `events kept : 113 (cap 512); lost 106 + resyncs 7 = 113`.
- The two runs' event lines were identical: 936 lines once times were masked.
  Key hits 0 in both logs.
- Elapsed 1798.0 s and 1794.4 s at a load of about 6.7 on 8 cpus (17138
  answers/s through the reference cell).

The rehearsal matches the prediction: exactly 2 reopens, one per stall, none
for the ordinary losses, and after the reopen at answer 5,754,002 the run
continued to 30,762,752 and stayed bit-exact. Whether a reopen clears a real
stop on the line is what the board run tests.

## Board run

Not run at the time this pre-registration was committed. The plan, after
`tri fpga-quiet` and with `tri fpga-watch-clients gen_tokens_32_reopen` beside
it:

```
tri fpga-run gen_tokens_32_reopen --limit 13800 -- python3 -u tern_tc_generate_reopen_long_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt
```

The owner's standing directive covers this run. After it, `tri fpga-keycheck`,
then `tri fpga-decode board_runs/gen_tokens_32_reopen.log --tokenizer
artifacts/tokenizers/data8k_tokenizer.json` — the first generation record
decodable with the tokenizer pinned in this repo.
