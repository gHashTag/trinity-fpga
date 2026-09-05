"""Two figures for the prior-work section, drawn from computation only.

Figure 1 (tnf_phi_split): the field-layout rule of the GoldenFloat family,
e = round((N-1)/phi^2), m = N-1-e, across the widths the family names
(arXiv:2606.05017). Nine widths are the ones whose realised exponent widths the
rule reproduces; three are consistent extensions. The right panel shows m/e
approaching phi^2.

Figure 2 (tnf_lucas): the Lucas-exact identity phi^(2n) + phi^(-2n) = L_(2n).
Evaluated exactly in integers the deviation is zero for every n; evaluated in
binary64 the deviation grows and passes 1/2, at which point the nearest integer
is no longer recoverable. Both curves are computed here, not quoted.
"""
from fractions import Fraction
import math

import canon_style  # noqa: F401  (installs the engraving house style)
import matplotlib.pyplot as plt

PHI = (1.0 + 5.0 ** 0.5) / 2.0
PHI2 = PHI * PHI

# --- Figure 1 -------------------------------------------------------------
REPRODUCED = [4, 8, 12, 16, 20, 24, 32, 64, 256]
EXTENDED = [128, 512, 1024]
WIDTHS = sorted(REPRODUCED + EXTENDED)


def split(n):
    e = round((n - 1) / PHI2)
    return e, n - 1 - e


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(4.80, 2.45))

es = [split(n)[0] for n in WIDTHS]
ms = [split(n)[1] for n in WIDTHS]

ax1.plot(WIDTHS, ms, marker="o", label="mantissa $m=N-1-e$")
ax1.plot(WIDTHS, es, marker="s", linestyle="--", label="exponent $e$")
for n in REPRODUCED:
    e, m = split(n)
    ax1.plot([n], [e], marker="s", markerfacecolor="black", markersize=4.5)
ax1.set_xscale("log", base=2)
ax1.set_yscale("log", base=2)
TICKS = [4, 8, 16, 32, 64, 256, 1024]
ax1.set_xticks(TICKS)
ax1.set_xticklabels([str(w) for w in TICKS], fontsize=7.2)
ax1.set_xlabel("total width $N$ (bits)")
ax1.set_ylabel("field width (bits)")
ax1.set_title("The rule $e=\\mathrm{round}((N-1)/\\varphi^{2})$")
ax1.legend(loc="upper left")

ratios = [m / e for m, e in zip(ms, es)]
ax2.plot(WIDTHS, ratios, marker="o", label="$m/e$ realised")
ax2.axhline(PHI, linewidth=0.8, linestyle=":", color="black")
ax2.annotate("$\\varphi=%.4f$" % PHI, xy=(WIDTHS[5], PHI),
             xytext=(6, 6), textcoords="offset points", fontsize=7)
ax2.set_xscale("log", base=2)
ax2.set_xticks(TICKS)
ax2.set_xticklabels([str(w) for w in TICKS], fontsize=7.2)
ax2.set_xlabel("total width $N$ (bits)")
ax2.set_ylabel("$m/e$")
ax2.set_ylim(1.2, 2.15)
ax2.set_title("The split converges on $\\varphi$, not $\\varphi^{2}$")
ax2.legend(loc="lower right")

fig.tight_layout()
fig.savefig("tnf_phi_split.pdf")
plt.close(fig)

# --- Figure 2 -------------------------------------------------------------
# Exact integer path: L_k by recurrence, and phi^(2n)+phi^(-2n) as an element of
# Z[phi] reduced by phi^2 = phi + 1 -- an integer, so the deviation is exactly 0.
def lucas(k):
    a, b = 2, 1  # L_0, L_1
    for _ in range(k):
        a, b = b, a + b
    return a


def phi_pow(k):
    """phi^k = a + b*phi with integer a, b, from phi^2 = phi + 1."""
    a, b = 1, 0
    for _ in range(k):
        a, b = b, a + b  # (a + b phi) * phi = b + (a+b) phi
    return a, b


NS = list(range(1, 41))
exact_dev = []
float_dev = []
for n in NS:
    k = 2 * n
    a, b = phi_pow(k)
    # phi^-k = (-1)^k * (a' + b' phi) with L_k = phi^k + (-phi)^-k; use the
    # closed identity phi^k + phi^-k = L_k for even k, verified in integers.
    target = lucas(k)
    # exact: the Z[phi] reduction plus its conjugate leaves an integer
    exact = Fraction(2 * a + b) - Fraction(target)  # phi^k + conj = 2a + b
    exact_dev.append(abs(float(exact)))
    val = PHI ** k + PHI ** (-k)
    float_dev.append(abs(val - target))

fig, ax = plt.subplots(figsize=(4.80, 2.55))
ax.plot(NS, [max(d, 1e-18) for d in float_dev], marker="o",
        label="binary64 evaluation of $\\varphi^{2n}+\\varphi^{-2n}$")
ax.plot(NS, [max(d, 1e-18) for d in exact_dev], marker="s", linestyle="--",
        label="integer path in $\\mathbb{Z}[\\varphi]$: deviation exactly $0$")
ax.axhline(0.5, linewidth=0.8, linestyle=":", color="black")
ax.annotate("$1/2$: past here binary64 no longer recovers $L_{2n}$",
            xy=(NS[24], 0.5), xytext=(0, -14), textcoords="offset points",
            fontsize=7, ha="left")
ax.set_yscale("log")
ax.set_xlabel("$n$")
ax.set_ylabel("$|\\,$value$\\,-\\,L_{2n}|$")
ax.set_title("The identity is exact in integers and drifts in binary64")
ax.set_ylim(1e-19, 1e6)
ax.legend(loc="upper left", framealpha=1.0, fontsize=7)
fig.tight_layout()
fig.savefig("tnf_lucas.pdf")
plt.close(fig)

print("phi^2 =", PHI2)
print("widths:", list(zip(WIDTHS, es, ms)))
print("float dev at n=20:", float_dev[19], " L_40 =", lucas(40))
print("first n where float dev > 0.5:",
      next((n for n, d in zip(NS, float_dev) if d > 0.5), None))
print("max exact dev:", max(exact_dev))
