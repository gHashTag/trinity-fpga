# GF-T16 — arXiv material, v2

> Supersedes `ARXIV_GFT16_SNIPPET.md`. For the GoldenFloat paper (arXiv:2606.05017)
> or the catalogue (2606.09686); long enough to stand alone if you prefer a third paper.
>
> Everything below was measured or **re-measured independently on 2026-08-08**. The v1
> snippet carried two things that would not survive review, and both are fixed here:
> a mislabelled axis, and a caveat saying the hardware argument was architectural
> rather than synthesized. It is synthesized now.

---

## What changed since v1, and why it matters

**1. The accuracy bins are powers of two, not decades.** v1 labelled them "dec".
They are `|e|`. This is not cosmetic: GF-T16's exponent reaches ±40 *in powers of
two*, about ±12 decades. Binned in actual decades the far column is not a win —
GF-T16 overflows there and tekum16's unbounded regime keeps working (measured:
1,458 of the far-bin values clip). A reviewer who checks the labelled axis finds
overflow where the table promises 5.5× and concludes the number was invented. The
result is real; the label was not.

**2. The ratios are now the measured ones.** v1 rounded to "3× and 5.5×".
Re-derived from the claim rather than by re-running the script that produced it —
encode, decode, relative error, fixed seed, same oracles — they come out 2.84×
and 5.53×.

**3. The hardware argument is no longer architectural.** v1 said ternary
energy/area superiority was "an architectural argument … not a synthesized
number — no ternary process exists to synthesize on." That remains true *for a
ternary fabric*. But GF-T's cost **on a binary fabric** is now measured, and it is
the stronger claim: the format is cheap even where its native advantage does not
apply.

---

## LaTeX — accuracy (replaces the v1 subsection)

```latex
\subsection{GF-T16: a ternary-native GoldenFloat}
Tapered formats such as takum~\cite{takum} and its balanced-ternary descendant
tekum~\cite{tekum} win dynamic range with a variable-length regime field, at the
cost of a barrel-shift regime decode and precision that tapers to $\sim$4 mantissa
bits at the extremes. We introduce \textbf{GF-T16}, a fixed-field GoldenFloat whose
exponent is a \emph{balanced-ternary} number:
\[
\text{GF-T16}=[\,s\,|\,E{=}4\ \text{balanced-ternary trits}\,|\,M{=}9\ \text{bits}\,],\quad
v=(-1)^{s}\Bigl(1+\tfrac{M}{2^{9}}\Bigr)2^{e},\ e=\sum_i t_i 3^i\in[-40,40].
\]
GF-T16 has \emph{no regime decode}, adds its exponent as a native balanced-ternary
operation on a ternary fabric, and keeps a \emph{uniform} 9-bit mantissa across its
whole range. Four trits give $3^4{=}81$ exponent steps.

Table~\ref{tab:gft16} reports mean relative round-trip error binned by
\emph{binary exponent} $|e|$ (6{,}000 values, $2^{-38}\!\dots\!2^{38}$, random
sign): GF-T16 ties tekum16 near unity and beats it $2.84\times$ at mid range and
$5.53\times$ at far range, while eliminating the clipping GF16's 6-bit exponent
suffers at the top of that interval.

\begin{table}[t]\centering
\caption{Round-trip mean relative error by binary exponent magnitude.
Bins are powers of two, not decades.}
\label{tab:gft16}
\begin{tabular}{lrrr}
\toprule
magnitude & GF16 ($\varphi$) & \textbf{GF-T16} & tekum16 \\
\midrule
$|e|<8$      & $3.43\mathrm{e}{-4}$            & $\mathbf{3.56\mathrm{e}{-4}}$ & $3.27\mathrm{e}{-4}$ \\
$|e|\,8$–$20$  & $3.57\mathrm{e}{-4}$            & $\mathbf{3.52\mathrm{e}{-4}}$ & $1.00\mathrm{e}{-3}$ \\
$|e|\,20$–$38$ & $6.98\mathrm{e}{-3}$\,(479 clip) & $\mathbf{3.53\mathrm{e}{-4}}$ & $1.95\mathrm{e}{-3}$ \\
\bottomrule
\end{tabular}
\end{table}

The exponent-trit budget $E_t$ tunes the range/precision Pareto: $E_t{=}3$
($M{=}10$) is most precise but clips 17\% of the tails; $E_t{=}4$ ($M{=}9$) is the
knee and is what we adopt; $E_t{=}5,6$ buy range for mantissa.
```

---

## LaTeX — hardware realization (new; this is the section v1 could not write)

```latex
\subsection{Hardware realization}
The GF-T multiplier was synthesized with Yosys and placed and routed with
nextpnr-xilinx on a Xilinx XC7A200T (Artix-7), with hard multipliers disabled so
that the figures describe fabric alone. Table~\ref{tab:gft-hw} gives the ladder.
Latency is one cycle and throughput one result per cycle.

\begin{table}[t]\centering
\caption{GF-T multiplier, post-route on XC7A200T, no DSP blocks. One harness
across all three rungs, so the rows are comparable.}
\label{tab:gft-hw}
\begin{tabular}{lrrr}
\toprule
rung & LUTs & $F_{\max}$ & latency \\
\midrule
GF-T8  & $50$    & $153.23$\,MHz & 1 cycle \\
GF-T16 & $212$   & $131.73$\,MHz & 1 cycle \\
GF-T32 & $1{,}477$ & $83.27$\,MHz  & 1 cycle \\
\bottomrule
\end{tabular}
\end{table}

For context, a published Altera \texttt{ALTFP\_MUL} on a Cyclone~IV reports
119--132\,MHz at 6--10 cycles of latency, using 832--1041 logic elements
\emph{and} 18 embedded multipliers; posit multiplier studies report 95--572 LUTs
with 4.28--15.55\,ns of logic delay. GF-T16 is ahead on frequency, area,
hard-multiplier count and latency simultaneously, on a fabric that gives it no
ternary advantage at all.

Isolating the pipeline register: the combinational multiplier closes at
$81.35$\,MHz and the two-stage version at $147.32$\,MHz, for one cycle of latency.
The cut is between the significand product and the renormalization --- a
$10\times10$ multiply, then a carry test, a saturating exponent add and a bit
select.
```

---

## LaTeX — a reproducibility note worth including

```latex
\subsection{Interface width dominates the arithmetic}
Our first synthesizable realization declared every port and the significand
product 32 bits wide. Nothing in GF-T16 is 32 bits: the mantissa field is 9, so
$1{+}M$ is 10, their product is exactly 20, and the exponent offset never exceeds
$\mathrm{OFFSET\_MAX}{=}80$, which is 7. Synthesis built a $32\times32$ multiplier
and a 32-bit comparison tree and charged for it: $1{,}179$ LUTs, or three DSP48
blocks, against $219$ LUTs and none once the buses are the size of the values they
carry. The arithmetic is unchanged; equivalence is established over $321{,}156$
input combinations.

The same width also decides correctness. At GF-T32 the significand product needs
52 bits, so the 32-bit wire truncates and the module returns wrong results while
appearing to support the rung --- $1{,}995{,}730$ mismatches in $2{,}128{,}964$
combinations against a 64-bit reference. Deriving every width from the format
parameters removes both problems at once, and we recommend it as the default form
for any parametric arithmetic core: a width that is merely \emph{large enough for
the case you tested} is a silent-truncation trap at the next rung.
```

---

## Equivalence evidence (for the artifact appendix)

| Check | Combinations / cycles | Mismatches |
|---|---|---|
| Width-corrected vs original, GF-T16 exhaustive | 321,156 | **0** |
| Width-corrected vs original, GF-T8 | 3,716 | **0** |
| Width-corrected vs original, GF-T16 | 77,444 | **0** |
| Width-corrected vs `gft_mul32` (64-bit ref), GF-T32 | 300,000 | **0** |
| Pipelined vs combinational | 199,994 | **0** |
| Original 32-bit module at GF-T32 vs 64-bit ref | 2,128,964 | **1,995,730** |

The GF-T16 sweep is exhaustive in the sense that matters: the mantissa space is
swept in full at offset pairs that exercise underflow, mid-range and saturation,
then the offsets are swept in full at mantissas that do and do not carry — every
path through the carry, the saturation and the underflow clamp.

---

## Caveats that must survive into the paper

1. **The comparison is against a model of tekum, not tekum itself.** tekum
   (arXiv:2512.10964) is a descendant of takum (arXiv:2404.18603) adapted for
   balanced ternary. Our oracle is a reverse-engineered structural model built
   from takum's field scheme; the full per-trit specification requires the paper.
   **State this explicitly.** The ratios are as good as the model, and a reader
   who discovers the reconstruction unstated will discount everything else.

2. **No head-to-head in hardware.** takum's RTL is public and is VHDL
   (`takum-arithmetic/Takum-Codec-RTL`, arXiv:2408.10594). We did not synthesize
   it alongside GF-T. What is visible in their source and is worth reporting as
   *structure* rather than measurement: their 16-bit codec instantiates a
   725-line FloPoCo leading-zero-counter and barrel shifter generated for a
   Kintex-7 — the regime decode a fixed-field format does not have.

3. **Range is bounded** at ±40 in powers of two, roughly ±12 decades. tekum16's
   regime is not. Fixed fields buy the cheap datapath and the uniform precision;
   range is the price, and it should be stated as a trade rather than omitted.

4. **One device family.** Artix-7 on an open flow. Not multi-corner
   characterization; ASIC numbers will differ.

5. **The ternary-fabric advantage remains architectural.** No ternary process
   exists to synthesize on. The binary-fabric numbers above are the measured
   claim; the ternary claim is reasoning about regime decode and native exponent
   addition, and should be labelled as such.

---

## Artifacts to cite

| Artifact | Path |
|---|---|
| Bit-exact oracle (RNE) | `trinity-fpga/conformance/gft16_ref.py` |
| Comparison oracles | `conformance/tekum_ref.py`, `conformance/gf_ref.py` |
| Format specification | `t27/specs/numeric/gft16.t27` |
| Original RTL | `trinity-fpga/build/gft_mul8/gft_mul.v` |
| Width-derived RTL + pipeline + testbenches | `trinity-fpga/fpga/gft/` (PR #510) |
| Accuracy study | `trinity-fpga/research/GFT16_BEATS_TEKUM16_2026-08-05.md` |

## Before submitting

- [ ] Axis says **powers of two** everywhere, including any figure captions
- [ ] Ratios read 2.84× and 5.53×, not 3× and 5.5×
- [ ] The tekum-is-a-reconstruction caveat is in the body, not only a footnote
- [ ] Tool versions stated: Yosys 0.65, nextpnr-xilinx 1743d0f, Icarus 13.0
- [ ] Generative-AI use disclosed if the venue asks (arXiv does not; NLnet does)
- [ ] `\cite{takum}` → arXiv:2404.18603, `\cite{tekum}` → arXiv:2512.10964
