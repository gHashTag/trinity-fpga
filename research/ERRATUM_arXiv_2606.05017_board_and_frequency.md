# Erratum draft — arXiv:2606.05017, the board and the kind of frequency

**Status: DRAFT IN REPOSITORY. Not submitted anywhere.** Replacing an arXiv entry
needs the author's credentials. This file records the finding and the evidence so
the decision can be made from facts.

**Article:** D. Vasilev, *GoldenFloat: A Phi-Derived Static-Split Floating-Point
Family from GF4 to GF1024 with a Lucas-Exact Integer Identity*,
[arXiv:2606.05017](https://arxiv.org/abs/2606.05017), v3 of 2026-06-22.

**Type of correction:** two of them, and they are different in kind.
1. **Factual** — the abstract names a part the work was not done on, and the
   article's own body names a third.
2. **Interpretive** — the headline frequency is a real measurement of something
   the sentence does not say it is measuring.

**Source of the evidence:** `research/XC7A200T_GF16_DATAPOINT_2026-08-05.md`,
produced 2026-08-05 by a local openXC7 run plus on-silicon conformance.

---

## 1. Three parts are cited for one result

| Source | Part | Package |
|---|---|---|
| arXiv:2606.05017 abstract | XC7A**35T** | Arty |
| `t27/docs/arxiv-submission/trinity-gf16.tex`, body and table | XC7A**100T** | QMTECH FGG676 |
| Reproduction, 2026-08-05 | XC7A**200T** | ALINX AX7203 FBG484 |

The abstract and the body of the same work disagree with each other. That is not
a question of which board a reader should believe; it is an internal
contradiction, and it is the one a reviewer notices first.

The RTL in the repository points the same way: every file in `fpga/vivado/` is
named `*_ax7203`, and AX7203 is the XC7A200T.

## 2. The headline 323 MHz is a combinational number, presented as if it were a clock rate

The abstract reports the GF16 FPGA codec as *"passing a 35-of-35 testbench at
323 MHz on Artix-7"*. The source of that figure is `trinity-gf16.tex`:

> "Max frequency for clock `chain[19]`: 323.31 MHz"

`chain[19]` is a **ripple-counter probe clock**. The bare `gf16` core is a purely
combinational multiply: it has no register-to-register path, so what is being
reported is `1 / (combinational delay)` exposed through a counter. That is a
valid measurement and a normal way to characterise a combinational block. It is
not the clock rate of a working design, and the sentence in the abstract reads as
though it is.

The routed, clocked conformance design on the same family measures **27.55 MHz**
by nextpnr static timing for clock `mclk` — an order of magnitude below the
bare-core figure. Both numbers are true. They measure different things, and the
paper presents only one of them, in the position where a reader expects the
other.

The design nonetheless functions, because the datapath is UART-paced at
160 kbaud, far below either estimate. openXC7/nextpnr static timing on xc7 is
also known to be conservative. Neither of those facts rescues the sentence: a
combinational figure quoted as a design's operating frequency is wrong however
well the design runs.

## 3. What this erratum does NOT touch

The conformance results stand and are independent of both corrections. Measured
on the AX7203, bit-exact against `conformance/gf_ref.py`:

- **GF16 multiply — 5/5 exact.** 1.5x2.0=3.0, 2.0x2.0=4.0, 1.5x1.5=2.25,
  3.0x2.0=6.0, 1.0x3.0=3.0, as raw codes 0x3F00/0x4000 -> 0x4100 and so on.
- **GF8 add — 5/5 exact** on the same board.
- **Special values on silicon:** `gf16_mul(inf, 0)` = 0x7E01 (NaN),
  `gf16_mul(inf, 2)` = 0x7E00 (inf), exponent field all-ones as specified.

The "35-of-35 testbench" claim is likewise not in question. What is in question
is the frequency attached to it and the part it is attached to.

## 4. Proposed corrections

1. **Abstract:** name the exact part and package once, and say what kind of
   frequency it is. Either drop the number, or write it as what it is --
   *"a GF16 codec passing a 35-of-35 testbench; the bare core's combinational
   delay corresponds to 323 MHz measured against a probe clock"*.
2. **Body and table:** reconcile with the abstract. One part, named once.
3. **Add the routed number** alongside the combinational one, so the two kinds
   are visible together rather than one standing in for both.

## 5. Relationship to the withdrawn matmul figure

There is a separate, already-published withdrawal of *"323 MHz and 41.2 GOPS for
the GF16 matmul"*, on the grounds that the matmul holds no registers in any of
its nine copies and therefore has no clock. **That withdrawal does not apply
here.** The matmul and the codec are different modules: `gf16_codec_ax7203.v`
carries 8 `posedge` and 11 `always` blocks, so it is a sequential design and a
frequency can belong to it.

Three distinct things share the number 323 and are routinely confused, including
by people working on this repository:

| | module | registers | status |
|---|---|---|---|
| withdrawn | `gf16_matmul4x4` / `gf16_dot4` | none | correctly withdrawn |
| this erratum | `gf16` bare core / codec | codec is clocked | figure real, description wrong |
| unrelated | `phi^k` iterative applier | clocked | 323.42 MHz post-route, 2026-08-10 |

Anyone reading a "323" in this project should establish which of the three it is
before repeating it.
