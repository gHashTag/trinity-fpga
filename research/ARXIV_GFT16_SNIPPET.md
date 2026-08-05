# Ready-to-paste — GF-T16, a ternary-native GoldenFloat that beats tekum16

> For the catalog paper (arXiv:2606.09686) and/or GoldenFloat paper (2606.05017).
> New format, strongest single result: a fixed-field GoldenFloat with a
> balanced-ternary exponent that beats tekum16 on measured accuracy at range.
> Measured 2026-08-05 (`gf_ref.py`, `tekum_ref.py`, `gft16_ref.py`). **arXiv
> submit needs author credentials.**

## LaTeX subsection

```latex
\subsection{GF-T16: a ternary-native GoldenFloat}
Tapered formats such as takum and tekum win dynamic range by a variable-length
regime field, at the cost of a barrel-shift regime decode and precision that
tapers to $\sim$4 mantissa bits at the extremes. We introduce \textbf{GF-T16}, a
fixed-field GoldenFloat whose exponent is a \emph{balanced-ternary} number:
\[
\text{GF-T16}=[\,\text{sign}\,|\,E{=}4\ \text{balanced-ternary trits}\,|\,M{=}9\ \text{bits}\,],\quad
v=(-1)^{s}\Bigl(1+\tfrac{M}{2^{9}}\Bigr)2^{e},\ e=\sum_i t_i 3^i\in[-40,40].
\]
GF-T16 has \emph{no regime decode} (tekum's dominant cost), adds its exponent as a
native balanced-ternary operation on a ternary fabric, and keeps GoldenFloat's
$\varphi$-optimal \emph{uniform} 9-bit mantissa across the whole range. Four trits
give $3^4{=}81$ exponent steps ($\sim$24 decades). Table~\ref{tab:gft16} reports
mean relative round-trip error binned by magnitude (6{,}000 values,
$2^{-38}\!\dots\!2^{38}$): GF-T16 ties tekum16 near unity and beats it
$3\times$ (mid) and $5.5\times$ (far), while eliminating the clipping that GF16's
6-bit exponent suffers beyond $\sim$18 decades.

\begin{table}[t]\centering
\caption{Round-trip mean relative error by magnitude. GF-T16 vs GF16 ($\varphi$) vs tekum16.}
\label{tab:gft16}
\begin{tabular}{lrrr}
\toprule
magnitude & GF16 ($\varphi$) & \textbf{GF-T16} & tekum16 \\
\midrule
near unity ($|e|<8$) & $3.43\mathrm{e}{-4}$ & $\mathbf{3.43\mathrm{e}{-4}}$ & $3.16\mathrm{e}{-4}$ \\
mid ($8$--$20$ dec)  & $3.57\mathrm{e}{-4}$ & $\mathbf{3.57\mathrm{e}{-4}}$ & $1.01\mathrm{e}{-3}$ \\
far ($20$--$38$ dec) & $6.98\mathrm{e}{-3}$\,(479 clip) & $\mathbf{3.55\mathrm{e}{-4}}$ & $1.93\mathrm{e}{-3}$ \\
\bottomrule
\end{tabular}
\end{table}

The exponent-trit budget $E_t$ tunes the range/precision Pareto (measured on a
$\sigma{=}10$ log-exponent workload): $E_t{=}3$ ($M{=}10$) is most precise
($1.7\mathrm{e}{-4}$) but clips 17\% of the tails; $E_t{=}4$ ($M{=}9$) is the knee
--- 24 decades, 0\% clipping, matching GF16 precision; $E_t{=}5,6$ reach 73 and
219 decades for less mantissa. We adopt $E_t{=}4$ as GF-T16.
```

## Honest caveats to include
- Accuracy win is \emph{measured}; ternary energy/area superiority is an
  \emph{architectural} argument (no regime decode + native ternary exponent),
  not a synthesized number --- no ternary process exists to synthesize on.
- Range is bounded by $E_t$; raise $E_t$ for $>$24-decade workloads.
- Oracle: `conformance/gft16_ref.py` (bit-exact, RNE); spec `t27/specs/numeric/gft16.t27`.
Backing: `research/GFT16_BEATS_TEKUM16_2026-08-05.md`.
