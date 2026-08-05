# Ready-to-paste — GFTERNARY vs balanced-ternary hardware cost

> For the GoldenFloat paper (arXiv:2606.05017), soft-logic / honesty section.
> Supports the distinction that GFTERNARY is a golden-ratio *alphabet over a float
> unit*, not a ternary ALU. Measured 2026-08-05, `yosys synth_xilinx -arch xc7`,
> part xc7a200tfbg484-2. **Prepared material — arXiv submit needs author creds.**

## LaTeX subsection (paste into results / soft-logic)

```latex
\subsection{GFTERNARY is a float unit, not a ternary ALU}
The two-bit GFTERNARY alphabet $\{-\varphi,0,+\varphi\}$ is decoded to the FP32
constants $\pm\varphi$ (\texttt{0x3FCF1BBD}, \texttt{0xBFCF1BBD}) and multiplied
by the GoldenFloat \texttt{gf\_mul\_param} core. Its hardware cost is therefore a
floating-point multiply, not ternary arithmetic. Table~\ref{tab:gftern-hw}
reports \texttt{yosys synth\_xilinx} on Artix-7 (XC7A200T): a \emph{single}
GFTERNARY multiply infers two DSP48E1 blocks and $1{,}191$ logic cells, whereas a
genuine balanced-ternary datapath (\texttt{trinet\_mac32}, the
$\text{popcount}(+)-\text{popcount}(-)$ core) computes \emph{thirty-two}
multiply-accumulates in $398$ logic cells with zero DSP. We therefore anchor all
``1.58-bit / ternary compute'' cost claims to the balanced-ternary core and
describe GFTERNARY as a $\varphi$-scaled alphabet evaluated on a float unit.

\begin{table}[t]\centering
\caption{Balanced ternary vs.\ GFTERNARY, Artix-7 XC7A200T (yosys \texttt{synth\_xilinx}).}
\label{tab:gftern-hw}
\begin{tabular}{lrrrr}
\toprule
Core & Work & DSP48E1 & LCs & LUTs \\
\midrule
TF3 \texttt{trinet\_mac32} $\{-1,0,+1\}$ & 32 MACs & 0 & 398 & 504 \\
GFTERNARY \texttt{corona\_gfternary\_mul} $\{-\varphi,0,+\varphi\}$ & 1 mul & 2 & 1191 & 1552 \\
\bottomrule
\end{tabular}
\end{table}
```

## One-sentence abstract/discussion caveat (optional)

> "GFTERNARY denotes a golden-ratio-scaled 2-bit alphabet evaluated on the
> GoldenFloat multiplier (2 DSP48E1, 1191 LC per operation on XC7A200T), and is
> not a ternary-arithmetic cost result; the balanced-ternary core (0 DSP, 398 LC
> for 32 MACs) is the ternary-hardware reference."

Backing data: `trinity-fpga/research/GFTERNARY_vs_BALANCED_TERNARY_HW_2026-08-05.md`.
