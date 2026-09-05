# Trinity-FPGA Literature & Landscape Scan (2024–2026)

**Author:** Agent S (Specs/Standardization) + Scholar scan
**Date:** 2026-07-14
**Scope:** Six research axes relevant to Trinity — number formats, open-source FPGA toolchains, FPGA FP arithmetic, VSA/HDC hardware, HSLM/attention on FPGA, DePIN.
**Method:** arXiv + F4PGA/openXC7 primary sources, cross-checked against Trinity's own catalog (`fpga/`, EPIC #199 Tier-E 71/83, `LOOP_REPORT_2026_07_03_takum64_routing.md`).

> **Read `COMPETITIVE_LANDSCAPE_2026-08-11.md` alongside this.** This scan counts
> 32 mentions of posit and 21 of takum against 2 of MXFP4 and none of NVFP4 — it
> surveys the opposition we win against, not the one that threatens us. The
> companion note covers MXFP4/NVFP4, MR-GPTQ (ICLR 2026), HiFloat4, SharQ and
> SOAR, and states which of our results survive contact with them.

---

## TL;DR — Three findings that change the strategy

1. **The single most important paper is Hunhold, "Tekum" (arXiv:2512.10964, Dec 2025).** It is a *balanced-ternary tapered-precision* number format — i.e. it occupies the **exact intersection of Trinity's two core theses** (ternary + float). It is published, peer-track (CoNGA/ARITH community), and from the same author who already beat posits with "takum." Trinity's "ternary + φ-ratio float" framing is no longer unoccupied territory; **Trinity must either (a) differentiate GoldenFloat from tekum with a concrete, measured advantage, or (b) reposition as the FPGA-silicon-proof catalog (which it already uniquely is).**

2. **The dominant LLM-on-FPGA paradigm has crystallized around BitNet b1.58 ternary weights** (arXiv:2402.17764) with a now-mature accelerator lineage: **TeLLMe → TeLLMe v2 → PD-Swap → BitROM → ELiTeFormer** (2025–2026). These do *exactly* what HSLM-on-FPGA aims at — table-lookup ternary matmul, no-DSP, edge power budgets. Trinity's HSLM is now competing in a crowded, well-funded lane rather than an open one.

3. **Trinity's actual moat is not any single format — it is the "format catalog × open-source-silicon proof" infrastructure.** Nobody else is proving 83 number formats (posit, takum, decimal, GoldenFloat, TF3, …) through *bit-exact decode + compute on openXC7*. That catalog + the truncation-analysis methodology (`LOOP_REPORT_2026_07_03`, 4 decode templates) is the genuinely novel, citable artifact. The literature scan below should be read with that reframing in mind.

---

## 1. Number Formats — GoldenFloat & alternatives

### 1.1 Key papers

| # | Title | Authors | Venue / Year | arXiv | Key finding |
|---|-------|---------|--------------|-------|-------------|
| 1 | **Beating Posits at Their Own Game: Takum Arithmetic** | L. Hunhold | CoNGA 2024 | 2404.18603 | Tapered-precision *logarithmic* format; constant asymptotic dynamic range; matches/beats posits, fixes posit issues at large magnitudes. 72pp formal treatment. |
| 2 | **Design and Implementation of a Takum Arithmetic Hardware Codec** | L. Hunhold | cs.AR 2024 (v4 Nov 2025) | 2408.10594 | VHDL codec for linear+LNS takum. **On FPGA: −38% latency, −50% LUTs vs best posit codecs.** Direct competitor to any GF-HW. |
| 3 | **Tekum: Balanced Ternary Tapered Precision Real Arithmetic** | L. Hunhold | cs.ET 2025 | 2512.10964 | Tapered precision **for balanced ternary logic**. "In many respects outperforms posits and takums." **Collides head-on with Trinity's ternary thesis.** |
| 4 | **Microscaling Data Formats for Deep Learning** | Rouhani, Zhao, … (OCP consortium: AMD/Arm/Intel/Meta/MS/NVIDIA/QCOM) | OCP 2023 | 2310.10537 | Defines the **MX** standard (block-floating-point with shared per-block scale). The de-facto industry 8/6/4-bit format. First sub-8-bit LLM training. |
| 5 | **Nanoscaling (NxFP)** — NanoMantissa, Adaptive Microexponents, Code Recycling | Lo, Wei, Brooks (Harvard) | cs.AR 2024 | 2412.19821 | Fixes MX's <6-bit outlier problem; +0.64 perplexity vs MXFP4, −16% footprint. |
| 6 | **MX+: Pushing the Limits of Microscaling Formats for LLM Serving** | Lee et al. | MICRO 2025 | 2510.14557 | Repurposes outlier exponent field as extended mantissa. Beats MXFP4 at near-zero cost. |
| 7 | **VMXDOTP / MXDOTP** — RISC-V Vector ISA for MX | Wipfli, İslamoğlu, …, Benini (ETH/Bologna) | DATE/ASAP 2025/2026 | 2603.04979 / 2505.13159 | First RISC-V MX ISA extensions. 97% utilization, 843 GFLOPS/W (MXFP8) @ 12nm. Hardware is being standardized around MX. |
| 8 | **AetherFloat: Block-Scale-Free Quad-Radix FP for AI Accelerators** | K. Morisaki | cs.AR 2026 | 2603.08741 | "Design a float from first principles" — exactly GoldenFloat's premise. Quad-radix (base-4) scaling + explicit mantissa ⇒ **−33% area, −22% power, −12% delay** vs IEEE MAC. Eliminates AMAX block-scale logic. **Has VLSI numbers Trinity lacks.** |
| 9 | **Shedding the Bits: Minifloats on FPGAs** | Aggarwal, Damsgaard, Pappalardo, Blott, Mitra | FPL 2024 | 2311.12359 | Custom **FPGA MAC library for FP3–FP8** (minifloats). Sweep vs INT. Shows minifloats win for ViT. **Closest prior art to Trinity's parameterized GF MAC.** |
| 10 | **FP8 Formats for Deep Learning** | Micikevicius et al. (NVIDIA/ARM/Intel) | 2022 | 2209.05433 | The OCP FP8 (E4M3/E5M2) standard paper. |
| 11 | **FP8 Quantization: The Power of the Exponent** | Kuzmin et al. (Qualcomm AI Research) | 2024 | 2208.09225 | Outlier severity drives optimal exponent-bit choice — i.e. *there is no universally best exp/mant split*. |
| 12 | **μnit Scaling: Simple and Scalable FP8 LLM Training** | Narayan et al. | ICML 2025 | 2502.05967 | FP8 training with no dynamic scaling, +33% faster, 1B–13B models. |
| 13 | **GSQ-Tuning: Group-Shared Exponents Integer** | Zhou et al. | ACL 2025 Findings | 2502.12913 | Integer-only on-device fine-tune; **−5× power, −11× area vs FP8** at same perf. |
| 14 | **Spectral Methods (FFT) in OFP8/Bfloat16/Posit/Takum** | Hunhold & Gustafson | 2025 | 2504.21197 | Takum follows posit closely; OFP8 unsuitable for general compute. |
| 15 | **Evaluation of Bfloat16, Posit, Takum in Sparse Solvers** | Hunhold & Quinlan | ARITH 2025 | 2412.20268 | "Takum arithmetic exhibits exceptional stability, even at low precision." |

### 1.2 Relation to Trinity / GoldenFloat

- GoldenFloat (GF4…GF32) is, mechanically, an **IEEE-754-style float family** whose only distinguishing design rule is the **φ-ratio selection criterion** (exp/mant → 1/φ ≈ 0.618). The *encoding* is conventional; the *justification* is aesthetic/geometric.
- The field has moved on two axes that GoldenFloat does not currently occupy:
  - **Tapered precision** (posit → takum → tekum): variable precision near unity. This is a structurally different and demonstrably superior family for general-purpose compute (ARITH 2025, CoNGA 2024). Takum already has a published FPGA codec beating posits by 38/50%.
  - **Block scaling** (MX/NxFP/MX+): the industry has standardized on per-block shared exponents for ML. GoldenFloat has no block-scaling story.

### 1.3 Novelty assessment

- **The φ-ratio criterion itself is not novel as a numerical claim.** There is no evidence in the literature that exp/mant ≈ 0.618 yields measurably better accuracy/dynamic-range than alternatives; FP8-Quantization (Kuzmin) shows the optimal split *depends on outlier distribution, not a universal constant*. The "φ² + 1/φ² = 3" invariant is algebraically true but is a property of φ, not an accuracy theorem for floating point.
- **What IS novel and defensible:** Trinity's catalog-level hardware proof of *many* formats on open-source silicon. No other group publishes LUT/latency/route-yield numbers for 71+ formats on openXC7.

### 1.4 Risks (what could supersede)

1. **Takum (2408.10594)** — already beats posits on FPGA; if the takum32/64 decoders Trinity is building (Tier-E) succeed, Trinity may end up *validating a competitor's format*. Mitigation: position Trinity as the independent silicon proving ground, cite Hunhold correctly (Trinity already does, arXiv:2404.18603 — good).
2. **Tekum (2512.10964)** — pre-empts the "ternary float" niche. Trinity should read this paper immediately and produce a documented GoldenFloat-vs-tekum comparison (accuracy, dynamic range, LUT cost) *before* claiming ternary-float novelty externally.
3. **MX / OCP standard** — if Trinity targets ML workloads, GF without block scaling will be perceived as non-standard. Consider a "GF-MX" hybrid (φ-structured elements inside MX blocks) as a genuine novel niche.
4. **AetherFloat (2603.08741)** — another "first-principles float" with concrete silicon area numbers. Sets the bar for any GoldenFloat VLSI claim.

---

## 2. Open-Source FPGA Toolchains (openXC7 / F4PGA / prjxray)

### 2.1 Current state (verified)

- **F4PGA** ("the GCC of FPGAs", CHIPS Alliance workgroup) targets Xilinx 7-Series, Lattice iCE40/ECP5, QuickLogic EOS-S3. Pipeline: Yosys → nextpnr-xilinx / VPR → FASM → fasm2frames → xc7frames2bit.
- **Project X-Ray bitstream documentation status** (F4PGA official, `status.html`):
  - Xilinx 7-Series: Logic tiles ✅, Clock ✅, IO ✅, Routing ✅.
  - **Block RAM = "Partial".** **DSP = "Partial".** **Hard Blocks = "Partial".**
- **openXC7** (Trinity's chosen flow, `regymm/openxc7` Docker, 5.72 GB) wraps Yosys + nextpnr-xilinx + prjxray-db for Artix-7. Trinity's `TOOLCHAIN_COMPARISON.md` reports 100% synth success on XC7A100T, ~165 MHz on a 30-CLB heartbeat. Trinity's `synth.sh` runs `synth_xilinx -flatten -abc9 -nobram`.

### 2.2 Limitations that directly constrain Trinity (from Trinity's own `LOOP_REPORT_2026_07_03` + `COMMON_PITFALLS.md`)

| Limitation | Source | Impact |
|---|---|---|
| `synth_xilinx -nodsp` required | DSP48E1 inference breaks routing on this part | **All FP MAC must be LUT-only — no DSP.** This is the central design constraint and the reason "zero-DSP MAC" is Trinity's K-agent pitch. |
| `-flatten` hangs ≥3 h on BRAM+wide-logic | commits 92eafad5, d08d9878 | Limits flatten-based optimization on wide datapaths |
| **Wide *multiplies* are the openXC7-killer** | takum64 119-bit & 140-bit products fail routing across 32 seeds | Any format with transcendental decode (exp/log) must use truncation (Mitchinson–Smith) or table decomposition |
| Wide *tables* route fine | decimal128 (336-bit) routes | Prefer BRAM-LUT over carry-chain multiplies |
| Placer `heap` ≫ `sa` for wide datapaths | Trinity empirical | nextpnr seed/strategy constraints |
| BRAM only "Partial" in X-Ray | F4PGA status | Constrained BRAM inference; Trinity uses explicit 65 536-entry tables |
| Docker Hub reliability | HTTP 500 killed 6-hour jobs | Trinity added 6× backoff retry across 85 workflows |

### 2.3 Relation to Trinity / Novelty

- Trinity is **the most aggressive known user** of openXC7 for non-trivial datapaths (83 formats, decode + compute). The accumulated know-how (4 proven decode templates: algebraic, table-2^x, transcendental-exp-via-tables, truncated-multiply) is a real, citable contribution.
- The native-Zig **FORGE** toolchain attempt (0/23 success, documented bugs in LUT INIT / FFMUX / OLOGIC) is, by Trinity's own assessment, not viable. This matches the broader reality: prjxray's reverse-engineered DB is hard to reproduce from scratch.

### 2.4 Risks

1. **AMD/Xilinx litigation or bitstream-encryption changes** could disrupt prjxray (low probability, high impact).
2. **nextpnr-xilinx is less mature than VPR**; for large designs Vivado remains far superior. Trinity's 100% rate is on small designs — scaling to full HSLM attention blocks is unproven.
3. **The "Partial" DSP status** caps achievable GFLOPS. Any claim of competitive ML throughput on Artix-7 vs. an ASIC/GPU flow must be hedged.
4. **RHemann / RapidWright / LLVM-CIRCT** open flows are advancing; a competitor open flow could overtake openXC7.

---

## 3. FPGA Floating-Point / Alternative-Format Arithmetic

### 3.1 Key papers (FPGA-specific)

| # | Title | Authors | Year | arXiv | Key finding |
|---|-------|---------|------|-------|-------------|
| 1 | **PERI: A Posit Enabled RISC-V Core** | Tiwari, Gala, Rebeiro, Kamakoti | 2019 | 1908.01466 | Posit FPU on **Artix-7-100T** (Trinity's exact board): **3507 LUTs, 1294 regs, 100 MHz.** The canonical posit-on-Trinity-board baseline. |
| 2 | **Evaluation of POSIT Arithmetic with Accelerators** | Nakasato, Murakami, Kono, Nakata | HPCAsia 2024 | 2401.14117 | Posit(32,2) on FPGA+GPU; Cholesky/LU; +0.5–1.0 digit accuracy vs FP32 near unity. 0.043–0.076 GFLOPS/W. |
| 3 | **EULER-ADAS: SIMD Logarithmic-Posit Engine** | Lokhande, Pilipovic, Kokane, Teman, Vishvakarma | 2026 | 2605.06875 | Bounded-regime posit + log mantissa mul. **−41% LUT, −76% delay, −72% power vs exact posit.** TinyYOLOv3 on Pynq-Z2 @ 0.29 W. |
| 4 | **Takum Hardware Codec** | Hunhold | 2024 | 2408.10594 | (see §1) −38% latency, −50% LUT vs posits. |
| 5 | **Minifloats on FPGAs** | Aggarwal, …, Blott, Mitra | FPL 2024 | 2311.12359 | Parameterized FP3–FP8 MAC on FPGA; minifloats beat INT for ViT. |
| 6 | **RedMulE / RedMule** (FP16/FP8 GEMM, PULP RISC-V) | Tortorella, Bertaccini, Benini, Rossi, Conti | 2023 | 2301.03904 | 755 GFLOPS/W FP16, 1.67 TFLOPS/W FP8 @ 22nm. Mixed-precision training. |
| 7 | **MiniFloat-NN / ExSdotp** (RISC-V ISA) | Bertaccini, Paulin, …, Benini | ARITH 2022 | 2207.03192 | 575 GFLOPS/W FP8→FP16 GEMM @ 12nm. |

### 3.2 Relation to Trinity

- Trinity's GF MAC (`t27:specs/fpga/mac.t27`, zero-DSP) is the right idea *given the openXC7 `-nodsp` constraint*. The literature baseline to beat is **PERI's 3507 LUTs @ 100 MHz on the identical Artix-7-100T** — Trinity should publish GF16-MAC numbers against this directly.
- **EULER-ADAS (2026)** is the strongest contemporary datapoint: bounded-posit + logarithmic mul gives −41% LUT. Trinity's φ-structured approach should be benchmarked against bounded-posit, not just exact posit.
- Trinity's "transcendental decode via BRAM table + Taylor correction" template is consistent with **Crdkovic/Milenkovic** (2^x via small table + degree-2 poly) cited in its own loop report — solid prior-art grounding.

### 3.3 Novelty assessment

- **Incremental.** Parameterized FP-MAC on FPGA is well-trodden (Aggarwal FPL 2024; PERI; RedMulE). Trinity's novelty is the *φ-ratio parameterization* and the *LUT-only constraint from openXC7*, not the MAC topology.
- The **catalog breadth** (83 formats) is novel; the **per-format MAC** is incremental.

### 3.4 Risks

1. **EULER-ADAS-style bounded/log-posit** may deliver more LUT savings than φ-ratio split. Run a head-to-head.
2. **DSP-unlocked flows** (Vivado, or future prjxray DSP completion) would erase Trinity's "zero-DSP" differentiator. Keep the MAC design portable to DSP48E1 for the day that arrives.

---

## 4. VSA / Vector Symbolic Architectures on Hardware

### 4.1 Key papers (2024–2026 surge)

| # | Title | Authors | Venue / Year | arXiv | Key finding |
|---|-------|---------|--------------|-------|-------------|
| 1 | **ImageHD: On-Device Continual Learning via HDC on FPGA** | Arockiaraj, Parikh, Prasanna | FCCM 2026 | 2604.21280 | FPGA HDC continual-learning dataflow on ZCU104; 40× CPU / 4.8× GPU speedup, 383× energy. Word-packed binary hypervectors. |
| 2 | **HyperX: FPGA HDC Graph Classification** | Arockiaraj, Parikh, Prasanna | CF 2026 | 2512.08089 | First end-to-end FPGA HDC graph accelerator; DPP landmark selection; minimal-perfect-hash; 6.9× CPU speedup. |
| 3 | **BiHDTrans: Binary HD Transformer** | Zhang, Liu, Shen, Wang | 2025 | 2509.24425 | Self-attention *inside* HDC; **39.4× lower latency than binary transformers on FPGA.** Directly overlaps Trinity's VSA+HSLM intersection. |
| 4 | **Efficient HDC with Modular Composite Representations (MCR)** | Angioli, Kymn, …, **Kleyko**, Olivieri | 2025 | 2511.09708 | First MCR dedicated accelerator; MCR matches binary spatter code at 4× less memory; 3 orders of magnitude speedup. **Kleyko co-author ⇒ VSA-community legitimacy.** |
| 5 | **HPVM-HDC: Heterogeneous Programming System for HDC** | Arbore, …, Adve, Rosing | 2024 | 2410.15179 | First retargetable HDC compiler (CPU/GPU/FPGA/ReRAM/PCM). Sets the "HDC programming system" agenda. |
| 6 | **ApproxHDC: Compiler-Driven Approximation Tuning** | Routh, …, Adve, Rosing | 2026 | 2606.26547 | Automated approximation search across HDC SW+HW. |
| 7 | **HyDra: SOT-MRAM VSA Macro** | Nayan, Liu, Wan, Raychowdhury, Naeemi | 2025 | 2504.14020 | Binding/permutation/similarity in SOT-CAM; 6× latency via bit-drop permutation. Non-CMOS VSA. |
| 8 | **DecoHD** | Yun, Oh, …, Imani | DATE 2026 | 2511.03911 | Decomposed HDC; ~97% fewer params; 277×/35× energy/speed vs CPU. |
| 9 | **DPQ-HD** (post-training HDC compression) | Pandey, …, Rosing | 2025 | 2505.05413 | 20–100× memory reduction, no retrain. |
| 10 | **ScalableHD** (multi-core CPU HDC) | Parikh, Prasanna | 2025 | 2506.09282 | 10× over TorchHD. |
| 11 | **Clo-HDnn / FSL-HDnn** (HDC ODL chips) | Song, Xu, …, Rosing, Kang | VLSI 2025 / 2025 | 2507.17953 / 2512.11826 | 4.66 TFLOPS/W; gradient-free continual learning silicon. |

### 4.2 Relation to Trinity

- Trinity's VSA core (`src/vsa.zig`, ternary trits {-1,0,+1}, bind/unbind/bundle, φ²+1/φ²=3 invariant) sits in a **rapidly industrializing field**. Kleyko (a central VSA theorist) is now co-authoring hardware-accelerator papers (MCR, 2511.09708) — the VSA↔hardware bridge is being formalized *without* Trinity.
- **BiHDTrans (2509.24425)** is the most direct conceptual neighbor: it puts self-attention *inside* HD computing on FPGA — i.e. it unifies Trinity's VSA and HSLM pillars. Trinity's "φ-attention" should be benchmarked against it.

### 4.3 Novelty assessment

- Trinity's **ternary VSA** (vs the dominant binary/bipolar VSA) is genuinely less explored, but **Tekum (§1) and the broader balanced-ternary revival** mean this niche is now contested too.
- The **φ²+1/φ²=3 invariant** as a *binding-algebra identity* is mathematically true but, again, is not an established accuracy/capacity theorem in the VSA literature (capacity is typically measured vs dimension D and noise). Trinity should produce a capacity curve (boundable # of bound items vs D) to substantiate the φ framing.

### 4.4 Risks

1. **HPVM-HDC / ApproxHDC (Adve & Rosing)** are building a retargetable HDC compiler stack. If Trinity's VSA stays hand-rolled Zig/Verilog, it risks being non-portable relative to a community IR.
2. **In-memory HDC (HyDra SOT-MRAM, SpecPCM, Neuro-Photonix)** will dominate energy efficiency numbers; pure-CMOS FPGA VSA cannot compete on TFLOPS/W. Trinity's pitch must stay on *open-source-silicon reproducibility*, not raw efficiency.
3. **Kleyko et al. MCR** may become the reference integer-VSA; Trinity's ternary-VSA should interop/document conversion to MCR.

---

## 5. HSLM / Attention on FPGA (low-resource)

### 5.1 Key papers — the BitNet-ternary-on-FPGA lineage

| # | Title | Authors | Venue / Year | arXiv | Key finding |
|---|-------|---------|--------------|-------|-------------|
| 0 | **The Era of 1-bit LLMs (BitNet b1.58)** | Ma, Wang, …, Wei (Microsoft) | 2024 | 2402.17764 | Every weight ternary {-1,0,1}. Matches FP16 perplexity. **Defines the paradigm Trinity's ternary thesis rides on.** |
| 1 | **TeLLMe: Ternary LLM Accelerator on Edge FPGAs** | Qiao, Chen, Zhang, Wang, Huang | 2025 | 2504.16266 | First ternary-LLM FPGA accelerator (AMD KV260). Table-lookup ternary matmul, 1.58-bit weights / 8-bit activations, fused attention. **9 tokens/s, 1024-token ctx, 7 W.** |
| 2 | **TeLLMe v2** | same group | 2025 | 2510.15926 | Adds full prefill+decode; **25 tokens/s decode, 0.45–0.96 s TTFT, 5 W.** |
| 3 | **PD-Swap: Prefill-Decode Logic Swapping via DPR** | Zhang, Chen, Qiao, Huang | 2025 | 2512.11550 | Dynamic Partial Reconfiguration to time-multiplex attention; **27 tokens/s**, +1.3–2.1× over SOTA. |
| 4 | **BitROM: Weight Reload-Free CiROM for 1.58-bit LLMs** | Zhang, Li, Ando, Yoshioka | ASP-DAC 2026 | 2509.08542 | Two ternary weights/transistor; **20.8 TOPS/W**, 4967 kB/mm². CiROM + eDRAM KV-cache. |
| 5 | **ELiTeFormer: Efficient Linear *Ternary* Transformer for FPGAs** | Agostinelli, Agostini, Tumeo | 2026 | 2607.03652 | Linear attention + ternary projections; **eliminates all multiplications via bitmasking, no DSP blocks.** 10× weight / 12.8× KV compression vs LLaMA3. VCK5000 Versal. **Closest intellectual neighbor to Trinity's HSLM-on-FPGA.** |
| 6 | **BiHDTrans** | (see §4) | 2025 | 2509.24425 | Binary HD Transformer on FPGA. |

### 5.2 Relation to Trinity / HSLM

- **This is the most crowded lane in the scan.** HSLM ("Hierarchical Sequence Language Model") on low-resource FPGA now competes with at least **five 2025–2026 accelerator papers**, all leveraging BitNet-ternary, all doing no-DSP / table-lookup ternary matmul — which is precisely Trinity's K-agent "zero-DSP MAC" thesis.
- **ELiTeFormer (2607.03652)** is the sharpest collision: ternary + FPGA + no-DSP + attention, with concrete MMLU (31.9%) and latency numbers.

### 5.3 Novelty assessment

- **HSLM as a model architecture** is not, on its own, novel relative to this lineage unless it introduces a structurally different attention (Trinity's "φ-attention" claim). That φ-attention claim must be formalized and benchmarked against linear attention (ELiTeFormer) and HD-attention (BiHDTrans).
- Trinity's **hierarchical** framing could be a differentiator *if* it means something concrete (multi-resolution sequence modeling) rather than a branding term.

### 5.4 Risks (highest of all six axes)

1. **Obsolescence risk is severe.** TeLLMe v2 / PD-Swap / ELiTeFormer already publish the numbers (tokens/s, W, TTFT) that HSLM would need to beat. Without a published benchmark against these, HSLM claims will not land.
2. **BitNet b1.58 supply chain**: Microsoft controls the reference models. Trinity's HSLM should stay model-agnostic (able to host any b1.58-style model).
3. **Versal/ACAP (VCK5000)** is becoming the preferred FPGA platform for this work (HBM, AIE). Artix-7 XC7A100T/200T is resource-starved by comparison; Trinity's edge-low-power framing is the only sustainable pitch.

---

## 6. DePIN (Decentralized Physical Infrastructure) & verifiable compute

### 6.1 Key papers / landscape

| # | Title | Authors | Year | arXiv | Key finding |
|---|-------|---------|------|-------|-------------|
| 1 | **Optimistic TEE-Rollups: Verifiable Generative AI Inference on DePIN** | Chan, Ding, Chen, Wu, Zhang, Tian | 2025 | 2512.20176 | Frames the **"Verifiability Trilemma"** (integrity vs latency vs cost). ZKML is O(k·NlogN) — infeasible for billion-param models. Proposes TEE (H100 confidential compute) + optimistic fraud proofs + stochastic ZK spot-checks. 99% of centralized throughput at +$0.07/query. |

### 6.2 Broader context (not arXiv-indexed, but industry-defining)

- **ZKML** (EZKL, Modulus Labs) remains the cryptographic-integrity gold standard but is bottlenecked by proving cost — the central reason DePIN+AI verification is hard.
- **opML / optimistic approaches** (Cartesi, AltLayer) avoid ZK cost but impose dispute windows.
- **TEE-based** (Super Protocol, Marlin, Attestation-based) is the pragmatic middle: hardware attestation binds execution to a model hash.

### 6.3 Relation to Trinity

- Trinity's DePIN/Y-agent ("tri depin status/nodes/fitness", `deploy/contracts/`) intersects a field where **FPGA has a genuine, under-exploited advantage: deterministic, low-power, attestable hardware**. An Artix-7 running a fixed ternary-LLM bitstream is a *physically verifiable* compute node in a way a GPU in a TEE is not — the bitstream is the attestation.
- This is arguably Trinity's **most defensible novel niche**: DePIN-verified FPGA inference, where the open-source-silicon constraint *is* the trust anchor (no proprietary Vivado blob in the trust path if the openXC7 flow is reproducible end-to-end).

### 6.4 Novelty assessment

- **Potentially the strongest novelty in the whole project**, *if* framed correctly: "reproducible open-source FPGA bitstream = verifiable compute primitive for DePIN." No paper in the scan occupies this.
- The risk is that "DePIN" in Trinity today reads as marketing rather than a protocol with a verifiability story comparable to OTR (2512.20176).

### 6.5 Risks

1. **ZK-ML proving-cost breakthroughs** (e.g., validium-style GPU proofs) could make TEE/FPGA attestation unnecessary.
2. **FPGA bitstream provenance**: if the openXC7 flow cannot be made *bit-for-bit reproducible* by independent parties, the trust anchor weakens. Reproducible-builds discipline is essential.

---

## 7. Cross-cutting synthesis

### 7.1 Where Trinity is genuinely novel (defend these)

1. **The format catalog × open-source-silicon proof (EPIC #199, Tier-E 71/83).** No competitor proves this many number formats on openXC7. The 4 decode templates + truncation-analysis methodology is citable.
2. **Open-source-silicon as DePIN trust anchor.** Strongest under-explored niche.
3. **LUT-only (zero-DSP) arithmetic under the openXC7 constraint.** A well-scoped engineering contribution, *provided* it is benchmarked against PERI (1908.01466) and EULER-ADAS (2605.06875).

### 7.2 Where Trinity is incremental (be honest)

1. **GoldenFloat φ-ratio criterion** — no accuracy theorem; the field (takum/tekum/MX/AetherFloat) has moved to tapered + block-scaled designs.
2. **HSLM-on-FPGA** — crowded; TeLLMe/PD-Swap/ELiTeFormer set the bar.
3. **VSA-on-hardware** — industrializing fast (HPVM-HDC, MCR, HyDra).

### 7.3 Where Trinity risks being pre-empted

1. **Tekum (2512.10964)** — ternary tapered precision. **Read this week.**
2. **ELiTeFormer (2607.03652)** — ternary transformer on FPGA, no-DSP.
3. **HPVM-HDC (2410.15179)** — retargetable HDC compiler may set the IR standard.

### 7.4 Recommended research-direction adjustments

1. **Stop claiming GoldenFloat φ-ratio as a numerical theorem** until a capacity/accuracy proof exists; reframe it as a *design heuristic* within the catalog.
2. **Publish the catalog.** A short paper "83 number formats, bit-exact decode + LUT-only compute on openXC7: a reproducible benchmark" would be immediately citable and occupies empty ground. Cite Hunhold (2404.18603, 2408.10594, 2512.10964), PERI (1908.01466), Aggarwal FPL 2024 (2311.12359).
3. **Run a head-to-head**: GoldenFloat GF16 vs takum16 vs posit(16,1) vs MXFP8 vs E4M3 — accuracy on a fixed suite (SuiteSparse-style, à la Hunhold & Quinlan ARITH 2025) + LUT/route-yield on openXC7. This is the table nobody else can fill.
4. **Formalize φ-attention** against linear attention (ELiTeFormer) and HD-attention (BiHDTrans), or drop the claim.
5. **Position DePIN-FPGA as the verifiable-compute primitive**: reproducible openXC7 bitstream = attestation. Write this up before OTR-style TEE work absorbs the niche.
6. **Read & diff vs Tekum immediately** — it is the single highest-urgency item in this scan.

---

## Appendix A — Trinity internal state cross-reference

- `t27/specs/numeric/goldenfloat_family.t27` — GF4…GF32, φ-ratio target 1/φ, GF16 primary.
- `t27/specs/numeric/gf8.t27` — GF8 [S|EEE|MMMM], exp/mant 3/4 = 0.75, φ-distance 0.132.
- `fpga/TOOLCHAIN_COMPARISON.md` — openXC7 100%, FORGE 0/23.
- `fpga/LOOP_REPORT_2026_07_03_takum64_routing.md` — Tier-E 71/83; takum64 routing unlock via 119→94 / 140→72-bit truncation; 4 decode templates; `-nodsp` constraint.
- `fpga/FORGE_COMPATIBILITY_MATRIX.md`, `fpga/COMMON_PITFALLS.md` — openXC7 limits.
- `research/goldenfloat-hw-conformance/` — HW conformance v0.1/v0.2.
- EPIC #199 — 83-format × {SW/decode-HW/compute-HW} matrix.

## Appendix B — Bibliography (arXiv IDs)

Number formats: 2404.18603, 2408.10594, 2512.10964, 2310.10537, 2412.19821, 2510.14557, 2603.04979, 2505.13159, 2603.08741, 2311.12359, 2209.05433, 2208.09225, 2502.05967, 2502.12913, 2504.21197, 2504.21130, 2412.20268, 2503.14067, 2606.26587.
FPGA toolchains: F4PGA readthedocs (status.html), prjxray-db (artix7), openXC7 (`regymm/openxc7`).
FPGA arithmetic: 1908.01466, 2401.14117, 2605.06875, 2301.03904, 2207.03192.
VSA/HDC: 2604.21280, 2512.08089, 2509.24425, 2511.09708, 2410.15179, 2606.26547, 2504.14020, 2511.03911, 2505.05413, 2506.09282, 2507.17953, 2512.11826, 2512.03394, 2412.10187, 2411.09760, 2509.26131.
HSLM/attention: 2402.17764, 2504.16266, 2510.15926, 2512.11550, 2509.08542, 2607.03652, 2506.07530.
DePIN: 2512.20176.
