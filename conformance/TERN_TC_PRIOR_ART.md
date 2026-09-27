# tern_tc: competitor and prior-art analysis (2026-09-27)

**Editor's note (read first).** A research agent compiled this survey on
2026-09-27, and it is kept as written below this note. Its external figures
were not re-checked, except for the CP2102N datasheet, which was fetched and
read directly (Rev. 1.5, PDF sha256 prefix `32fbab0ba17f394a`). The datasheet
confirms three points:

- a 512-byte receive buffer (section 1);
- "Handshaking is required at high baud rates (greater than 1 MBaud) to avoid
  receiver overrun" (section 4.3.9, which also names "CP2102N placement on the
  physical USB device tree" as a factor in throughput);
- RTS watermarks of 448 and 384 bytes (section 4.3.7).

Since this survey was written, two pre-registered runs used that buffer size
(`TERN_TC_LAYER_RECEIPTS.md`, rerun step 3). Window 26 (494 bytes in flight)
passed and window 30 (570 bytes) slipped.

Two corrections to the text below:

- **What the MAC covers.** It is not unverified. The harness recomputes the
  tag over `receipt_preimage(op, nonce, w, x, y, node)`, so every tag binds the
  job's operands, nonce and result.
- **The 403,200 figure is compared to a host reference.** Every row is checked
  bit-exact against an oracle computed from the model's int8 weights (`rows
  bit-exact : 33792/33792`). The MAC sits on top of that check and does not
  replace it.


Scope: tern_tc = 6.45M ternary weights / 42 matrices; 32-trit dot-product jobs on an ALINX AX7203 (XC7A200T), openXC7 flow, UART 1,144,744 baud via CP2102N, SipHash-2-4 receipt per job; 403,200/403,200 receipts verified, ~4,700 jobs/s, 0 DSP.
Derived (my arithmetic, not measured): 4,700 jobs x 32 MAC ~ 150k ternary MAC/s ~ 0.3 MOPS. 6.45M/32 ~ 201,600 jobs per full pass, so ~43 s per token if every weight crosses the link once per token. 403,200 = 2 x 201,600, i.e. two full passes.
UNVERIFIED = not confirmed from a primary source in this pass. Local notes = the owner's own skill and repo files, not a primary source.

## A. Ternary / 1.58-bit LLM inference on FPGA and low-end hardware

| Name | What | Numbers | Source |
|---|---|---|---|
| TeLLMe v1 | Ternary LLM on AMD KV260; 1.58-bit weights, 8-bit activations | up to 9 tok/s over 1,024-token context; 7 W; prefill 0.55-1.15 s for 64-128-token prompts | https://arxiv.org/abs/2504.16266 |
| TeLLMe v2 | Same board, URAM weight buffering; Vitis HLS 2024.1 + Vivado, 250 MHz | up to 25 tok/s decode, 143 tok/s prefill, <5 W, TTFT 0.45-0.96 s; board $248 | https://arxiv.org/abs/2510.15926 |
| TerEffic | Ternary LLM on Alveo U280; LUT-only TMat core; Vivado 2023, 150 MHz | 370M model on-chip: 16,300 tok/s, 455 tok/s/W (192x Jetson Orin Nano); 2.7B with HBM: 727 tok/s at 46 W (3x A100); multi-card over QSFP28 | https://arxiv.org/abs/2502.16473 |
| FlightLLM (FPGA'24) | LLaMA2-7B on U280 / Versal VHK158; DSP-based sparse chain | 6.0x energy efficiency vs V100S; 1.2x A100 throughput (VHK158); TerEffic quotes 55 tok/s at 45 W | https://arxiv.org/abs/2401.03868 |
| TENET | Ternary LUT accelerator with FPGA and ASIC prototypes | 4.3x (FPGA) / 21.1x (ASIC) energy efficiency vs A100 | https://arxiv.org/abs/2509.13765 |
| ELiTeFormer | Ternary transformer on VCK5000 (Versal); HLS | 0 DSP; throughput not extracted (UNVERIFIED) | https://arxiv.org/abs/2607.03652 |
| TernaryCore | Open ternary MAC for Arty A7-100T (Artix-7) + Tang Nano 9k; MicroBlaze/Vivado; CERN-OHL-S | ~81 LUT / 32 FF per MAC, 0 DSP; 768x768 projection in 5.32M cycles vs 19.5M on soft CPU (3.67x); "Verification PASS" on Arty A7 (2026-07-25) over UART; 40 GOPS is a target, not a measurement | https://github.com/Ternarycore/ternarycore |
| Ando & Nakashima | BitNet on a CGLA overlay, FPGA prototype at 145 MHz | 2.52 tok/s | https://arxiv.org/abs/2609.27453 |
| T-ACE (ICS'26) | Ternary accelerator, FPGA prototype, 5-trit unpacker | figures not extracted (UNVERIFIED) | https://dl.acm.org/doi/10.1145/3797905.3807877 |
| T-MAC (EuroSys'25) | LUT-based mixed-precision GEMV on CPUs | BitNet-b1.58-3B: 30 tok/s on 1 core, 71 tok/s on 8 cores (M2 Ultra); 11 tok/s on Raspberry Pi 5 | https://arxiv.org/abs/2407.00088 |
| bitnet.cpp / BitNet b1.58 2B4T | Official ternary CPU kernels (TL, I2_S) and 2B ternary model | up to 6.25x over full precision, 2.32x over low-bit baselines | https://arxiv.org/abs/2502.11880 , https://arxiv.org/abs/2504.12285 |
| LUT Tensor Core (ISCA'25) | LUT-based low-bit mpGEMM hardware (software-hardware co-design) | 1.44x compute density and energy efficiency over prior LUT accelerators | https://arxiv.org/abs/2408.06003 |

Toolchain: every FPGA result above uses AMD Vivado or Vitis HLS. None uses yosys/nextpnr. TernaryCore's Tang Nano toolchain is UNVERIFIED.
Output verification: no work I read authenticates individual outputs. They report model accuracy or benchmark numbers. TernaryCore checks element-by-element agreement with a CPU reference.

## B. Verifiable / attested inference, and where a per-job keyed MAC sits

| Name | What | Numbers | Source |
|---|---|---|---|
| zkLLM (CCS'24) | Zero-knowledge proof of a full LLM inference | 13B model: proof in <15 min, proof <200 kB | https://arxiv.org/abs/2404.16109 |
| EZKL | zkML toolkit (Halo2) | 65.88x faster proving than RISC Zero, 2.92x faster than Orion, on small models | https://blog.ezkl.xyz/post/benchmarks/ |
| TOPLOC | Locality-sensitive hash commitments over activations | 258 B per 32 tokens (vs 262 KB raw); detects model, prompt or precision swaps | https://arxiv.org/abs/2501.16007 |
| Verde + RepOps (Gensyn) | Refereed delegation; bitwise-reproducible operators | correct if at least one provider is honest | https://arxiv.org/abs/2502.19405 |
| NVIDIA H100 CC | GPU TEE: on-die root of trust, measured boot, signed attestation report, encrypted bounce buffers, with SEV-SNP/TDX VMs | qualitative | https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/ |
| ShEF | FPGA TEE: secure boot and remote attestation of the loaded design | qualitative | https://arxiv.org/abs/2103.03500 |
| Starbleed (USENIX Sec'20) | Full break of 7-series bitstream encryption through the configuration interface (possibly remote) | affects all 7-series, including XC7A200T; AMD advisory 73541 | https://www.usenix.org/conference/usenixsecurity20/presentation/ender |
| Proof-of-Learning / spoofing | Training-transcript proofs; later shown spoofable | qualitative | https://arxiv.org/abs/2103.05633 , https://arxiv.org/abs/2208.03567 |
| SipHash (INDOCRYPT'12) | Short-input PRF/MAC: 128-bit key, 64-bit output | "an attacker who blindly tries 2^s tags will succeed with probability 2^(s-64)" | https://eprint.iacr.org/2012/351 |

What the tern_tc receipt proves:
- The reply was produced by some holder of the per-node 128-bit key.
- The reply was not altered on the wire; a blind forgery succeeds with probability about 2^-64 per try.
- It is bound to its job if the MAC input covers the job id/nonce and the operands. What the MAC covers is UNVERIFIED; if a nonce is missing, replays are possible.

What it does not prove:
- That the FPGA computed it. The key is symmetric, so the host (or anything holding the key, such as a software simulator) can mint valid receipts. A third party cannot tell them apart.
- Which bitstream ran. The 7-series has no measured boot or attestation. DNA_PORT reads zeros under openXC7 (local notes), so identity is a configured id, not silicon.
- Key secrecy. The key lives in fabric SRAM, is loaded over JTAG, and is lost on reflash (local notes). JTAG readback protection under openXC7 is UNVERIFIED. Even encrypted 7-series bitstreams are breakable (Starbleed).
- Correctness. A wrong sum under a valid tag still verifies. Because a 32-trit dot product is exact integer arithmetic, the host can recompute it bit-exactly for ~32 ops. That recomputation, not the MAC, is the correctness check.

Position: a MAC gives authenticated transport from a keyed endpoint. On the verification ladder it sits below TEE attestation (H100 CC, ShEF), which proves what code ran, and far below zk proofs, which prove the computation itself. Its advantage over TOPLOC and Verde is that ternary integer results need no LSH tolerance and no RepOps to be compared bit-exactly.

## C. Number formats on FPGA

| Name | What | Numbers | Source |
|---|---|---|---|
| Walters 2016, LUT soft multipliers | Single-cycle multipliers on Virtex-7 XC7VX330T-3 (same 6-LUT fabric as Artix-7), Vivado 2014.4 | LogiCORE: 8x8 = 72 LUT, 16x16 = 280, 32x32 = 1,089; proposed: 8x8 = 36 LUT (3.594 ns), 16x16 = 136, 32x32 = 528 | https://www.mdpi.com/2073-431X/5/4/20 |
| PACoGen (IEEE Access 2019) | Parameterised posit add/mul/div generator; Virtex-7 xc7vx330t and 15 nm ASIC; pipelined (32,6) uses DSP48E/BRAM | LUT tables are images: UNVERIFIED | https://ieeexplore.ieee.org/document/8731915 , https://github.com/manish-kj/PACoGen |
| Takum codec (Hunhold 2024) | VHDL takum encoder/decoder | up to 38% lower latency and 50% fewer LUTs than the best posit codecs | https://arxiv.org/abs/2408.10594 |
| Owner's own takum/posit runs | yosys/nextpnr on XC7A200T (local notes) | takum16 817 LUT + 57 BRAM; takum32 10,967 LUT + 84 BRAM when clocked; regime decoder: posit 438 LUT, takum 40, fixed field 0 | local notes (not primary) |
| MX on FPGA (Samson et al. 2024) | First open-source FPGA implementation of OCP MX arithmetic (MXFP4 = E2M1, block of 32) | per-format LUT counts not extracted: UNVERIFIED | https://arxiv.org/abs/2407.01475 |
| LNS beyond base-2 (2021) | Low-precision LNS in which the base is a free parameter; add/sub in logic, not ROM | base choice changes error and area; "no one base which gives the global optimum" | https://arxiv.org/abs/2102.06681 |
| Bitwidth-specific LNS (2025) | Piecewise-linear log-add for 12-bit LNS MAC | up to 32.5% less area, 53.5% less energy vs fixed-point MAC | https://arxiv.org/abs/2510.17058 |
| L-Mul FP8 on FPGA (2024) | Approximate FP8 multiplier from UltraScale LUT and carry primitives | resource figures not extracted: UNVERIFIED | https://arxiv.org/abs/2412.18948 |
| Golden Ratio Encoder (Daubechies et al., IEEE Trans. IT 2010) | beta-encoder with beta = phi for A/D conversion; tolerant of imprecise components | qualitative; robustness follow-up by Ward | https://arxiv.org/abs/0809.1257 , https://arxiv.org/abs/0806.1083 |
| Z[phi] / base-phi / Fibonacci-coded ML arithmetic in hardware | Searched Google and arXiv in this session | nothing found beyond the golden-ratio ADC and non-base-2 LNS; this negative result is UNVERIFIED | none |

## D. Host-link transports for FPGA compute nodes

| Name | What | Numbers | Source |
|---|---|---|---|
| CP2102N (datasheet Rev. 1.5) | USB-UART bridge on the AX7203 | 512 B RX and 512 B TX buffers (s.1); 300 baud to 3 Mbaud; RTS deasserts at 448 B, reasserts at 384 B, sends at most 2 bytes after CTS drops (s.4.3.7); "Handshaking is required at high baud rates (greater than 1 MBaud) to avoid receiver overrun" (s.4.3.9); typical >450 kB/s at 3 Mbaud with hardware handshaking, >330 kB/s with XON/XOFF | https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf |
| tern_tc link as run | 8N1 at 1,144,744 baud, 24 B request | ceiling 4,770 jobs/s; 4,716/s measured at window 24 (98.9%); window 64 loses bytes (local notes) | local notes |
| FT232H | USB 2.0 HS bridge | sync 245 FIFO up to 40 MB/s; async 245 up to 8 MB/s; UART up to 12 Mbaud; 1 KB buffers UNVERIFIED (datasheet PDF returned 403). On the AX7203 it is wired for JTAG only (local notes) | https://ftdichip.com/products/ft232hq/ |
| FT601 | USB 3.0 to 32-bit sync FIFO | burst up to 400 MB/s; 16 kB FIFO RAM; FMC module UMFT601X-B | https://ftdichip.com/products/ft601q-b/ |
| verilog-ethernet (Forencich) | 1G/10G/25G MAC plus UDP/IP/ARP stack; UDP echo examples for Arty A7 (XC7A35T) and Nexys Video (XC7A200T) | deprecated, superseded by fpganinja/taxi; examples target Vivado; building under openXC7 is UNVERIFIED | https://github.com/alexforencich/verilog-ethernet |
| LiteEth (EnjoyDigital) | MII/RMII/GMII/RGMII on 7-series; MAC, ARP/ICMP/UDP/DHCP, Etherbone, UDP streaming; BSD-2 | achieved rates and openXC7 builds UNVERIFIED | https://github.com/enjoy-digital/liteeth |
| Owner's GbE on openXC7 | Open-flow Gigabit Ethernet on Artix-7 via openXC7 PRs #109-113 and #115 | owner claim, UNVERIFIED here; per a local scan it is not in the current node bitstream (node is UART-only) | local notes |

On the window-64 loss (hypothesis, not established): the line runs above the datasheet's 1 Mbaud handshaking threshold, apparently without RTS/CTS. Loss that appears at window 64 but not at window 24 points to a FIFO overrun somewhere in the path, not a baud mismatch. Which FIFO it is (CP2102N 512 B, the FPGA's RX FIFO, or host USB latency) is not isolated; whether the AX7203 routes RTS/CTS to the FPGA is UNVERIFIED. Scale of the headroom: at the same 24 B per job, 3 Mbaud with handshaking would give ~12.5k jobs/s, sync FIFO at 40 MB/s ~1.6M jobs/s, and 1 GbE ~5M jobs/s before packet overhead (all derived).

## Where this project is weaker (ranked)

1. **Throughput and scale, by orders of magnitude.**
   - About 150k MAC/s, or ~43 s/token derived, against 9-25 tok/s for TeLLMe on a $248 KV260 at <=7 W, and 16,300 tok/s for TerEffic.
   - Only the 32-trit dot products run on the FPGA; the rest of the LLM runs on the host.
   - TeLLMe and TerEffic run whole models on the fabric.
2. **Link-bound design: the fabric is mostly idle.**
   - Each job sends 24 B over the link for 32 MACs, so jobs/s is set by the baud rate, not by the logic.
   - Weights appear to stream per job, whereas competitors keep weights on chip (URAM/BRAM/HBM).
   - 6.45M trits packed 5 per byte is ~10.3 Mbit, below the XC7A200T's ~13.1 Mbit of BRAM (DS180 figure, UNVERIFIED this session), so full weight residency looks feasible.
3. **The link runs outside the datasheet's operating guidance.**
   - 1.144 Mbaud without handshaking is above the CP2102N's stated 1 Mbaud limit, and window 64 loses bytes.
   - The baud comes from the uncalibrated CFGMCLK (~68.7 MHz / 60, local notes), so reproducing it on another board is not guaranteed.
4. **"Verified" means MAC-valid, not computed correctly on this bitstream.**
   - A symmetric key gives no third-party verifiability and no bitstream attestation.
   - The key sits in SRAM, silicon identity reads as zeros, and 7-series bitstream security is broken (Starbleed).
   - The real correctness check is cheap bit-exact recomputation. The 403,200 figure should say whether results were also compared to a host reference.
5. **Nearest open competitor already has Artix-class ternary hardware results.**
   - TernaryCore has hardware results on Artix-7 (Arty A7-100T) with CPU cross-checking, a public repo and a TRETS citation (publication status UNVERIFIED).
   - tern_tc has no peer-reviewed or preprint write-up of the hardware run (none found).
6. **The TNF/GF paper's hardware basis is thinner than its comparison set.**
   - Its LUT counts are synthesis results, not board measurements.
   - A local scan in this session reports that TNF/BNF exist only as Python reference models and that the TNF cost sweep has not been run. The provenance of any TNF LUT numbers should be checked.
   - Posit and takum baselines in the literature come from Vivado or ASIC flows. A fair comparison needs both sides on the same flow; the owner's own guard says to claim no FPGA decode advantage.
   - Non-base-2 LNS (2021) already treats the number base as a design parameter.

## Where it is genuinely different or ahead (defensible only)

1. **Open toolchain on real hardware.**
   - A ternary compute node built entirely with openXC7 (yosys + nextpnr-xilinx), with a clean 403,200-job hardware run.
   - Every FPGA ternary-LLM result found here (TeLLMe, TerEffic, FlightLLM, ELiTeFormer, TernaryCore) depends on Vivado or Vitis HLS.
2. **Per-output authentication.**
   - No surveyed FPGA LLM accelerator authenticates individual results. tern_tc tags each job, at 2^-64 blind-forgery odds per try.
   - This is transport and origin integrity, not attestation, and should be described that way.
3. **Exactness makes checking cheap and sound.**
   - Ternary integer dot products allow bit-exact spot-check recomputation.
   - GPU-side schemes need LSH tolerance (TOPLOC) or special reproducible operators (Verde/RepOps).
   - Combining a MAC receipt with random recomputation is a simple, sound audit that float pipelines cannot match as cheaply.
4. **0 DSP on a low-cost Artix-7** is shared with TernaryCore and TerEffic's LUT-only core. It counts as ahead only when paired with point 1, not on its own.
5. **Z[phi] / GFTernary {-phi,0,+phi} arithmetic.**
   - No hardware prior art was found for phi-based number formats in ML arithmetic. The closest are golden-ratio ADC encoders and non-base-2 LNS.
   - Novelty is plausible but the search was narrow (UNVERIFIED negative), and per the owner's own guard, multiplier-freedom must not be credited to the format.
