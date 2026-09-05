# At matched width, it is parity — on all three axes (W946)

Six waves of measurement end here. Every advantage this project reported for the
φ-lattice at four to six bits has now been re-measured against a **same-width**
IEEE-style float, and each one either shrinks to insignificance or turns out to be
an artefact of our own instruments.

## Axis 1 — cost, at six physical bits

Every decoder generated from its own oracle, priced behind one identical multiply:

| format | physical bits | grid values | decoder | **consumer** |
|---|---:|---:|---:|---:|
| **TNF4** | 6 | 58 | 8.00 | **51.29** |
| `fp6 e2m3` | 6 | 63 | 7.00 | **50.29** |
| `fp6 e3m2` | 6 | 63 | 7.00 | **50.29** |
| `fp4 e2m1` | 4 | 15 | 3.00 | 19.14 |

**TNF4 is 2 % dearer than either six-bit float.** The "2.76× cheaper than fp8"
of W941 compared six bits against eight; at matched width the cost advantage is
gone.

## Axis 2 — accuracy, at six physical bits

From W945, learned scale, five seeds, paired: TNF4 − fp6 e3m2 is **+0.11 pp**
(MNIST, t 2.2) and **+0.17 pp** (Fashion, t 1.2 — **not significant**), and with
quantised activations on Fashion **fp6 e3m2 wins by 0.42**.

## Axis 3 — stability, and it was our recipe

W945's surviving claim was that TNF4 trains reliably where the fp6 formats do not
(σ 0.21 against 46.09 and 32.33). Logging the learned scales showed the mechanism:
in **every** failing run the layer-2 activation scale collapses monotonically —
0.81 → 0.29 → **0.0065** — and in every surviving run it settles. That is the known
LSQ failure mode, and our implementation **omitted the gradient-scaling factor**
`1/√(N·Q_p)` that exists to prevent it.

Adding it:

| format | without the factor | with the standard factor | failed runs |
|---|---:|---:|---|
| **TNF4** | 96.76 ± 0.21 | 96.70 ± 0.38 | 0/5 → 0/5 |
| **`fp6 e3m2`** | 73.63 ± 32.33 | **96.58 ± 0.56** | 2/5 → **0/5** |
| `fp6 e2m3` | 45.01 ± 46.09 | 30.19 ± 37.13 | 3/5 → 4/5 |

**`fp6 e3m2` is completely fixed by the standard factor** and lands within
0.12 pp of TNF4. The stability advantage against the fair peer was **ours to
lose, and we lost it by omitting a line from the recipe we cited.**

`fp6 e2m3` is not fixed — its two-bit exponent leaves too little dynamic range for
a sparse task, which is the same mechanism as everywhere else in this session and
is a property of that format rather than of the comparison.

## The end state

> **At six physical bits, TNF4 is at parity with `fp6 e3m2`: 2 % dearer in
> datapath cells, +0.11–0.17 pp in accuracy (not significant on one task), and
> statistically indistinguishable in training stability once the quantiser is
> implemented as its authors specify.**

That is not the paper's claim, and it is not nothing. A novel lattice reaching
parity with a mature IEEE-style encoding at equal width means the φ-structure costs
nothing to adopt — and the project's real assets are elsewhere: the mathematics
(φ-uniqueness, Z[φ] closure), the 8-bit null that survived every attempt to break
it, and the measurement apparatus itself.

## The full correction chain

| wave | claimed | why it moved |
|---|---|---|
| W940 | +37.9 / +64.4 pp accuracy | PTQ only |
| W943 | +0.19 / +0.89 | trained through the quantiser |
| W944 | +1.58 / +0.91 | learned scale |
| W945 | **+0.11 / +0.17**, n.s. on one task | width-matched at last |
| W941 | 2.76× cheaper | compared against 8 bits |
| **W946** | **2 % dearer** | width-matched cost |
| W945 | stability: σ 0.21 vs 46 | our LSQ lacked its gradient factor |
| **W946** | **parity** (0/5 failures both) | factor restored |

Eight steps, every one against this project's interest, every one forced by the
previous step's own stated principle.

---

*φ² + φ⁻² = 3 | TRINITY*
