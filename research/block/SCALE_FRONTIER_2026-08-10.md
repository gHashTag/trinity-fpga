# The scale applier has three vertices and no winner

Yesterday's claim that the phi grid is the right one for a multiplier-free scale
was withdrawn: APoT is 15x more accurate at one cycle. Measuring the *area* of
each applier, rather than only its accuracy, shows the question was never
one-dimensional.

## Measured, XC7A200T primitives, yosys, DSP inference off

| applier | LUT | cycles | excess error | note |
|---|---:|---:|---:|---|
| multiplier, real `alpha` | 1215 | 1 | 0.0000% | or 2 DSP48 blocks |
| APoT-2, `d=0` | 384 | 1 | 0.1651% | two barrel shifts |
| APoT-4, `d=1` composed | 659 | 1 | -- | four shifts |
| APoT-8, `d=2` composed | 1217 | 1 | -- | eight shifts |
| **`phi^k`, any `d`** | **173** | k | 2.4420% | **no shifter at all** |

Area ratio, phi against APoT: **2.22x** at `d=0`, **3.81x** at `d=1`, **7.03x**
at `d=2`.

## Why, and it is not what we predicted

The prediction was that phi would win through term-count non-growth. It does, but
that is the second effect. The first is that **APoT's shift is by a runtime
value, so it is a barrel shifter** -- 192 LUTs each at 32 bits. The Fibonacci
step `(a,b) -> (b, a+b)` contains no shifter: it is a fixed wire permutation and
one adder.

We had been calling APoT "shift-add" and treating that as free. A shift by a
*constant* is free. A shift by a *variable* is a barrel, and a scale that must
serve any layer is variable by construction.

## Theorems

**T-1 (term growth).** A value represented as a sum of `n` terms drawn from a
multiplicatively closed generating set, composed through `d` scale
multiplications without requantisation, has `n^(d+1)` terms. A value in
`Z[phi]` has two components for every `d`, since `phi^a * phi^b = phi^(a+b)`
adds exponents rather than multiplying terms.

**T-2 (shifter cost).** A runtime-variable shift over `W` bits costs
`Theta(W log W)` LUTs; a fixed permutation costs zero. An `n`-term APoT applier
is therefore `Theta(n W log W)` while a Fibonacci step is `Theta(W)`. Measured:
384 LUTs for `n=2` at `W=32` against 173 for the pair, of which 192 per barrel.

**T-3 (crossover with the multiplier).** Since APoT area grows as `n^(d+1)` and
the multiplier's does not grow at all, there is a depth `d*` where APoT costs
what it was introduced to avoid. Measured at `W=32`, `n=2`: **`d* = 2`**, where
APoT-8 costs 1217 LUTs against the multiplier's 1215.

**T-4 (no single winner).** In `(area, latency, error)` no applier dominates.
The multiplier is exact and largest; `phi^k` is smallest and least accurate;
APoT-2 sits between and is beaten by neither. All three are vertices of the
frontier, and a design picks by which axis binds.

## What this does and does not restore

**Does:** the phi applier is the smallest of the three by 2.2x to 7x, and its
area is independent of composition depth. That is a real advantage on the area
axis and it was measured, not argued.

**Does not:** the accuracy claim stays withdrawn. APoT-2 is 15x more accurate
than `phi^k` and one cycle against `k`. Anyone whose binding constraint is
accuracy or latency should use APoT, and we say so.

**The honest recommendation is a hybrid**, not a victory: use `phi^k` where the
scale path is area-bound or composed without requantisation, and APoT where it is
latency- or accuracy-bound. Naming that is worth more than defending a single
answer, because the previous two iterations each defended one and each was wrong
in a different direction.

## Where `d >= 1` actually occurs

Term growth needs a chain with no requantisation between links. In a normal
layer the nonlinearity requantises, so `d = 0`. The cases that are real:

- a low-rank factorisation `W = U V`, `d = 1`
- a folded convolution plus batch norm, `d = 1`
- a residual branch scalar times a block scalar, `d = 2`
- accumulation along a mesh route without renormalisation, `d` up to the hop count

The first three are common and shallow. The fourth is the tri-net case and is the
only one where `d` is not bounded by a small constant.
