# arXiv replacement — what to change, in order

> One page. Everything here is verified against the **currently published** text
> (Paper A v3, Paper B v2, both updated 2026-06-22, re-fetched 2026-08-01).
> Re-read end to end on 2026-08-01 (pass 71) against everything learned since it was
> written; §4 had gone stale enough to contradict §2, and did.
>
> Evidence for every line is in `VERIFICATION_DOSSIER.md`; the verbatim replacement
> text is in `ARXIV_ABSTRACTS_READY_TO_PASTE.md`, `ARXIV_BODY_FIXES_READY_TO_PASTE.md`
> and `RELATED_WORK_READY_TO_PASTE.md`. Nothing below needs those files to be read
> first — they are where to look if a line is disputed.

---

## 0. Read this first — which document are you editing?

There are **three** GoldenFloat papers, with three different bibliographies, and the
fixes below do not apply to all of them equally:

| document | references | last touched |
|---|---|---|
| `goldenfloat-preprint/gf_preprint_v19.tex` | **28** | 2026-06-07 |
| **arXiv:2606.05017v3 — what a reader sees** | **33** | 2026-06-22 |
| `trinity-papers-ru/paper1-goldenfloat/main_ru.tex` — Russian, for ВАК journals | **56** | 2026-08-01 |

Two things follow:

- **`goldenfloat-preprint` is not the source of v3 — this is now proven.** Five
  references appear in the published v3 and nowhere in `gf_preprint_v19.tex`, two of
  them postdating that repository's last commit (2026-06-07): an NVIDIA forum post
  dated 2026-06-17, and **Paper B itself**, which appeared 2026-06-08.
  **Editing that file and submitting it would delete Paper A's citation of Paper B.**
  Locate the tree that actually produced v3 before touching anything.
- **`ARXIV_BODY_FIXES_READY_TO_PASTE.md`'s line numbers point into `main_ru.tex`** —
  the Russian ВАК submission, not the preprint. The *claims* hold against the
  published text (re-verified: IEEE 754 and TestFloat are uncited in v3's 33
  references). The *locations* do not.

§1 below is stated against the **published arXiv text**. Use the line numbers only
when editing the Russian manuscript.

---

## 1. Do these — high value, low cost, no new work required

| # | paper | change | why | cost |
|---|---|---|---|---|
| **1** | **B, abstract** | "a suite of **six** bit-exact conformance packs" → **83 packs (75 bit-exact, 8 structural)** | The single largest defect in either paper, and it is an *under*-claim. The abstract reports the central contribution at ~7 % of its actual coverage. The body already says 49/34. | one sentence |
| **2** | **A, abstract** | delete or rewrite "**the fabricated TTSKY26b dies** carry the defective multiplier portfolio" | The only claim in either paper that measurement contradicts — the silicon track was cancelled, so there are no fabricated dies to carry anything. Present in v1, v2 and v3. | one clause |
| **3** | **B, references** | fix **at least 11 of 20** bibitems | Resolved mechanically against arXiv and Crossref, not by reading: **9 of the 12** entries carrying an arXiv id differ from the work that id resolves to. Four are outright misattributions — **[2]**, **[3]** (*"ProofWright: Towards verified floating-point arithmetic"* is really *"…Agentic Formal Verification of CUDA"*), **[8]**, **[13]**. **[1]** is the companion-paper self-citation under a title Paper A does not have. **[19]** and **[20]** carry no title at all. Outside that set, **[12]** credits *"C. Hunhold"* for libtakum — the author is **Laslo** Hunhold — and **[18]** attaches *"v3.2.0"* to the Interim Report, which carries no version number. | verbatim replacements supplied |
| **3a** | **both** | work from **`BIBLIOGRAPHY_FIXES.md`** | One table, both papers, **20 entries**: 8 in A and 12 in B, each with what it currently says, what the identifier actually resolves to, and the defect class. Regenerated from the live arXiv API rather than transcribed. Paste-ready LaTeX for all of them is in `CORRECTED_BIBITEMS.tex`. | — |
| **3b** | **A, references** | fix ref **[11]**, and add the work it was meant to cite | Cited as *"L. Hunhold, Hardware evaluation of takum arithmetic, ARITH 2025, DOI 10.1109/ARITH64983.2025.00019"*. That DOI resolves — checked against Crossref — to **"Evaluation of Bfloat16, Posit, and Takum Arithmetics in Sparse Linear Solvers", Hunhold and Quinlan**: wrong title, wrong author list, wrong subject. It is also a **duplicate of ref [10]**, which cites the same work as `arXiv:2412.20268`. So the bibliography carries one paper twice under two titles, and the ARITH hardware-evaluation paper is missing entirely. | one entry replaced, one added |
| **4** | **B, abstract** | say what the P3109 cross-walk maps — **layout**, not values | The abstract says it "maps each pack to its **corresponding** standards-track configured format". The working group's own Interim Report, §3.1, is normative: *"For signed formats, the exponent bias **shall be** B = 2^(K−P−1). For unsigned formats, the exponent bias **shall be** B = 2^(K−P)"*, and Annex A.5 states plainly *"This differs from IEEE-754"*. So every `binaryKpP` value is exactly **twice** its same-layout IEEE/OCP counterpart. Confirmed empirically at **all 252 configurations** of their published tables and across **258,524 finite codes** against four packs — one distinct ratio. The special-value codes differ too, by exactly the count P3109's *"single NaN, no negative zero"* predicts: 3, 9 and 2049 observed, 3, 9 and 2049 predicted. Mapping layout is worth publishing; the sentence needs one word to say so. | one word |
| **4b** | **A, related work** | add the **DLFloat** acknowledgement — *it already exists, in Russian* | GF16's layout is sign + 6-bit exponent + 9-bit mantissa, bias 31. That is **exactly IBM DLFloat** (Agrawal et al., ARITH 2019, `10.1109/ARITH.2019.00023`). `main_ru.tex` says so plainly — *"is not new as a layout and is not claimed to be… GoldenFloat is honestly positioned as one of the formats using that layout, not as its originator"* — and names Popescu et al. as independent precedent for the 1/6/9 split. **Neither English paper mentions DLFloat or Agrawal at all: zero occurrences in both.** GF16 is the flagship rung, the one with silicon and the 35/35 claim, so a preprint reader cannot learn this. The paragraph translates almost directly, and it *strengthens* the paper — Paper A already says it makes no per-rung superiority claim, and this is the most concrete thing that sentence could point at. | one paragraph, already written |
| **4c** | **A, hardware section** | add the **Tier-E** evidence standard — *also already written, in Russian* | `main_ru.tex` defines a hardware-verification criterion requiring **all four** of: a public openXC7 CI run with its URL, the **SHA-256 of the bitstream**, a **UART log** reading `HW RESULT: N/N bit-exact (fails=0)` at 160000 baud from the physical board, and a matching **IDCODE `0x13636093`** — and states that a green commit message or a passing simulation does **not** count. Proofs are published per cell in issue #199. **`Tier-E`, `AX7203`, `IDCODE`, `openXC7` each occur zero times in both preprints.** This is a separate track from the paper's XC7A35T synthesis result, not a correction to it. **And it is met, not merely proposed:** of 217 comments in `trinity-fpga#199`, 74 carry all four links, covering 45 cells. **44 map onto published packs, so 44 of the 83 formats (53 %) have their DECODE verified on the board** — `binary16` and `gf16` exhaustively, at **65,536/65,536** each. **Arithmetic is a smaller, separate claim:** 30 compute proofs across **12 formats** (gf4–gf32, `double_double`, `quad_double`) for ADD, MUL and SUB. Decoding a bit pattern on silicon and adding two values on silicon are different claims, and the subsection should say which is which. The 38 software-only packs are a coherent set — the wide GF rungs, the wide integers, `x87_fp80`, and the parametric entries with no fixed layout to synthesise — so the split has a physical explanation rather than being a gap in rigour. **And the chain checks out, not just exists:** all **74 cited CI runs resolve and report success**, and a spread sample of **5 of 5 bitstream SHA-256s re-derive exactly** from their CI artifacts — the bitstream each proof names is the one its run produced. **One of the 74 is partial and should be described as such:** `lns16` decode reports `472/576 bit-exact, 104 known-limitation(s), 0 hard-fail(s)`, where the 104 are 1-ULP subnormal-band residuals, tagged in the log and documented in an appendix. Counting it on zero hard-fails is defensible and is stated openly in the proof; a paper repeating the figure should not imply all 74 are uniformly `N/N`. The residuals are also the campaign's third independent sighting of the same boundary — takum32 differs from `libtakum` by one ULP because a logarithmic decode needs `exp()`, and numpy states 1–4 ULP tolerances for the same reason. Software oracle, third-party library and silicon agree that bit-exactness is attainable over the decidable class and logarithmic evaluation is not in it. The UART log and IDCODE need the board. A hardware claim with a stated standard, demonstrably satisfied and independently re-checkable, is far harder to dispute than one without. | one subsection, already written |
| **5** | **B, related work** | add the four-paragraph subsection | Positions the corpus against *published vector sets*, measured from six projects — including the P3109 working group, which ships **504 exhaustive CSV tables (154 MB)** and whose README forbids using them for conformance. That is the real gap this work fills. | one subsection |

**Items 1–4 are corrections. Item 5 is an addition** — skip it if the replacement
needs to be minimal.

## 2. Answer these, or the numbers stay unverifiable

Nobody outside the project can settle these. Each has a spec holding the question.

| question | what is unclear | spec |
|---|---|---|
| the `(9/9)` reproduction count | Off in **both** directions. 17/17 catalogued widths satisfy `e = round((N−1)/φ²)`; the abstract claims 9. Which nine are the *realised* widths, and which postdate the rule? | `WIDTH_PROVENANCE` |
| "83 formats spanning **13 families**" | Never checkable from outside. A module grouping gives 15 — which would not be a defect, just a different cut. | `FAMILY_TAXONOMY` |
| the accumulator **path** | The Lucas identity verifies at 500 digits, n = 1…256. The *implementation* has never been executed here. | `ACCUMULATOR_IMPLEMENTATION` |
| ~~IEEE P3109 **v3.2.0**~~ **— settled, moved to §1 item 3** | Paper B ref [18] names the artefact outright: *"IEEE SA P3109 Interim Report v3.2.0"*. That is the same Interim Report Paper A's [27] points at, and it carries **no version number anywhere in its text**. So this was never "two different document series" — it is a version string attached to a document that has none, in both papers, differently. **Cite the Interim Report by retrieval date.** | — |

## 3. Blocked on a toolchain, not on you

- **GF16 FPGA codec, 35/35 at 323 MHz** — `nextpnr-xilinx` is absent here. The same
  gap blocks post-route P&R and the paper's own FL-002 experiment. Anyone with
  openXC7 or Vivado can settle it in an afternoon.
### The FPGA part number — now located, and only you can settle it

The **same** achieved result is attributed to **two different parts**:

| claim | Paper A | `main_ru.tex` |
|---|---|---|
| **achieved** — GF16 codec, 35/35 at 323 MHz | **XC7A35T** | **XC7A100T** |
| *planned* — matched-substrate H₄ (Appendix D) | XC7A100T, QMTech Wukong V1 | — |
| *physical board* — Tier-E track | — | XC7A200T, ALINX AX7203 |

Paper A is internally consistent: it uses XC7A100T only for the **pre-registered**
comparison, never for the achieved result. `main_ru.tex` attributes the achieved
result to that same part — which is precisely the shape a copy-edit produces.

They cannot both be right, and which one is correct needs whoever ran the synthesis.
It is a one-token fix in whichever document is wrong, and it sits in the abstract of
both.

## 4. Deliberately NOT flagged

Checked and found correct, listed so nobody re-opens them:

- The **83 vs 84** count. The v2 replacement corrected **both the title and the
  abstract**; `ERRATA_2026-06-14.md` is complete and honest. Nothing left to do.
- **ml_dtypes 0.5.4** — the version string is correct and the cross-validation
  reproduces against it exactly (66,224 codes, 0 divergences).
  *(P3109's version was listed here as fine until pass 69 established it is not —
  see §2. Left visible rather than deleted, because a checklist that quietly moves
  an item from "settled" to "open" is harder to trust than one that says it did.)*
- Paper A's **related-work positioning** — it already names posit, takum, OCP-MX and
  IEEE P3109 explicitly. An earlier draft of this package implied otherwise; that
  was wrong and is corrected.
- The **`φ² + 1/φ² = 3`** anchor, the **SHA-256** fingerprints, the **ml_dtypes**
  cross-validation, the **no-superiority-claim** discipline — all verified, all
  hold.

## 5. What the papers could claim and don't

Measured, in the repository, and mentioned in neither paper. All of §2 of the
dossier, but the three that would most change a reader's impression:

- **The corpus uses three distinct exactness techniques** — exact rational,
  log-domain, and an algebraic ring ℚ[φ] that closes via the papers' own anchor
  `φ² = φ + 1`. Most catalogues have one.
- **Wide formats serialise as `A·2^B` dyadic strings** with an explicit
  `value_encoding` field. This is a working answer to "how do you publish bit-exact
  vectors for formats wider than a double?" — `gf1024` has a 632-bit mantissa — and
  no document anywhere says the corpus does it.
- **Commutativity holds everywhere add and mul are exposed**, now including every
  GoldenFloat rung through gf1024 — 8,865 ordered pairs, zero violations.

---

## 5a. One phrasing to avoid — software and hardware are not two witnesses

Read the harness before writing the sentence. The compute cores carry no expected
values at all: `corona_compute_gf16_add_ax7203.v` is a UART transponder — the host
sends two operands, the board returns a sum. The comparison happens on the host, and
`conformance/*_conformance_ax7203.py` gets its expected values from `gf_ref` — the
same module the software law-proofs use.

So **do not write that the arithmetic was "verified in software and confirmed on
hardware"** as though those were two independent confirmations. They are one
definition checked twice: once by reasoning about it, once by executing an RTL
implementation of it on silicon. The hardware result is a statement about the RTL,
which is worth stating and is a different claim.

Nothing in the repository overstates this — `gf_ref`'s own docstring says it is a
software oracle and that the compute-hardware checkmark closes only on the board. The
risk is in the paper's summary sentence, not in the artefact.

**Both main operations do have an independent second formulation, and that may be claimed.** `formal/verify_mul_oracle.py` runs
three structurally distinct implementations against each other — the RTL port, an
exact-integer-product-then-single-RNE oracle embedded in the formal property file, and
the `Fraction` golden — expressly to rule out bug-equals-bug before the SAT proof.
Re-run independently: **1,269,632 pairs, GF6 and GF8 exhaustive, zero disagreement.**
ADD now has the same, added in pass 97: `research/verify_add_oracle.py` puts a
third oracle beside the RTL port and the `Fraction` golden — one that bisects the
format's grid of representable values and shares no rounding code with either, so
it has no exponent extraction, no alignment shift and no sticky bit to inherit a
fault from. **971,008 pairs, GF6 and GF8 exhaustive, every structural-boundary
pair including Inf and NaN, zero disagreement** — and `--self-check` injects three
rounding faults to demonstrate the comparison would have caught them.

For both operations the support is from a second *software* formulation, not from
the board. That is the distinction to keep in the sentence.

---

## 5b. The strongest methodological claim either paper can make, and neither does

A 512-vector conformance suite ran on real silicon, reported **512/512 bit-exact**, and
the cell it tested was **defective**. A second suite of the same size, on the same
board, through the same adder, found the defect at 508/512.

The cell is shared: `SUB(a,b)` is computed as `ADD(a, b XOR sign)` in both the RTL and
the golden, so ADD and SUB exercised one adder. The defect was IEEE-754 ordering —
zero-passthrough evaluated before the NaN branch, so a zero paired with a NaN returned
that NaN's **raw payload** instead of the canonical quiet NaN (fixed in `711f5d572`).

Why one suite was blind:

- gf16 ADD carries exactly one NaN, `0x7E01` — and `0x7E01` **is** gf16's canonical
  quiet NaN, so the defective path returned the right answer by coincidence.
- ADD's b-position set holds **no NaN at all**: two zeroes, two subnormals, four
  ordinary finites.
- gf16 SUB seeds `0xFFFF`, a NaN whose payload is **not** canonical. Against a zero,
  the defect is immediate.

**Reproduced exactly, with no board** — `research/vector_blindness.py` replays the
pre-fix behaviour over each suite's own vectors: **ADD 0 failures, SUB 4**, matching
the silicon's 512/512 and 508/512, with the four pairs named.

So the difference was not sample size, not the operation, and not the hardware: one
vector set contained a non-canonical NaN payload and the other did not. That is a
transferable argument for enumerating structural boundaries rather than sampling, and
it is backed by a defect that actually shipped rather than by a constructed example.
A conformance-suite paper that can say this has something most cannot.

It also carries a caution the papers should state: **a bit-exact hardware result
bounds the vectors, not the cell.**

---

## 5c. Three conformance suites repaired — and this one needs your board

Pass 98's question, asked of all 106 conformance scripts (`research/audit_vector_coverage.py`).
41 analysed, 62 not a GF format, **3 unparseable and reported as unknown rather than
clean**. Only **5** target a format carrying Inf/NaN — `gf_ref` gives `has_inf` to
gf16 alone — and **3 of those 5 were incomplete**.

**The serious one: `gf16_sub` was testing binary16 constants.** gf16 is 1+6E+9M, bias
31. Four of its eight seeded "specials" were binary16 values:

| constant | labelled | actually, in gf16 | is that value in… |
|---|---|---|---|
| `0x7C00` | +Inf | **a normal, 2³¹** | binary16 |
| `0x7C01` | NaN | **a normal, 2³¹** | binary16 |
| `0xFC00` | −Inf | **a normal, 2³¹** | binary16 |
| `0x3C00` | 1.0 | **2⁻¹** (gf16's 1.0 is `0x3E00`) | binary16 |

So the suite tested **no Inf at all** and exercised ordinary normals under the names
Inf and NaN. The one constant that landed, `0xFFFF`, is a NaN in *both* layouts — and
it is the one through which this suite caught the defect that shipped. The catch was
real and it was luck.

**Repairs, measured against the shipped defect:**

| suite | before | after |
|---|---|---|
| `gf16_sub` | 4 catches / 512 | **8** |
| `gf16_add` | **0** catches / 512 | **6** |

`gf16_mul` had the same blind spot; probing it found **0 divergences over 108
special-value pairs**, so the gap is closed preventively — a gap in the vectors is not
a defect in the cell. Constants are now derived from the format rather than written as
hex, so they cannot drift again. The audit now reports 5 of 5 complete.

> **This needs a decision only you can make.** gf16 ADD, MUL and SUB each carry a
> recorded `N/N` established under the *old* vectors. Those figures no longer describe
> what the code runs. Nothing suggests the cells are wrong — but the three proofs need
> a re-run on the AX7203 to stand under the corrected vectors, or the changes reverted.
> I do not have the board.

---

## 5d. One paragraph that turns a limitation into a result

Three independent measurements, made in three different passes for three different
reasons, reached the same boundary:

| route | result |
|---|---|
| `takum32` vs **`libtakum`** | **12 of 15** vectors differ by exactly one ULP, **none by more** |
| **numpy 2.4.4** validation sets | **26,615** rows, 20 transcendental operations, tolerance 1–4 ULP, **0 rows claim exactness** |
| **silicon** — `lns16` on AX7203 | `472/576 bit-exact, 104 known-limitation(s), 0 hard-fail(s)`, all 104 one-ULP subnormal residuals |

Software reference, third-party implementation and hardware agree on where the line
falls: **bit-exactness is attainable over the decidable class, and logarithmic
evaluation is not in it.** Neither preprint says this, and saying it converts an
apparent weakness into a stated boundary with three measurements behind it.

**Ready-to-paste text is in `ONE_ULP_BOUNDARY_READY_TO_PASTE.md`**, including the
sentence that must accompany it — the corpus is exact *because of the problem it
chose*, not through superior rigour, and numpy is the deeper artefact on operation
coverage (20 operations against 1). A reviewer who knows numpy will check that; saying
it first is both more accurate and more persuasive than being corrected.

---

## 5e. A section neither paper has: how the suite was verified

Both preprints describe **what** the corpus contains. Neither describes **how it was
checked against the possibility of being uniformly wrong** — which is the half a
referee will care about most, and it is already done.

| operation | third oracle, sharing no code with the other two | result |
|---|---|---|
| **MUL** | exact integer product, single RNE | **1,269,632 pairs, 0 divergences** |
| **ADD** | nearest-representable by bisection over the format's grid | **971,216 pairs, 0 divergences** |

GF6 and GF8 exhaustive in both. And the harness proves it discriminates: four faults
injected into the third oracle, each required to be caught — three plausible rounding
errors and **one that actually reached silicon** in this project's own adder.

**Ready-to-paste text is in `VERIFICATION_METHOD_READY_TO_PASTE.md`**, including §3 —
the reproduction showing why gf16 ADD reported 512/512 on a defective cell while gf16
SUB, the same cell through a sign flip, reported 508/512. Replaying the defect over
each suite's own vectors gives **ADD 0, SUB 4**, matching the silicon exactly.

---

## 5f. The three §5 items, now written as paragraphs

§5 lists these as *"what the papers could claim and don't"*. They are now drafted, in
**`THREE_MORE_RESULTS_READY_TO_PASTE.md`**, with every figure re-run rather than quoted.

| result | figures | why it is worth the space |
|---|---|---|
| **P3109 maps layout, not values** | **252** configurations (119 signed, 133 unsigned); **258,524** finite codes differing by **one distinct ratio, exactly 2** | *A decoder defect scatters.* A constant offset against an independently generated standards-body table is two correct decoders reading two conventions — so this **confirms** the decode law rather than qualifying it |
| **Three exactness techniques** | **12** oracles, **19,110** values, all exact carriers | most catalogues carry one; the third is the ring **ℚ[φ]**, closing on the papers' own anchor `φ² = φ + 1`. Sampled, not exhaustive — and the draft says so |
| **Wide formats serialise as `A·2^B`** | `gf1024` carries a **632-bit** mantissa | a working answer to "how do you publish exact vectors wider than a `double`?" — no decimal literal parsed into a binary64 survives above ~53 bits |

Item 1 costs **one word in Paper B's abstract**: *"corresponding"* → *"same-layout"*.

---

## 5g. Thirteen formats the harness already covers, and three of them are the competitor

Not a correction — **capacity neither paper mentions.** `gen_conformance_pack.py`
carries **84** golden oracles; the catalogue publishes **83** packs. Comparing the sets
leaves **thirteen formats with no published pack**, and every one generates a pack
today with a SHA-256 and **zero decode errors**: 1,161 vectors in total. The machinery
reaches **96** where the catalogue publishes 83.

**Retracted: do not publish `tekum8/16/32`.** An earlier version of this line
recommended them as the strongest item in the set. The oracle's own header rules it
out — the per-trit specification needs the full 23-page paper, the abstract does not
give the offset tables or the balance rule, and what is implemented is a **structural
model reverse-engineered from `takum64_decode.v` and interpreted linearly** where real
takum is logarithmic, with three `# TODO: verify from full paper` markers still open.

Publishing those as `tekum` vectors would misrepresent another author's published
format under its own name. The catalogue is right to exclude them. `takum8/16/32/64`
*are* published and are a different format with a real reference behind them. If the
comparison is worth making, implement against the paper's tables first.

**Ten of the thirteen are now validated** — five against a third party (`uint4/8/16/32`,
`mxfp8_e4m3`; 66,135 codes, 0 divergences) and five by construction, each against a
format already among the 83: `bfloat32` ≡ `binary32`, `bfloat24` ≡ `binary32` truncated,
`pdp11_float` ≡ `vax_f`, `x87_48bit` ≡ `x87_fp80` over a 32-bit mantissa, and `mxint8`'s
**element** decode ≡ `int8` on all 256 codes. Only `tekum8/16/32` remain unvalidated,
and they are the three that would need an external build.

`mxint8` is deliberately not a third alias. An MX block is one shared `e8m0` scale byte
plus N elements, so two formats whose *elements* decode alike are still different
formats — it agrees at one level and differs at another, where `bfloat32` and
`pdp11_float` agree at every level.

**Two of the thirteen are aliases, not new formats.** `bfloat32` decodes exactly as
`binary32` and `pdp11_float` exactly as `vax_f`, both of which the catalogue already
publishes. `x87_48bit` is *not* in that category — a 32-bit mantissa against 64 is
genuinely narrower. So the headline is **eleven new formats and two aliases**, and the
aliases should be a deliberate choice: published with a note on what the second name is
for, or left out.

**The honest bound, which must travel with it:** generating is not publishing. Zero
decode errors shows the oracle is self-consistent and terminates, not that its values
are right. The 83 went through review, third-party cross-validation where one exists,
and hardware verification in 44 cases. These thirteen have had none of that, so the
claim is *"working oracles, not yet reviewed packs"*.

**Ready-to-paste text, with both the publish and the do-not-publish sentence, is in
`THIRTEEN_MORE_FORMATS_READY_TO_PASTE.md`.** The second costs nothing: *"A further
thirteen formats have working decode references in the repository but no published
pack, pending review."*

---

## 6. The artefact itself has been repaired

The papers point a reader at `github.com/gHashTag/t27`. Five defects that a reader
following that pointer would have hit are fixed and merged (#1576, #1578, #1582,
#1584, #1589):

- the pack generator **could not run on a clean checkout** — its catalog came from an
  uncommitted `/tmp` path, so the corpus could be read but not regenerated;
- re-running that generator **silently reverted** the 2026-07-05 promotions,
  rewriting the index from 75/0/8 back to 69/6/8;
- the **six witness decode references failed standalone**, defaulting to a path under
  `/home/user/workspace` — these are the files honesty rule #10 points a sceptic at,
  and running one is the first thing an auditor does;
- CI demanded an erratum the v2 replacement had already made, on every run;
- `cocotb_ref_model.py` **could not be imported at all**.

Regeneration now reproduces the committed corpus exactly — 83/83 digests unchanged —
and a new gate locks the index against the packs it summarises.

---

## 7. What was re-verified on 2026-08-02, and what could not be

This checklist grew over forty passes. Section 0 was last checked against the
**published** arXiv text at pass 71. This pass re-ran everything re-runnable and states
plainly what it could not reach.

**Re-verified by execution, still holding:**

| claim | where | result |
|---|---|---|
| φ-rule over the catalogued widths | §2, `(9/9)` question | **17/17** satisfy `e = round((N−1)/φ²)`; no width lands on an exact .5, so the unstated rounding convention is moot |
| commutativity and the arithmetic laws | §5 | **8,865** ordered pairs, **0** violations |
| every file this checklist cites | throughout | **19 of 19** resolve — 13 here, 4 in the papers' own repositories as §0 says, 2 in `t27` |

**Could not be re-verified, and why** (one of the two was closed the same day):

- ~~**ml_dtypes cross-validation**~~ — **settled the same day.** `ml_dtypes 0.5.4` was
  installed and `research/crossval_ml_dtypes.py` re-run: **66,224 codes compared, 0
  divergences**, across `bfloat16`, `float8_e4m3fn`, `float8_e5m2`, `float4_e2m1fn`,
  `float6_e2m3fn`, `float6_e3m2fn`, `int4` and `uint4`. The run also reports **14
  zero-sign codes the oracle's container cannot carry**, excluded explicitly rather
  than silently — worth keeping in any sentence that quotes the figure.
- **Everything in §1 that quotes the published papers** — abstracts, reference lists,
  the TTSKY26b clause. Verifying those needs the arXiv text, and the web-fetch tool has
  been unavailable across fourteen consecutive attempts (a fetch of `example.com` fails
  identically, so it is the tool and not the target). Those claims were correct at
  pass 71 and have not been re-read since.

Nothing was found to have gone stale except the self-correction count in the caution
below, which is now stated with its derivation.

---

### One caution about this checklist

**27** blocks across ten spec files are typed `correction` — measurements or fixes of
mine that turned out to be wrong and were withdrawn or repaired before publication.
That figure is re-derivable: `grep -c '^correction' specs/numeric/*.t27`, through pass
112. An earlier version of this line said "roughly fifteen across seventy passes",
which was true when written and is no longer. Examples:
a defaulted format width that manufactured 57,330 phantom defects, an oracle loader
that silently skipped two formats, API throttling read as dead references, a URL
typo that made 238 files look unreadable. One correction was *not* caught in time — a
"fix" to `takum_ref.py` shipped as a PR and was retracted unmerged once the module's
docstring turned out to document the behaviour as deliberate.

So treat §1 as claims with evidence attached, not as instructions. Every line names
where to check it. **The science holds** — the defects are in citations and in things
left unsaid, not in the results.
