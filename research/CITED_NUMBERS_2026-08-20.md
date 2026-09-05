# Cited numbers — the external-attribution sweep (2026-08-20)

Every number (or exactly-stated quantitative fact) that `research/arxiv_tnf/tnf_paper.tex`
attributes to an external source via citation, checked against that source itself.
Companion to `RANGE_PROVENANCE_2026-08-20.md` (the paper's own measured numbers) and
`WEIGHT_RECORDS_2026-08-20.md` (weight-derived numbers): this file covers the numbers the
paper did NOT measure but quotes from someone else.

## Method

**The evidence rule (hard, from two confabulations this campaign caught):** a summary,
abstract-snippet from a search engine, or model-paraphrase of a fetch is NEVER evidence of
what a paper says. Evidence is a verbatim quote extracted from the SOURCE PDF/text itself —
a local file, or the arXiv/publisher page fetched raw and read. Where a fetch could only
return a paraphrase, or no source text could be obtained at all, the verdict is
UNVERIFIED-OFFLINE, never confirmed and never refuted. Fetches for this sweep were raw
(`curl` + own extraction from the HTML/PDF); no model-mediated fetch answers were used.

Refinements applied:

- **Author-written arXiv abstracts are source text** (the authors wrote them), but
  compression is indistinguishable from omission: a claim confirmed only at abstract level
  is marked so when the cited detail is body-level.
- **Every CONTRADICTED was re-derived before being recorded** (skill rule). The one upheld
  contradiction was re-spot-checked against the RTL in this worktree during write-up; the
  one overturned contradiction was re-established from the takum e-print and libtakum
  sources on disk.
- **Digit strings the PDF text layer would not yield** (Wu's degree-5 Perron number,
  Siegel's plastic-number digits) were re-derived numerically from the minimal polynomial
  quoted verbatim from the source, and are marked as derivations.
- **Provenance.** This file consolidates the campaign's verification pass with a write-up
  re-extraction: every quote below was read from the named source file/page during the
  writing of this document (the goldenfloat and catalogue quotes delivered by the
  verification pass were re-verified line-by-line against the local e-prints
  `gf_paper/src/main.tex` and `catalog_09686.txt`).

**Inventory: 40 claims** across 31 sources/source-groups. Same-source claim sites in the
same paragraph are merged into one row (merges are marked). Line numbers refer to
`tnf_paper.tex` at worktree state ff2d9d037.

Verdict key: **CONFIRMED** — verbatim source quote matches the citation as stated.
**CONTRADICTED** — source text contradicts the citation; upheld after re-derivation.
**UNVERIFIED-OFFLINE** — no source text obtainable; exact reason recorded.

---

## Verdicts by source

### goldenfloat (arXiv:2606.05017) — own prior work — 4 claims

Source: arXiv e-print, local at `gf_paper/src/main.tex` (latest version).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 1 | 256 | rule reproduces nine realised widths (GF4…GF256), extends to GF128/512/1024 | CONFIRMED |
| 2 | 264 | accumulator checked at 500-digit precision for n = 1…256 | CONFIRMED |
| 3 | 265 | GF16 codec 35-of-35 at 323 MHz on Artix-7 XC7A35T | CONFIRMED |
| 4 | 269 | RTL erratum dated 2026-05-31; corrected generator is the baseline | CONFIRMED |

- **#1** — main.tex 122–125: "The rule reproduces the realised exponent widths of nine
  formats GF4, GF8, GF12, GF16, GF20, GF24, GF32, GF64, GF256 (9/9) and extends
  consistently to GF6, GF10, GF14, GF48, GF96, GF128, GF512, GF1024." The nine match
  exactly and GF128/GF512/GF1024 are among the extensions — note the source lists EIGHT
  extension widths; the citing paper names a 3-of-8 subset. Accurate as stated, incomplete
  as an enumeration of the source's extension set.
- **#2** — main.tex 112–114: "(ii) an integer-backed Lucas-exact accumulator path verified
  at 500-digit precision for $n = 1,\dots,256$". Corroborated at 514–517: "At 500 decimal
  digits (\texttt{mpmath}), the maximum residual … over the range is $1.55 \times
  10^{-499}$ at $n = 256$ … consistent with 500-digit precision."
- **#3** — main.tex 114–115: "(iii) a GF16 FPGA codec passing a 35-of-35 testbench at
  323~MHz on Artix-7 (Xilinx XC7A35T)". The citing paper's caveat that this is "a
  different and smaller part" than its own XC7A200T is its own commentary (XC7A200T
  appears nowhere in the source). Repo note `gf16_323mhz_withdrawn.md` separately withdrew
  this number, but the source paper itself still asserts it — the citation reports the
  source accurately.
- **#4** — main.tex 140–143: "An RTL-correctness erratum dated 2026-05-31 is reported in
  Section~\ref{sec:hw-erratum}; the fabricated TTSKY26b dies carry the defective
  multiplier portfolio, and the corrected generator is the regeneration baseline."

### catalogue (arXiv:2606.09686) — own prior work — 3 claims (5 sites)

Source: v2 PDF text local at `catalog_09686.txt`; v1/v2 abs pages local at
`abs_09686v1.html` / `abs_09686.html`.

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 5 | 371 | bit-exact packs, SHA-256 fingerprints, thirteen families, ml_dtypes 0.5.4, divergences recorded as interpretation gaps | CONFIRMED |
| 6 | 375 + 401 | v1 title said 84 formats; v2 title, shipped catalog and this paper's count are all 83 | CONFIRMED — with one stale-wording defect at 401 |
| 7 | 6055–6056 + 7643–7645 | the 83-format catalogue cross-walks against P3109 explicitly; shipped count matches current title | CONFIRMED |

- **#5** — v2 abstract (catalog_09686.txt:17): "This paper describes a catalog of 83
  numeric formats spanning 13 families, a suite of six bit-exact conformance packs…";
  body: "Cross-check against ml dtypes 0.5.4" (l.395, pdftotext drops the underscore),
  "SHA-256 self-fingerprint (computed over the canonical JSON serialization)" (l.367),
  divergences "documented explicitly and interpreted as a spec-permitted interpretation
  gap rather than hidden" (abstract). Side-fact verified: in the citing paper
  `ml\_dtypes` occurs only at line 371 and has no \bibitem; the catalogue itself DOES
  carry a bibliography entry for ml_dtypes.
- **#6** — v1 abs title verbatim: "An 84-Format Numeric Catalog with Bit-Exact Conformance
  Vectors…"; v2 title: "An 83-Format…"; shipped catalog: "The sum of counts is exactly 83;
  this is a continuously enforced catalog invariant (CI-01, Section 3.4)"
  (catalog_09686.txt:149–150). Exactly as line 375 states. **Defect:** the figure caption
  at line 401 says, present tense, "whose title says 84 where the shipped count is 83" —
  true only of the superseded v1 title; the current v2 title already says 83. Fix the
  caption.
- **#7** — catalog_09686.txt:19: "…and an IEEE P3109 v3.2.0 cross-walk that maps each pack
  to its corresponding…"; l.60: "Section 6 provides an IEEE P3109 cross-walk."

### gustafson / posit (2017 SFI paper + pre-standard spec + Posit Standard 2022) — 3 claims

Sources local: `gustafson_posit.txt` (Posits4.pdf, "Posit Arithmetic", 10 Oct 2017, from
posithub.org/docs/Posits4.pdf), `posit_standard_2022.txt`.

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 8 | 678 | posit64's oracle carries the pre-standard es = 3 | CONFIRMED |
| 9 | 736 | Posit Standard (2022) fixes es = 2 at every precision | CONFIRMED |
| 10 | 821 | literature describes taper qualitatively: more precision near unity, less at the extremes | CONFIRMED |

- **#8** — Posits4 (gustafson_posit.txt:4574–4576): "The es value should simply be
  es = log2 (nbits) - 3" — for nbits = 64 this gives es = 3, the pre-standard convention
  the paper's posit64 oracle carries. (The 2022 standard later fixed es = 2; the citation
  correctly labels es = 3 as pre-standard.)
- **#9** — Posit Standard 2022 (posit_standard_2022.txt:314–315): "The exponent bit field
  𝐸 has length 2 bits, but one or both bits may be beyond the LSB and thus have value 0."
  One fixed 2-bit exponent field at all precisions — es = 2 with no per-precision
  parameter.
- **#10** — Posits4 (gustafson_posit.txt:202–204): "regime bits … automatically and
  economically create tapered accuracy, where values with small exponents have more
  accuracy and very large or very small numbers have less accuracy."

### takum (arXiv:2404.18603 + codec paper arXiv:2408.10594 + libtakum) — 3 claims

Sources local: `takum_src/extracted/hunhold-beating_posits_at_their_own_game.tex`
(fetched e-print), `libtakum/` (reference implementation), `abs_2408.10594.html`
(raw abs page, fetched this pass).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 11 | 786 | mechanism behind takum's stated improvement on posits | CONFIRMED |
| 12 | 7156–7160 | enumerated takum16 reach (1.84e-77 … 5.61e76, ±255 binades) is "exactly the published takum reach" | CONFIRMED — prior CONTRADICTED verdict OVERTURNED on recheck; residual defect: variant naming |
| 13 | 7510 | takum's published codec RTL is VHDL | CONFIRMED |

- **#11** — takum abstract (tex:118–125): "Although the posit encoding scheme offers
  superior coding efficiency at values close to unity, its efficiency markedly diminishes
  with deviation from unity. This reduction in efficiency leads to suboptimal encodings
  and a consequent diminution in dynamic range, thereby rendering posits suboptimal for
  general-purpose computer arithmetic." Takum is introduced "synthesising the advantages
  of posits in low-bit applications with high encoding efficiency for numbers distant
  from unity."
- **#12** — the recheck that overturned the prior contradiction, re-established from
  sources on disk. The headline takum of arXiv:2404.18603 is **logarithmic, base √e**
  (tex:28: `\newcommand{\euler}{\sqrt{\mathrm{e}}}`) with published reach (tex:296–297):
  "The integer $255$ remains as the sole candidate, offering a dynamic range of
  $(\euler^{-255}, \euler^{255}) \approx (\num{4.2e-56}, \num{2.4e55})$" — i.e. ≈ ±184
  binades, NOT 2^±255, which is what made the first pass mark the paper's "exactly the
  published takum reach" CONTRADICTED. The recheck found the claim has a **genuine
  published referent**: the linear (floating-point) takum variant. The codec paper's
  abstract (abs_2408.10594.html): "a hardware codec for both takums (logarithmic number
  system, LNS) and linear takums (floating-point format)"; the takum paper itself defines
  the linear-significand variant in active equations (tex:1345 `eq:takum-exponent-linear`,
  tex:1361 `eq:takum-value-linear`); and libtakum — the format's reference
  implementation — ships "takum8, takum16, takum32, takum64 for the (floating-point)
  takums" (libtakum/README.md) whose decode (`codec_s_and_linear_l_to_float64`,
  src/codec.c:226) is base-2 with c ∈ [−255, 254], giving exactly the 2^±255-binade reach
  the paper's enumeration measured. **Residual defect (paper fix):** the sentence cites
  \cite{takum} without naming the variant; "the published takum reach" is true of the
  linear/floating-point takum, while the cited paper's headline logarithmic takum has
  published reach 4.2e-56 … 2.4e55. Name the variant.
- **#13** — codec-paper abstract (abs_2408.10594.html): "The presented takum codec,
  implemented in VHDL, demonstrates near-optimal scalability and performance on an FPGA."

### tekum (arXiv:2512.10964) — 1 claim (3 sites)

Source local: `tekum_full.txt` (full paper text).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 14 | 685–687 + 7498–7503 | tekum is the balanced-ternary member of the posit/takum tapered family; counts width in trits (tekum16 = 16 trits ≈ 25.4 bits); tekum_true_ref implements its Definitions 7–8 | CONFIRMED |

- Abstract (tekum_full.txt:159): "This paper revisits the concept of tapered precision
  arithmetic, as used in posit and takum formats, and introduces a new scheme for
  balanced ternary logic: tekum arithmetic." ("Descendant of takum" is the citing paper's
  word; the source presents tekum as the balanced-ternary member of that family.)
- Width in trits: "The set of n-trit balanced ternary strings" (l.319); "a single trit
  contains log 2 (3) ≈ 1.58 bits" (l.191); "the overhead in trits for ternary formats is
  multiplied by log 2 (3)" (l.3033). 16 × log₂3 = 25.36 ≈ 25.4 bits — derivation from
  quoted statements.
- "Definition 7 (anchor function)" (l.705) and "Definition 8 (tekum encoding)" (l.1939)
  exist as cited.

### repo RTL, fpga/openxc7-synth/ — 1 claim — the sweep's one upheld contradiction

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 15 | 2421–2426 | one exp table (`takum32_2frac.mem`) serves four source widths (takum8/16/32/64) | **CONTRADICTED — upheld** |

- Paper: "It reads \texttt{takum32\_2frac.mem} --- \emph{the same file} --- and emits
  binary32, as do the takum8, takum16 and takum64 decoders. One table serves four source
  widths because all four target one datapath."
- Confirmed sub-parts, verbatim from RTL: `takum32_decode.v:49-50`
  `reg [47:0] tbl [0:65535];` + `initial $readmemh("fpga/openxc7-synth/takum32_2frac.mem",
  tbl);` (k = 16, 48-bit; the .mem is exactly 65,536 lines × 12 hex chars, re-counted);
  `takum32_decode.v:55` `wire [31:0] corr_q2 = corr + ((corr * corr) >> 49); // + quadratic
  Taylor term x^2/2` (d = 2); `takum64_decode.v:49` reads the same file.
- Contradicted sub-part, re-spot-checked in this worktree during write-up:
  `takum16_decode.v:14` reads a DIFFERENT file — `initial
  $readmemh("fpga/openxc7-synth/takum16_lut.mem", lut);` — a direct 65,536-entry
  code→FP32 BRAM LUT ("rounding to binary32 RNE; stored in takum16_lut.mem", header), not
  the shared exp table; and `takum8_decode.v` contains NO `$readmemh` at all — a
  256-entry inline literal ROM. Repo-wide grep for `takum32_2frac` in `*.v` hits only
  takum32/takum64 decoders (plus copies in fpga/tnet/, fpga/regime/real/). **One table
  serves TWO source widths, not four.** The comment in `takum64_decode.v:49` — "SAME
  table as takum32/16" — repeats the same false claim about takum16: a comment seeded the
  paper's error. Fix both the paragraph and the comment.

### goldberg1991 + ibmhfp — 1 claim

Sources local: `goldberg1991.txt` (ACM Computing Surveys reprint), `ibmhfp.txt`
(Wikipedia page capture).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 16 | 893 | IBM S/360 hexadecimal delivers between 4p−3 and 4p significant bits, a spread of three | CONFIRMED |

- Goldberg verbatim: "In general, base 16 can lose up to 3 bits, so that a precision of p
  hexadecimal digits can have an effective precision as low as 4 p - 3 rather than 4 p
  binary bits". Wiki corroborates the wobble framing: "Six hexadecimal digits of precision
  is roughly equivalent to six decimal digits" + "wobbling precision".

### yosys + nextpnr (tool versions) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 17 | 1194–1195 | synthesis with Yosys 0.65; P&R with nextpnr-xilinx (1743d0f) | CONFIRMED |

- Yosys verified against the instrument itself: `yosys --version` → "Yosys 0.65 (git sha1
  aec814bdf3071f7e0fd0fbe43f7f711e99d01e24, …)". nextpnr-xilinx 1743d0f verified against
  the repo's method records (`research/METHOD_2026-08-10.md:169`,
  `research/arxiv_tnf/README.md:79`, frontier post-route notes — all consistently
  1743d0f); the binary was not on PATH in this session, so this half is record-verified,
  not re-run.

### hayes2001 + radixeconomy — 1 claim

Sources local: `hayes2001_text.txt` ("Third Base", American Scientist 2001),
`optimal_radix_wiki.txt`.

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 18 | 1571 | the base-e radix-economy argument (3 the most economical integer radix) is the classical statement | CONFIRMED |

- Hayes verbatim: "the optimum radix is e , the base of the natural logarithms, with a
  numerical value of about 2.718. Because 3 is the integer closest to e , it is almost
  always the most economical integer radix". Wiki: "base e is the most economical base for
  the representation and storage of numbers" (quoted there as the classical argument).

### etiemble2019 (arXiv:1908.06841) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 19 | 1577 | Etiemble argues R=3 is NOT the optimal radix once realised circuit costs count | CONFIRMED |

- Raw abs page, fetched this pass: title "Ternary circuits: why R=3 is not the Optimal
  Radix for Computation"; abstract: "A demonstration that e=2.718 rounded to 3 is the best
  radix for computation is disproved. … For arithmetic circuits such as adders and
  multipliers, the ternary circuits are always outperformed by the binary ones using the
  same technology."

### aetherfloat (arXiv:2603.08741) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 20 | 1591 | AetherFloat proposes block-scale-free quad-radix floating-point for AI accelerators | CONFIRMED |

- Local abs capture `aetherfloat_abs.html`, author abstract: "By synthesizing
  Lexicographic One's Complement Unpacking, Quad-Radix (Base-4) Scaling, and an Explicit
  Mantissa, AetherFloat achieves zero-cyc[le]…" — motivated by "the strict necessity of
  Block-Scaling (AMAX) logic" in current 8-bit formats.

### ternary27 (hackaday.io/project/164907) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 21 | 1650 | Ternary27 counts positions: 2 type trits + 1 sign + 5 exponent + 19 significand = 27 | CONFIRMED |

- Local capture `ternary27.txt:109–110`: "The format is 27 trits wide and is composed of a
  2-trit type field, a sign trit, a 5-trit exponent field and a 19-trit significand
  field."

### elias1975 (IEEE Trans. Inform. Theory 21(2)) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 22 | 1818 | the prefix-code hierarchy (universal codeword sets) predates the catalogue's formats by decades | UNVERIFIED-OFFLINE |

- No source text obtainable, and the hunt (2026-08-21) was exhaustive: OpenAlex
  oa_status=closed / no repository fulltext; Semantic Scholar isOpenAccess=false; IEEE
  Xplore paywalled; archive.org holds only Elias's 1980 ONR report (cites the paper,
  no reprint); MIT DSpace holds RLE Progress Report 115 (Jan 1975) which lists the
  exact title as "to appear" — legitimate same-author corroboration of the "1975,
  decades before" arithmetic and content shape, but not the cited source. Verdict
  stays UNVERIFIED per the evidence rule.

### positgap (arXiv:2603.01615) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 23 | 2005 | bounded-regime posit variants cap the regime field precisely to avoid the scan | CONFIRMED |

- Raw abs page, fetched this pass: "the b-posit restricts the regime field to a 6-bit
  limit, reducing variability in regime and fraction sizes."

### echeverria2011customizing (Elsevier — this header earlier said IEEE, which was
### this doc's error; Microprocessors and Microsystems 35(6):535-546, 2011) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 24 | 2186 | an FPGA FP-unit customization study reports the same area/performance shape | CONFIRMED (2026-08-21) |

- Legitimate OA copy at the UPM institutional repository — the bibitem's own URL
  (oa.upm.es/12150, PDF read in full, 12 pp.). Section 6.1 verbatim: "handling
  exponents has a small hardware cost in the operators"; Sec. 6.2: one extra mantissa
  bit means requiring more resources; Table 6 shows the mantissa calculation stage
  dominating slices in the streamlined operators. Supports the qualitative
  "mantissa dominates, exponent cheap" shape; caveat: single precision only, no
  mantissa-width sweep, so it is not a quantitative area-vs-width curve. Provenance
  fixes recorded: Elsevier journal (not IEEE), and "technical report" in the bibitem
  is imprecise.

### bitnet (arXiv:2402.17764) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 25 | 2692 | BitNet-style ternary weights in {−1, 0, +1} | CONFIRMED |

- Local abs capture `bitnet_abs.html`, author abstract: "we introduce a 1-bit LLM variant,
  namely BitNet b1.58, in which every single parameter (or weight) of the LLM is ternary
  {-1, 0, 1}."

### oh2025tsar (arXiv:2511.13676) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 26 | 2696 | a 2025 co-design reorganises CPU SIMD lanes in place for ternary inference without an accelerator | CONFIRMED |

- Raw abs page, fetched this pass: "T-SAR, the first framework to achieve scalable ternary
  LLM inference on CPUs by repurposing the SIMD register file for dynamic, in-register LUT
  generation with minimal hardware modifications."

### fqp (DAC 2024) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 27 | 3517–3520 | FQP carries two distinct arithmetic units (dualistic-transformation adder; bit-exclusive adder) plus topological-order routing | CONFIRMED |

- Publisher's program-page abstract, local capture `fqp_dacprog.html`: "Fibonacci
  Quantization Processor (FQP) features two multiplication-free computing units: the
  Dualistic-Transformation Adder for large numbers multiplication and the Bit-Exclusive
  Adder for small numbers multiplication. Additionally, Topological-Order Routing
  optimizes data mapping onto these units."

### fibbinary (arXiv:2511.01921) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 28 | 3522–3524 | reports 45% and 44% savings in multiplier power and area | CONFIRMED |

- Local paper text `fib_paper.txt:19`: "45% and 44% in the multiplier's power and area,
  respectively".

### awq (arXiv:2306.00978) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 29 | 3753 | AWQ is built on the activation-aware channel-salience observation | CONFIRMED |

- Raw abs page, fetched this pass: "AWQ finds that not all weights in an LLM are equally
  important. Protecting only 1% salient weights can greatly reduce quantization error. To
  identify salient weight channels, we should refer to the activation distribution, not
  weights."

### mxgap (arXiv:2509.23202) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 30 | 3936 | that E8M0's range exceeds what weights occupy has been observed elsewhere | CONFIRMED |

- Full PDF fetched raw this pass, body verbatim: "Figure 4 shows the logarithmic dynamic
  ranges of several FP8 formats and compares them with the empirical distributions of
  shared scales for weights and activations across multiple models. One can see that the
  dynamic range of S = E4M3 covers the full range of these distributions. Trivially,
  S = E8M0, having more range, can easily cover it too."

### nvfp4 (NVIDIA, 2025) — 1 claim (2 sites)

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 31 | 3949 + 5394 | NVFP4: block shrinks to 16, shared scale becomes E4M3 (a scale carrying a mantissa) | CONFIRMED |

- Local paper text `nvfp4.txt`: "by reducing the block size from 32 to 16 elements, NVFP4
  narrows the dynamic range within each block … block scale factors are stored in E4M3
  rather than UE8M0, trading some exponent range for additional mantissa bits."

### frougny2011 + frougny2013 — 1 claim

Sources local: `frougny2011.txt`, `frougny2013.txt`.

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 32 | 4126–4129 | base φ: three digits is the proven minimum for constant-time carry-free addition; two impossible; {−1,0,1} and {0,1,2} both minimal | CONFIRMED |

- frougny2013.txt:1846–1852 (Corollary 38 and its preamble), verbatim: "for the base the
  golden ratio, it gives the precise value of cardinality of the minimal alphabet for
  parallel addition in this base, namely the cardinality #A = 3. … Addition in this base β
  can be performed in parallel on alphabet A = {0, 1, 2}, and also on alphabet
  A = {−1, 0, 1}. Both these alphabets are minimal." Two-digit impossibility:
  "Non-sufficiency of the alphabet {0, 1} for parallel addition was stated in [10]."

### legersky2018 (Acta Polytechnica 58(5)) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 33 | 4131 | Légerský extends the bound to any finite alphabet inside Z[φ] containing zero | CONFIRMED (abstract-level) |

- Publisher landing page (DOI 10.14311/AP.2018.58.0285), fetched raw this pass,
  author abstract: "We focus on alphabets consisting of integer combinations of powers of
  the base. … Under certain assumptions, we prove the same lower bound on the size of the
  generalized alphabet that is known for alphabets consisting of consecutive integers. We
  also extend the characterization of bases allowing parallel addition to numeration
  systems with non-integer alphabets." Caveat: the "inside Z[φ] containing zero"
  specialization is body-level; the abstract confirms the extension to non-integer
  alphabets generally.

### wu2010 (Math. Comp.) — 1 claim

Source local: `wu2010.txt`.

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 34 | 4181 | 1.123732821 is the smallest Perron number of degree 5 (exhaustive) | CONFIRMED (digits re-derived) |

- Verbatim: "In this paper we compute the smallest Perron numbers of degree d ≤ 24 and
  verify that they all satisfy the Lind-Boyd conjecture", with the conjecture's degree-5
  minimal polynomial quoted as "(X d+2 − X 2 − 1)/(X 2 − X + 1) if d ≡ 5 mod 6". The PDF
  text layer does not yield the digit string, so it was re-derived from the quoted
  polynomial: the real root > 1 of (x⁷−x²−1)/(x²−x+1) = x⁵+x⁴−x²−x−1 is
  1.123732821001638 — matching the paper's printed 1.123732821 to every digit. The
  family's value at d = 5, root of x⁵ = x+1 → 1.1673039…, also matches the paper's 1.1673.

### boyd1985 (Math. Comp.) — 1 claim

Source local: `boyd1985.pdf` (pdftotext).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 35 | 4185 | Boyd corrected Lind's conjecture at exactly d>3 with d ≡ 3, 5 (mod 6) | CONFIRMED |

- Verbatim (OCR renders ≡ as =): "In private correspondence, Lind conjectured that the
  smallest Perron number of degree d > 2 should have minimal polynomial x^d - x - 1. This
  turns out to be true if d = 2, 3, 4, 6, 7, 8, 10, 12, but false if d > 3 and d = 3 or 5
  (mod 6)." (Wu 2010 independently states the same correction.)

### siegel1944 (Duke Math. J.) — 1 claim

Source local: `siegel/firstpage.txt` (OCR of the paper's first page).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 36 | 4203 | Siegel proved the smallest Pisot number is 1.3247179572…, the root of r³ = r+1 | CONFIRMED (digits re-derived; OCR-degraded source) |

- Verbatim (OCR-degraded): "Consequently there exists a smallest 0 01 1. We shall prove
  that 01 is the positive zero of x3 [− x −] 1 and that also 01 is isolated in S. …
  1.324". The full digit string is not in the OCR text layer; re-derived from the quoted
  polynomial: real root of x³−x−1 = 1.32471795724475… — matching the paper's printed
  1.3247179572 to every digit.

### berend1994 (Math. Systems Theory 27) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 37 | 4230 | normalisation in base θ is realisable by a finite automaton exactly when θ is Pisot | UNVERIFIED-OFFLINE |

- No source text obtainable, and the hunt (2026-08-21) was exhaustive: Springer
  paywalled (the on-disk capture is verbatim a "Client Challenge" page); Frougny's
  publication page never lists the 1994 paper; Berend's own page links a DVI on a dead
  FTP host with zero Wayback captures; the BGU CRIS record is abstract-only with no
  deposit; Unpaywall/OpenAlex/Semantic Scholar all report no repository copy anywhere.
  Two academia.edu rips of the Springer PDF exist and were deliberately not used. The
  CRIS abstract states the exact claimed theorem verbatim ("...computable by a finite
  automaton over any alphabet if and only if θ is a Pisot number") — consistent, but an
  abstract is not source text. Verdict stays UNVERIFIED per the evidence rule.

### akiyama2016 (arXiv:1401.6329) — 1 claim

Source local: `akiyama.txt` (paper text).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 38 | 4232 | for n ≥ 4 the root of xⁿ = x+1 is not a Parry number; its shift is non-sofic | CONFIRMED |

- Abstract verbatim: "Let βn > 1 be a root of xn − x − 1 for n = 4, 5, . . . . We will
  prove that βn is not a Parry number, i.e., the associated beta transformation does not
  correspond a sofic symbolic system."

### li2020apot (arXiv:1909.13144) — 1 claim

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 39 | 4692 | APoT's quantization levels are sums of power-of-two terms | CONFIRMED |

- Raw abs page, fetched this pass: "By constraining all quantization levels as the sum of
  Powers-of-Two terms, APoT quantization enjoys high computational efficiency and a good
  match with the distribution of weights."

### ocp_mx2023 (OCP Microscaling Formats v1.0 spec) — 1 claim

Source local: `ocp_mx_v1.txt` (spec PDF text).

| # | Line | Claim | Verdict |
|---|------|-------|---------|
| 40 | 5392 | OCP MX fixes a block of 32 elements sharing one E8M0 scale, element at E2M1 | CONFIRMED |

- Spec verbatim: "All 𝑘 elements (𝑃𝑖) have the same data type … The scale factor 𝑋 is
  shared across all k elements"; Table 1 row: "MXFP4 | FP4 (E2M1) | 4 | 32 | E8M0 | 8" —
  block size 32, E8M0 scale, E2M1 element, exactly as cited.

---

## Paper fixes this sweep produces

1. **Line 2421–2426 (upheld contradiction):** "One table serves four source widths" is
   false — it serves two (takum32, takum64); takum16 reads its own `takum16_lut.mem`,
   takum8 is an inline ROM. Also fix the seeding comment in `takum64_decode.v:49`
   ("SAME table as takum32/16").
2. **Line 401 (stale caption):** "whose title says 84 where the shipped count is 83" is
   present-tense but true only of the superseded v1 title; v2's title says 83.
3. **Line 7159–7160 (variant naming):** "exactly the published takum reach" is true of the
   linear/floating-point takum (libtakum's takumN, codec paper's "linear takums"); the
   cited paper's headline logarithmic base-√e takum has published reach
   4.2e-56 … 2.4e55 (≈ ±184 binades). Name the variant.

## Bottom line

Of the **40** claims in the inventory:

- **36 CONFIRMED** — verbatim source quote obtained and matching. Within these: one is a
  prior CONTRADICTED verdict overturned on recheck (takum reach, #12 — genuine published
  referent found; residual defect is variant naming only), and four carry named caveats
  (#6 stale caption wording at line 401; #17 nextpnr half record-verified, not re-run;
  #33 abstract-level; #34/#36 digit strings re-derived from the quoted polynomial).
- **1 CONTRADICTED, upheld** — the repo-RTL "one table serves four widths" claim (#15),
  re-spot-checked against the RTL during write-up.
- **2 UNVERIFIED-OFFLINE** (was 3: echeverria2011 was closed on 2026-08-21 as CONFIRMED
  via the bibitem's own UPM open-access URL — the "IEEE paywalled" label was this doc's
  error, the journal is Elsevier) — elias1975 (#22) and berend1994 (#37): exhaustive
  legitimate-copy hunts recorded in their sections; same-author corroboration found for
  both but inadmissible under the evidence rule. No verdict was manufactured: no source
  text, no verdict.

The citing paper's external attributions are in materially good shape: one false claim
(about its own repo's RTL, seeded by a stale code comment), one stale caption, one
missing variant qualifier — and every number quoted from someone else's measured or
proved work checked out verbatim.
