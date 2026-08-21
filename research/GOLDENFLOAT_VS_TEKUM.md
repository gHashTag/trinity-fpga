# GoldenFloat vs Tekum — Structured Comparison

**Date:** 2026-07-14
**Authors:** Agent S (Specs/Standardization) + Agent N (Numeric), per the 2024–2026 literature scan
**Urgency:** Highest. Identified in `LITERATURE_SCAN_2024_2026.md` §1.4 / §7.3 as the single most urgent read.
**Sources:**
- **Tekum** — L. Hunhold, *Tekum: Balanced Ternary Tapered Precision Real Arithmetic*, [arXiv:2512.10964](https://arxiv.org/abs/2512.10964) (cs.ET; cs.AR), submitted 25 Nov 2025, 23 pp., 5 figs.
- **GoldenFloat** — φ-derived family [arXiv:2606.05017]; family spec `t27/specs/numeric/goldenfloat_family.t27`; HW conformance `research/goldenfloat-hw-conformance/GOLDENFLOAT_HW_CONFORMANCE_v0.2.md`.

---

## 0. Tekum abstract (verbatim)

> *In light of recent hardware advances, it is striking that real arithmetic in balanced ternary logic has received almost no attention in the literature. This is particularly surprising given ternary logic's promising properties, which could open new avenues for energy-efficient computing and offer novel strategies for overcoming the memory wall.*
>
> *This paper revisits the concept of tapered precision arithmetic, as used in posit and takum formats, and introduces a new scheme for balanced ternary logic: tekum arithmetic. Several fundamental design challenges are addressed along the way. The proposed format is evaluated and shown to exhibit highly promising characteristics. In many respects, it outperforms both posits and takums. As ternary hardware matures, this work represents a crucial step toward unlocking the full potential of real-number computation in ternary systems, laying the groundwork for a new class of number formats designed from the ground up for a new category of next-generation hardware.*
> — Hunhold, arXiv:2512.10964

**Subjects:** cs.ET (Emerging Technologies); cs.AR (Hardware Architecture). **ACM classes:** G.1.0; C.1.0. **License:** CC-BY 4.0.

---

## 1. One-paragraph framing

Tekum is the **balanced-ternary** instance of the tapered-precision family that already contains posit and takum. Its author (Hunhold) is the same researcher who defined takum and beat posits with it [arXiv:2404.18603] and who published a takum FPGA codec at −38% latency / −50% LUT vs posits [arXiv:2408.10594]. Tekum therefore collides *directly* with Trinity's "ternary + float" thesis: it is published, peer-track (CoNGA/ARITH community), and forward-looking toward next-generation ternary hardware. GoldenFloat, by contrast, is a **conventional IEEE-754-style linear float** whose only distinguishing rule is the φ-ratio exp/mant selection heuristic; its *encoding* is not tapered and its *logic* is binary. The two formats are structurally different and are not direct substitutes — but they compete for the same "rethink floating point" mindshare.

---

## 2. Comparison table

| Dimension | GoldenFloat | Tekum |
|---|---|---|
| **Encoding type** | IEEE-754-style linear (`S:E:M`, binary) | Tapered precision, balanced ternary |
| **Precision rule** | φ-ratio heuristic: exp/mant → 1/φ ≈ 0.618 | Balanced-ternary tapered (precision concentrates near unity) |
| **Dynamic range** | Fixed per format; conventional bias `2^(e-1)-1` | Tapered (wider near unity, narrows at extremes) |
| **Representative format** | GF16 = `[1\|6\|9]` (same split as IBM DLFloat / HFP8-backward) | tekum ternary words (width parameterized) |
| **Hardware cost** | LUT-only adder, **294 LUT (GF16)** [confirm vs EPIC #199] | TBD from paper (no FPGA codec published; format-property evaluation only) |
| **FPGA proven** | **Yes** — openXC7, 16 GF compute cells (ADD/MUL) bit-exact on Artix-7 | **No codec yet.** Nearest datapoint is the *takum* (binary) VHDL codec [arXiv:2408.10594]: −38% latency, −50% LUT vs posits |
| **Block scaling** | No | No (but tapered precision plays a similar range-adaptation role) |
| **Logic base** | Binary (2-valued) | Balanced ternary ({-1, 0, +1}) |
| **Standardization** | None | CoNGA / ARITH track (same community as posit/takum) |
| **Maturity** | Open-silicon proof (EPIC #199); no formal accuracy theorem | Published format definition (23 pp.); dependent on ternary hardware that is still maturing |
| **Anchor identity** | `φ² + φ⁻² = 3` (algebraically true; not an accuracy theorem) | Inherits tapered-precision accuracy theory from posit/takum lineage |
| **Silicon dependency** | Runs on today's commodity binary FPGAs | Targets next-generation ternary hardware (not yet commodity) |

---

## 3. Where they genuinely differ

1. **Logic base is the hard differentiator.** GoldenFloat runs on today's binary silicon (Artix-7, openXC7). Tekum is defined for balanced-ternary hardware that is still emerging; on a binary fabric, tekum must be emulated and loses its efficiency premise. This is not a quality judgment — it is a deployment-reality gap of several years.
2. **Tapered vs fixed precision.** Tapered designs (posit → takum → tekum) have accumulated ARITH/CoNGA evidence of *superior accuracy for general-purpose compute at low width* [arXiv:2412.20268; arXiv:2504.21197]. GoldenFloat's φ-ratio split has no comparable accuracy theorem; the literature scan concludes the optimal exp/mant split is workload-dependent [arXiv:2208.09225], not a universal constant. On numerical merit, the tapered family is ahead.
3. **Hardware evidence.** Trinity uniquely holds open-silicon numbers for GoldenFloat. Tekum holds format-property analysis but no codec; its hardware legitimacy currently rides on the *takum* codec's numbers.
4. **Community legitimacy.** Tekum comes from the posit/takum lineage with an active CoNGA/ARITH community. GoldenFloat is a single-group proposal with no standardization track.

---

## 4. What Trinity should *not* do

- **Do not claim GoldenFloat is numerically superior to tekum.** The evidence does not support it; tapered precision has the accuracy track record.
- **Do not claim the φ-ratio as an accuracy theorem.** It is a design heuristic. The `φ² + φ⁻² = 3` identity is algebraically true but is a property of φ, not a floating-point accuracy result.
- **Do not frame ternary as Trinity's exclusive territory.** Tekum pre-empts the "ternary + float" niche; Trinity's ternary-VSA / ternary-MAC work must now be positioned *relative to* tekum, not in ignorance of it.

---

## 5. Recommendation — should Trinity pivot to tekum?

**No.** But Trinity should **add tekum to the catalog and benchmark it head-to-head.**

Rationale:

- **Pivoting would discard the real moat.** Trinity's defensible contribution is the *format catalog × open-source-silicon proof* (71/83 cells on openXC7) and the four decode templates — not any single format. Abandoning GoldenFloat for tekum would discard proven silicon work for an unproven (no codec, no commodity ternary silicon) substitute.
- **The catalog is format-agnostic by design.** Tekum is exactly the kind of format the catalog exists to prove. Adding it (decode +, when a ternary-aware or emulated-decode path exists, compute) turns a competitor into a catalog entry and reinforces the "independent proving ground" positioning.
- **Run the head-to-head.** On a fixed accuracy suite (SuiteSparse-style, à la Hunhold & Quinlan, ARITH 2025 [arXiv:2412.20268]) and on openXC7 LUT/route-yield, compare: GoldenFloat GF16 vs takum16 vs tekum (emulated) vs posit(16,1) vs MXFP8 vs FP8 E4M3. This is the table nobody else can fill, and it is the catalog paper's strongest result.

**Concrete next actions:**

1. Add tekum as a catalog row (`gHashTag/t27/specs/numeric/formats_catalog.t27`) and a decode-conformance target (emulated decode path for binary fabric; document the emulation caveat).
2. Produce the GF16-vs-tekum-vs-takum16 accuracy + LUT table for the catalog paper [arXiv cs.AR outline, `CATALOG_PAPER_OUTLINE.md` §5].
3. Cite tekum [arXiv:2512.10964] in all external Trinity documents that mention ternary float, per the honesty rule.
4. Track ternary-hardware maturation; revisit a native-tekum compute path when commodity ternary FPGA/logic exists.

---

## 6. Honest bottom line

Tekum is the more *numerically principled* format (tapered precision, peer-track). GoldenFloat has the *hardware proof* (open silicon today) and a convenient deployment story (binary fabric). Neither dominates the other across all axes. Trinity's strategic move is to **stop competing on format novelty** and **compete on catalog breadth + open-silicon reproducibility**, while treating tekum as a first-class catalog citizen rather than a threat.
