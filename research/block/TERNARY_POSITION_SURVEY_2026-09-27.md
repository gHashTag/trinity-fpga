# Where could a ternary-substrate format stand? A survey, 2026-09-27

A web survey made for the owner's question: where is TNF stronger than MXFP4 "on a ternary
substrate". **A secondary source.** A research agent read the pages. The links below were
not re-read for this note, and nothing here was measured. Tags: [PR] peer reviewed, [pre]
preprint, [press] news or vendor. Two of this project's own documents turned up in the
results (arXiv 2606.09686, trinity-memory#29). They were not used as evidence.

## What exists

**Native ternary hardware**

The ternary hardware is devices and simulations, with no ternary memory for model weights.

- Huawei CN119652311A is a ternary add/subtract-1 gate. It is an application, not granted, and
  it says nothing about neural networks.
  https://patents.google.com/patent/CN119652311A/en
- A 2025 ternary MAC shows -45 % area and -30 % power in simulation.
  https://ieeexplore.ieee.org/document/10755970/ [PR]
- The PKU carbon-nanotube 6T ternary SRAM is fabricated. Its NN was simulated from device
  curves. https://pmc.ncbi.nlm.nih.gov/articles/PMC11721562/ [PR]
- ReTern stores each trit in two binary cells. It argues that native multi-level cells are
  harder to read. https://arxiv.org/html/2506.01140 [pre]

**Ternary weights on binary memory**

Ternary weights on binary memory are packed, never stored natively.

| system | bits per weight |
|---|---|
| bitnet.cpp I2_S / TL1 / TL2 | 2.00 / 2.00 / 1.67 |
| llama.cpp TQ1_0, 5 trits in a byte | 1.6875 |
| TerEffic (FPGA, 5 in 8) | 1.6 |
| TeLLMe v2 (FPGA, 3 in 5) | 1.67 |

The entropy is 1.585 bits. Dense packing costs about 1 % over that; what it really costs is
decode and alignment. Sources:

- https://arxiv.org/html/2502.11880v1 [PR]
- https://github.com/ggml-org/llama.cpp/pull/8151
- https://arxiv.org/html/2502.16473v2 [pre]
- https://arxiv.org/html/2510.15926v2 [pre]

**27-level (3-trit) elements, or balanced-ternary floats for NN weights: none found.**

- The nearest are the 9-level Tied Trit-Planes (https://arxiv.org/abs/2608.08910 [pre]).
- Tekum is balanced-ternary tapered arithmetic, not for NN weights
  (https://arxiv.org/abs/2512.10964 [pre]).

**4-bit block formats that already beat MXFP4 on binary**

| format | bits/elt | result against MXFP4 | source |
|---|---:|---|---|
| NVFP4 (E4M3 scale per 16) | 4.5 | recovery 94.7 % vs 87.8 %, Llama-3.1-8B W4A4 (MR-GPTQ, ICLR 2026) | https://arxiv.org/abs/2509.23202 [PR] |
| AdaMX-32 | 4.25 | WikiText-2 ppl 7.10 vs 8.31, Llama-3.1-8B W+A | https://arxiv.org/html/2608.03867 [pre] |
| BlockDialect-64 | < 4.25 | ppl -0.93, LLaMA3-8B | https://arxiv.org/abs/2501.01144 [PR] |
| MX+ | 4.5 | ppl 9.54 vs 27.38, Llama-3.1-8B W+A | https://arxiv.org/html/2510.14557v1 [PR] |

MXFP4's E2M1 has +0 and -0, so it holds 15 distinct values; RaZeR reuses the spare code
(https://arxiv.org/abs/2501.04052). A balanced-ternary element has one zero, so 27 codes
give 27 values.

## What it means for TNF's position

1. **The niche is empty, and emptiness is not a win.** Nobody publishes a 27-level element in a
   3-trit cell. That is novelty. It is not evidence that the format is better.
2. **"Beats MXFP4" is not a distinguishing claim.** Several binary formats already beat MXFP4:
   AdaMX and BlockDialect at 4.25 bits or less, NVFP4 and MX+ at 4.5. A reviewer will also say
   that a 3-trit cell carries log2 27 = 4.75 bits, so the fair opponents are the 4.5-bit
   formats, not only MXFP4. The pre-registered search
   (`specs/numeric/ternary_storage_search.t27`) already names this "a win of the substrate",
   and it predicts that a 5-bit binary element is at least as good. It has no 4.5-bit arm.
3. **The strongest honest position is conditional on the substrate.**
   - **If** a trit cell costs about what a bit cell costs, a 3-trit cell holds 27 levels where
     4 bit cells hold 15. The level shape then matters: which 27 levels, with which block scale.
   - That "if" is the first thing a reviewer attacks. There is no measured area, energy or read
     margin for a trit cell against a bit cell, and ReTern argues the opposite.
   - This project cannot measure it on an FPGA, which is binary.
4. **A second position:** ternary-weight models, the BitNet kind, stored with no pack/unpack.
   That is an argument for the substrate. It is not an argument for a 27-level TNF, and the gain
   over 5-in-8 packing is about 1 % in bits.

For the next pre-registration, if the owner wants one: put NVFP4 (4.5 bits) or MX+ beside
MXFP4 as a comparator, and state the equal-storage definition before the run.
