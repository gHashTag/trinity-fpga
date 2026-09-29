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
variant.

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
| nicholi.ai engine → **ternfpga** (Neumann-Labs/ternfpga, open-sourced by fire 16, 2026-09; Apache-2.0) | ternary BitNet-2B-4T batch-1 decode on a $130 Arty A7-35T, 72 commits; energy partly Vivado-derived (self-flagged), bit-exact vs golden models only | floor price point, now a maintained OSS repo — still no receipts |
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
C. **Corpus round 2** — bigger t27 FIM corpus (more items, longer contexts),
   fine-tune again on a cheap pod, target bpb < 0.5 and multi-line output.
   Spends pod money — owner's call.
   *Cost memo (fire 24, from the round-1 session's recorded numbers):* round 1
   was 337 steps, val bpb 0.756 → 0.611, **$0.58 spent** of the RunPod balance
   (**$74.68 remaining** at round-1 close). The gap to target (0.611 → < 0.5)
   is roughly the whole round-1 gain again, so round 2 costs dollars, not tens
   of dollars, even with a bigger corpus and longer contexts; the binding
   constraint is corpus quality for multi-line output, not money. Corpus copies
   from round 1: `/workspace/ft_t27_8k` on the pod + `/tmp/ft_t27_8k` local.
   *Durability (fire 27 → resolved fire 28):* no builder for `ft_t27_8k`
   exists in this repo (grep over .py/.zig/.md matches nothing outside
   .claude/loop), so the corpus lived only in /tmp (dies at reboot) and on
   the STOPPED pod (dies with the pod). Fire 28 closed the local half:
   `tri fpga-keep /tmp/ft_t27_8k ft_t27_8k` wrote all 92 files into the
   tmpcheck blob store (gitignored blobs + tracked MANIFEST.tsv rows tagged
   keep:ft_t27_8k), so `tri fpga-tmpcheck --restore` rebuilds it after a
   reboot and the audit watches it. The pod volume is still the only other
   copy — round 2 should not assume it.
