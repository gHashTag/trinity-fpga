# Loop research — weak points + competitors (2026-09-29, fire 2; competitor
# table refreshed fire 8, wedge re-checked fires 13, 16 & 26)

Swept through BrowserOS neo (Google → arXiv/GitHub). What the field looks like
from the tern_tc/AX7203 vantage, and where this project honestly stands.
Fire-8 refresh: TeLLMe and the nicholi.ai $130-board engine added after a
re-sweep; none of the new entrants publishes receipted inference either —
the wedge below is unchanged. Fire-13 re-check: the "verifiable inference"
vocabulary is heating up (zkML guides, on-chain proof-of-inference markets,
PQ-signed API receipts, pairing-based tensor commitments — two strongest
added to the table), but every entry is a software layer over GPU/API
serving; still nobody receipts on the accelerator silicon. Hobby-tier
BitNet-on-FPGA practice posts (KV260 write-ups) keep appearing at the
nicholi.ai price tier — floor, not competition. Fire-16 re-check: the
nicholi.ai engine went open source (Neumann-Labs/ternfpga, Apache-2.0, 72
commits, Arty A7-35T, BitNet-2B-4T batch-1 decode; energy self-flagged as
Vivado-derived) — the floor entry hardened, still no receipts; zkML-side
newcomers (ZK-Tracer, deep-prove) accelerate proof GENERATION on
GPU/ASIC, which sharpens the complement line rather than closing the gap.
Fire-26 re-check: PENSA joined the throughput tier (NeurIPS 2026, full
BitNet 2B4T on an HBM Alveo U50, 58.09 tok/s @ctx128); ternfpga unchanged
at 72 commits; Ternarycore active into Jul 2026 (hw verification run) but
still RTL-correctness only. The bigger movement is vocabulary: the Linux
Foundation's TRACE spec (Aug 2026) calls its workload-level TEE records
"tamper-proof receipts" — 135k PyPI downloads in ten weeks. TRACE's root
of trust is CPU confidential computing (SEV/TDX), not accelerator silicon,
and it attests workloads, not per-job math — the wedge holds, but our claim
must keep saying "on-silicon per-job receipts" or it now reads as a TRACE
variant. Fire-36 re-check: no movement in the lane itself — a fresh
ternary-FPGA + receipts/verifiable search returns nothing, PENSA and TRACE
are unchanged since the fire-26 record, Ternarycore shipped its v1.0-trets
release + Zenodo DOI (Sep 19, 337 commits, still RTL-correctness only), and
ternfpga's README now documents nine build phases with on-fabric energy
measurements (attention 1.99 J/tok, FFN 1.62 derived, phase-9 co-resident
bit-exact at 45/50 BRAM — "the honest pivot") — still 72 commits, still
zero receipts a stranger can verify. The wedge is intact and still
unoccupied.

## Competitors (all verified live, September 2026)

| who | what | number that matters |
|---|---|---|
| **TerEffic** (arXiv 2502.16473) | FPGA ternary LLM accelerator; fully-on-chip 370M variant + HBM 2.7B variant | ~16,300 tokens/s (370M, on-chip) |
| **Ternarycore** (github.com/Ternarycore/ternarycore, TRETS paper, CERN-OHL-S + commercial dual license) | open-source BitNet b1.58 accelerator on Arty-7 and Tang Nano; int8 attention measured on silicon; INA226 energy kit; 337 commits, hw verification run Jul 2026 | a whole maintained OSS stack |
| **PENSA** (NeurIPS 2026, Sydney; TernaryNet collab; phwl.org writeup) | full BitNet b1.58 2B4T inference on an HBM-equipped AMD Alveo U50 — row-partitioned ternary engines, packed TQ1_0 weights from HBM pseudo-channels | 58.09 tok/s @ctx 128, 24.60 @ctx 2048 (2.14–3.14× Xeon baseline); no verifiability story |
| **Ando & Nakashima** (arXiv 2609.27453, CANDAR 2026 CSA workshop) | BitNet mapped onto a CGLA ASIC via signed-int4 lanes (OP_SMA4), no BitNet-only datapath | 2.52 tok/s, 0.390 ns per s4 product at 28 nm |
| **ELiTeFormer** (arXiv 2607.03652, Agostinelli 2026) | first Transformer unifying hybrid linear attention + ternary, co-designed for FPGA | architecture-level claim |
| **VitaLLM** (arXiv 2604.27396, Lin & Chang) | dual-core (TINT ternary + BoothFlex mixed) with Leading-One-Prediction KV pruning | edge accelerator, prefill+decode |
| **Bitnet.cpp** (Microsoft) | CPU edge inference for ternary LLMs | the baseline everyone cites |
| **TeLLMe** (UCI-CORSA, FPGA 2026, ACM 3748173.3779191) | end-to-end ternary LLM prefill + decode on FPGA, course-turned-paper stack (TeLLMe_FPGA_2026 repo) | end-to-end (both phases), not just kernels |
| nicholi.ai engine → **ternfpga** (Neumann-Labs/ternfpga, open-sourced by fire 16, 2026-09; Apache-2.0) | ternary BitNet-2B-4T batch-1 decode on a $130 Arty A7-35T, 72 commits; README (fire 36) documents nine build phases with on-fabric energy (attention 1.99 J/tok, FFN 1.62 derived, phase-9 co-resident bit-exact 45/50 BRAM) | floor price point, now with self-measured silicon energy — still no receipts a stranger can verify |
| **TensorCommitments** (arXiv 2602.12630, 2026) | verifiable LLM inference: GPU prover commits to activation tensors as multivariate polynomials, client verifies with pairings | 12 ms verify, 2 B/token, ~1 % prover overhead (LLaMA-2-13B) — software/GPU layer |
| **Animica AICF 7.1.1 receipts** (2026) | each OpenAI-compatible API response can carry an ML-DSA-65-signed receipt binding model/prompt-hash/output-hash | PQ-signed *who-served-what* attestation — software gateway, not silicon |
| **TRACE** (Linux Foundation/CoSAI spec, Aug 2026; OPAQUE + AMD/Intel/Microsoft/TII) | open AI runtime-attestation spec: tamper-proof "Trust Records" per workload (execution env, launched software, data classifications, policies), root of trust = CPU TEEs (SEV/TDX) | 135k PyPI downloads in ~10 weeks; workload-level attestation, NOT per-job math and NOT accelerator silicon — complement, with a "receipt" vocabulary collision to stay clear of |

## Where we actually stand (no varnish)

**Throughput is not our claim and never was.** Our chain: ~4.7k jobs/s over a
1.14 Mbaud UART, 24 minutes for 7 tokens, 19 bytes of receipt per matmul job.
TerEffic's 16k tok/s is another universe. Anyone reading our record for speed
has misread it; the specs say so explicitly ("It is not speed").

**What nobody in the list has:** cryptographically receipted inference. Every
one of the 6,712,896 matmul jobs of the T35 run comes back as a MAC32-tagged
receipt verified under a node key; the run survives byte losses, resyncs and a
physically reopened serial port and stays bit-exact; everything is
pre-registered in executable specs before the board is touched. That is a
verified-computation claim, not an accelerator claim — and it is the wedge.
TerEffic/Ternarycore/ELiTeFormer publish throughput and energy; none
publishes "every FLOP is accounted for and the ledger is checkable". The
fire-13 additions sharpen the same line from the other side: zkML and
PQ-signed receipts verify *software serving* (re-execution proofs, gateway
attestation); ours verifies the *computation inside the accelerator* — the
receipt is produced by the silicon, per job, at line speed. The two are
complements, not rivals, but the vocabulary overlap (zkML, and since Aug
2026 TRACE's "Trust Records") means our claim should always be scoped
"on-silicon per-job receipts" so it cannot be read as another
zkML/TEE-attestation variant.

## Weak points of the task (own scan, ranked by cost)

1. **Wire bandwidth dominates useful work — and it is the requests, not the
   receipts.** Measured from the T35 log (2026-09-28): the 24 B request stream
   alone accounts for 99.7 % of the 1414.5 s wall; answers (19 B/job) account
   for 79 %. Batching receipts alone shortens nothing; the win is deduplicating
   the request stream (each w chunk is sent 6×, once per digit plane).
   Full arithmetic and the option ladder: `conformance/TERN_TC_BATCH_PLAN.md`.
2. **UART when the same chip family already proved GbE.** The openXC7
   gigabit-Ethernet work (merged PRs #109–#115) exists in this ecosystem; the
   tern_tc chain still runs over 1.14 Mbaud serial. Moving the receipt stream
   to the Ethernet path is the single biggest wall-clock lever.
3. **Model capability, honestly:** 9M params, val bpb 0.611 after fine-tune,
   output is one syntactically clean line (`'\n    return 0;\n'` + EOT) —
   a length the model itself chose (its own small first), but one line is not
   a program. Scaling the corpus/prompt work matters more than any wire fix
   for anyone who wants igla-coder to actually code.
   *Measured, fire 32:* the corpus is NOT the reason. Replicating the
   builder's exact walk over the pinned tree (import of the sibling's own
   `functions`/`is_stub`/`norm`): 3,521 train FIM targets of which only
   2.8 % are newline-free bodies, 25.4 % single-statement style, **58.3 %
   six-plus lines**; median target 48 tokens / 157 chars; the model's actual
   6-token output sits at the **1.3rd percentile** of target length. The
   data taught multi-line; the model collapsed to the shortest well-formed
   body anyway — a training-budget (337 steps) / capacity symptom, not a
   data-mix one. Round 2's lever is steps and schedule on the SAME corpus
   shape, not corpus reshaping.
4. **One board, one node.** The tri-net story (node ids, setkey) is built for
   many nodes; every run so far is one AX7203. A second node would exercise
   the impersonation/foreign-frame paths in real hardware, not just in the
   rehearsal's fault injections.

## Options for the next loop (derived from the above; refreshed fire 13)

A. **Batched wire protocol (SETX/DOT6)** — design COMPLETE through fires 6–12:
   executable spec, generated params, BatchCell model, rehearsal runner
   (26 checks), RTL plan, fpga-cost baseline, and the testbench half —
   `tri fpga-batch-cosim`, pre-built red against the current core (fails at
   SETX #1's tag as designed; PASS is the RTL edit's gate). What remains is
   ONLY: the owner's phantom-frame pick (one of three resolutions in
   TERN_TC_BATCH_RTL_PLAN.md Risks — recommendation: model adopts aliasing),
   the core edit per the plan, cosim → PASS, reflash («да»). Model projects
   235 s vs the T35 run's 1414.5 s.
B. **Ethernet receipt path** — port the harness transport from serial to the
   proven GbE node; the receipt/verify layer stays byte-identical. E3 RX
   capture already modeled PASS in nextpnr (hold 10.9 ns); TX-hold PASS.
C. **Corpus round 2** — more steps on the SAME corpus (fire 32 exonerated
   the data mix; round 1 was 337 steps = 23.98 epochs over the 7.37 M-token
   train split), extend the round-1 run on a cheap pod, target bpb ≤ 0.55
   (stretch < 0.5) and multi-line output. Spends pod money — owner's call.
   **Pre-registered plan: `.claude/loop/round2-plan.md` (fire 33)** —
   extend mode (resume ckpt.pt, full optimizer state), target 3,370 total
   steps ≈ $5.22 new spend, hard cap 4,000 steps / $7; five stop rules,
   the two load-bearing ones being the overfit wall (240 total epochs at
   target — val rising 2 evals in a row halts) and the capacity-plateau
   verdict (tc is 77 % of the board's BRAM; a bigger model is not an
   option behind this link — a plateau is a result, not a pivot).
   *Cost memo (fire 24, from the round-1 session's recorded numbers):* round 1
   was 337 steps, val bpb 0.756 → 0.611, **$0.58 spent** of the RunPod balance
   (**$74.68 remaining** at round-1 close). The gap to target (0.611 → < 0.5)
   is roughly the whole round-1 gain again, so round 2 costs dollars, not tens
   of dollars, even with a bigger corpus and longer contexts; the binding
   constraint is training budget, not money — fire 32 measured the corpus mix
   and multi-line was taught (58 % of targets 6+ lines): more steps on the
   same corpus shape, not corpus reshaping. Corpus copies
   from round 1: `/workspace/ft_t27_8k` on the pod + `/tmp/ft_t27_8k` local.
   *Durability (fires 27–28 → derivability proven fire 29):* no builder for
   `ft_t27_8k` lives in this repo — the builder is the sibling's
   `~/igla-coder-gpu/t27_bench.py` (`fim` subcommand, no RNG, fully
   deterministic). Fire 28 kept all 92 files in the tmpcheck blob store; fire
   29 pinned the missing input: the build ran over `~/t27` at commit
   `9fec01a78` (specs subtree `dfdbec0cd938`), proven by the manifest's own
   fingerprint (86 held specs present / 44 missing) plus an exact token-count
   match, and verified end-to-end by `tri fpga-derive ft_t27_8k`: git-archive
   extract of the pinned commit + the sibling scripts + items/tokenizer pulled
   from the keep blobs → **91/92 files byte-identical**, manifest.json the lone
   exception (the builder version that wrote its `held_specs_*` keys exists
   only on the stopped pod; its train/val token counts and held list reproduce
   exactly). The corpus now has three independent lives — /tmp, the blob
   store, and a verified derivation chain — so the pod volume no longer
   matters for round 2.
   *Round-2 verdict (fire 35, 2026-09-29, per round2-plan.md §4/§5):* ran
   end-to-end (extend-resume, --tokens 220,856,320 exact per correction 2);
   stop rule §5a OVERFIT fired — val_bpb 0.6105@337 → 0.8506@2696 → 0.7288@3370,
   primary ≤ 0.55 FAILED. **Pinned model stays ROUND-1** (pre-registered judge =
   loss). The behavioral criterion round 2 was for did move: non-degenerate
   ≥2-line bodies on the 20-prompt val set 10% (r1) → 45% (r2), zero
   repetition loops in r2 vs 6 in r1 — real, but not a re-pin (post-hoc metric
   chasing; the lesson is now machinery: `tri fpga-genscore`). Round-3 lever,
   per the plan's own §7 wall: data QUANTITY (the t27 tree has grown since
   9fec01a78 — new targets instead of more epochs), decided at the next fire,
   not pre-committed. Spent $3.35 (compute ≈ $0.15 of it; rest = idle-burn
   admission), balance ≈ $71.3. Round-2 artifacts local in
   `data/checkpoints/tern_tc_t27_r2/`, evidence kept `keep:tct27_r2_verdict`;
   no TC02 export of the loser.
