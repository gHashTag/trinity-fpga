# Round-2 fine-tune of tern_tc on t27 — pre-registered plan (option C)

Written fire 33 (2026-09-29), BEFORE any pod is started. Nothing here has
been run; every number cites its source. The owner's pick ("C") starts the
sequence in §6 — not before. No board, no RTL: this is the model-side leg.

Fire 34 adversarial pass (same day, still before any execution): three
corrections applied and recorded here — §5b re-anchored to the eval cadence
(step 2,022, not 2,000), §6.4 smoke side effects corrected (ckpt.pt DOES
advance — train.py checkpoints after the break), §6.5 --tokens made exact
(1.77e9 floors to 3,375 steps, not 3,370). Every other figure recomputed
from train.py arithmetic, the corpus manifest and the cost anchors: holds.

## 1. Why round 2 looks like this (measured)

- Fire 32 diagnosed the one-line output: the corpus is not the cause. Over
  the pinned builder walk (t27 `9fec01a78`, sibling `t27_bench fim`),
  3,521 train FIM targets, 58.3 % six-plus lines, median 48 tokens; the
  tuned model's actual output (6 tokens) sits at the 1.3rd percentile of
  target length. The data taught multi-line; the 337-step run did not
  learn it.
- Round-1 anchors (loop-state DONE + pod volume): 337 steps × 524,288
  batch-tokens = 176.68 M tokens = **23.98 epochs** over the 7,368,311-token
  train split (corpus manifest, fire 28 keep). Val bpb 0.756 (base) →
  0.611 (tuned); $0.58 → **$1.72 per 1,000 steps**. Model size `tc`:
  6.46 M ternary block weights + 2.6 M head ≈ 9.1 M params, sized for
  XC7A200T BRAM (77 % of it — model.py SIZES comment).
- Consequence: the lever is steps on the SAME corpus (no rebuild, no
  reshaping), and the central risk is epochs — 24× repetition already;
  more steps go deeper. The stop rules in §5 are the control, not
  ornament.
- Capacity is walled: every larger size (13m+) breaks the board story
  (BRAM fit). If `tc` plateaus, the verdict is "the BRAM-sized model
  plateaus" — an architectural result, not a prompt to upscale.

## 2. Mode: extend the round-1 run (resume ckpt.pt)

`train.py` resumes with full state (model + optimizer moments + data-stream
position + step) when `<out>/ckpt.pt` exists; `--init` loads weights only,
fresh schedule. Round 2 EXTENDS: same `--out /workspace/runs/tern_tc_t27`,
larger `--tokens`. The schedule restart is named, not hidden: warmup and
decay recompute against the new total (for 3,370 steps: warmup 100 steps,
decay from step 2,696), so LR steps back up to peak at resume — a bounded
warm restart with restored AdamW moments, SGDR-shaped.
Fallback, pre-registered: if ckpt.pt is absent or fails to load on the
volume, run the `--init` variant (round-1 final.pt weights, fresh
schedule) — same budget, same stop rules; record which branch ran.
Overwrite hazard, caught while writing this: resume REWRITES run.json at
start and a finished round 2 replaces final.pt — the volume is a working
dir, not an archive. §6 step 3 pulls the round-1 records BEFORE extending.

## 3. Budget (from the $1.72/1k-steps anchor; new-cost column = new steps only)

| total steps | new steps | tokens | total epochs | new cost |
|---|---|---|---|---|
| 1,685 (5× r1) | 1,348 | 883 M | 120 | $2.32 |
| **3,370 (10× r1)** | 3,033 | 1.77 B | 240 | **$5.22** ← target |
| 4,000 (cap) | 3,663 | 2.10 B | 285 | $6.30 |

Hard cap: 4,000 steps or $7, whichever first. Balance at round-1 close
$74.68 → ≥ $67 after. Wall time: round-1 hours live in the volume's
run.json, not recorded locally — read at §6 step 3 and record here before
the full run.

## 4. Success criteria (judge = train.py do_eval on the same val split)

- Primary: final val_bpb_mix **≤ 0.55**.
- Stretch: < 0.50 (option C's original number).
- Behavioral (the point of the fire-32 diagnosis): greedy FIM decode on 20
  held-out prompts produces ≥ 2-line bodies on ≥ 25 % of them (round 1:
  one line, 6 tokens, 1.3rd percentile). Driver: the same greedy path as
  the T35 pre-registration or `t27_bench gen` — pick at run time, record
  which.
- Guards: EOT still emitted; decode stays syntactically clean under the
  bench checker; TC02 export path unchanged (new sha recorded).

## 5. Stop rules (any one halts the run)

a. **Overfit**: val_bpb_mix rises on 2 consecutive evals (eval_every =
   337 steps) → stop, keep the best checkpoint.
b. **Plateau**: at the 6th eval (step 2,022 — evals land on multiples of
   337) the best val_bpb_mix has improved < 0.02
   over round 1's 0.611 → stop; verdict "capacity ceiling of the
   BRAM-sized model" (§1 wall).
c. **Budget**: 4,000 steps or $7.
d. **Restart spike**: train loss > 2× round-1's end value at any of the
   first 3 evals after resume → stop; switch to the --init branch (§2).
e. **Pod/GPU fault** → stop, salvage log.jsonl (appends incrementally),
   triage before any retry (MNL: 3 failures = toxic, skip).

## 6. Sequence (starts ONLY on the owner's "C")

1. `pod.py up tct27` (state `work/pods/tct27.json`; volume
   `igla-coder-data` h6zg0ak7b6 at /workspace). Never terminate the
   volume; stop, don't kill, at the end.
2. Verify inputs BEFORE spending: sha256 of `/workspace/ft_t27_8k/
   manifest.json` == the local keep copy (fire 28 blob = the round-1
   original); `runs/tern_tc_t27/` holds ckpt.pt, run.json, log.jsonl.
3. Pull the round-1 records off-pod FIRST (rsync -rlt; §2 overwrite
   hazard): run.json, log.jsonl, final.pt, ckpt_predecay.pt listing. Read
   run.json: peak LR, exact flags, hours — the full run reuses them
   verbatim except --tokens (and the §2 branch if taken). Record hours
   in §3.
4. Smoke: resume + `--max_steps 340`. Expect "resumed from step 337",
   three steps. Side effects, named (fire-34 correction): train.py
   checkpoints unconditionally after the break, so ckpt.pt advances
   337→340 — the three steps are real and count toward 3,370 — and
   run.json is rewritten (§2 hazard; the pull is step 3, before this).
5. Full: `--tokens 1766850560` (= 3,370 × 524,288 exactly — 1.77e9 would
   floor to 3,375), eval_every default (0.1),
   time_limit_h safety margin from step-3 hours.
6. Watch evals against §5; log.jsonl appends — pull live if needed.
7. Post: auto final eval → summary; export TC02 (same exporter, new sha);
   pull final.pt, run.json, log.jsonl, summary.json; keep them locally
   (`tri fpga-keep`); run the §4 behavioral check; record results in
   loop-state DONE + research.md option C; stop the pod (never terminate).

## 7. What this plan deliberately does NOT do

No corpus rebuild (fire 32 exonerated the mix), no larger model (BRAM
wall), no LR sweep (reuse round-1's recorded peak), no second seed (the
question is budget, not variance). If §5b fires, the next lever is data
QUANTITY — the t27 tree has grown since 9fec01a78, and a rebuilt corpus
over a newer pin adds new targets instead of more epochs — recorded as
the round-3 option, decided then, not now.
