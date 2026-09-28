# Loop research — weak points + competitors (2026-09-29, fire 2; competitor
# table refreshed fire 8)

Swept through BrowserOS neo (Google → arXiv/GitHub). What the field looks like
from the tern_tc/AX7203 vantage, and where this project honestly stands.
Fire-8 refresh: TeLLMe and the nicholi.ai $130-board engine added after a
re-sweep; none of the new entrants publishes receipted inference either —
the wedge below is unchanged.

## Competitors (all verified live, September 2026)

| who | what | number that matters |
|---|---|---|
| **TerEffic** (arXiv 2502.16473) | FPGA ternary LLM accelerator; fully-on-chip 370M variant + HBM 2.7B variant | ~16,300 tokens/s (370M, on-chip) |
| **Ternarycore** (github.com/Ternarycore/ternarycore, TRETS paper, CERN-OHL-S + commercial dual license) | open-source BitNet b1.58 accelerator on Arty-7 and Tang Nano; int8 attention measured on silicon; INA226 energy kit; 337 commits | a whole maintained OSS stack |
| **Ando & Nakashima** (arXiv 2609.27453, CANDAR 2026 CSA workshop) | BitNet mapped onto a CGLA ASIC via signed-int4 lanes (OP_SMA4), no BitNet-only datapath | 2.52 tok/s, 0.390 ns per s4 product at 28 nm |
| **ELiTeFormer** (arXiv 2607.03652, Agostinelli 2026) | first Transformer unifying hybrid linear attention + ternary, co-designed for FPGA | architecture-level claim |
| **VitaLLM** (arXiv 2604.27396, Lin & Chang) | dual-core (TINT ternary + BoothFlex mixed) with Leading-One-Prediction KV pruning | edge accelerator, prefill+decode |
| **Bitnet.cpp** (Microsoft) | CPU edge inference for ternary LLMs | the baseline everyone cites |
| **TeLLMe** (UCI-CORSA, FPGA 2026, ACM 3748173.3779191) | end-to-end ternary LLM prefill + decode on FPGA, course-turned-paper stack (TeLLMe_FPGA_2026 repo) | end-to-end (both phases), not just kernels |
| nicholi.ai engine (June 2026; article title says "multiply-free" — the ternary network is what needs no multipliers) | ternary engine on a $130 FPGA board, write-up with numbers | floor price point |

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
publishes "every FLOP is accounted for and the ledger is checkable".

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

## Options for the next loop (derived from the above)

A. **Batched wire protocol** — designed (fire 4) in
   `conformance/TERN_TC_BATCH_PLAN.md`: L1 batch receipts (answers, no wall
   gain alone) + L2 x-pinned dot runs (requests, 6× fewer frames, model says
   235 s vs 1414.5 s). **Both are RTL changes** — the node parser is stateless
   per frame, so the earlier "RTL unchanged" guess here was wrong and is
   retracted. Needs the owner's pick, then spec → BatchCell → rehearsal → RTL →
   reflash («да»).
B. **Ethernet receipt path** — port the harness transport from serial to the
   proven GbE node; the receipt/verify layer stays byte-identical.
C. **Corpus round 2** — bigger t27 FIM corpus (more items, longer contexts),
   fine-tune again on a cheap pod, target bpb < 0.5 and multi-line output.
