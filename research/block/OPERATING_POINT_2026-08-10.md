# The operating point: cheap under both operations, and only where the datapath needs it

Five claims were withdrawn tonight. This is what survives them, and it is a
better claim than any of the five because it says what the restriction is.

## The three systems, on both operations

| system | multiplication | addition |
|---|---|---|
| LNS / takum | exponents add -- **free** | `log(1 + 2^x)` table: **10,967 LUT + 84 RAMB36** (our own measurement of `takum32_decode`) |
| fixed point / APoT | multiplier, or shifts if the scale is frozen | adder -- **cheap** |
| **`Z[phi]`** | Fibonacci step, one adder -- **free, but only for powers of `phi`** | componentwise -- **64 LUT** |

**`Z[phi]` is the only one of the three that is cheap under both.** The price is
that its free multiplication is restricted to powers of `phi` rather than
general.

## Why that restriction is not a restriction here

**T-1 (the required multiplication set).** In a datapath where every weight is a
code applied by sign-select, the layer scale is a power of the alphabet base, and
accumulation is the only other operation, the set of multiplications the datapath
must perform is exactly `{base^k}`. No general multiplication is ever requested.

**T-2 (sufficiency).** A ring closed under addition and under multiplication by
powers of its generator is therefore sufficient for such a datapath. `Z[phi]` is
such a ring, with both operations at `Theta(W)`.

**T-3 (the other two are mis-provisioned).** LNS is over-provisioned: it buys
general multiplication, which the datapath never asks for, and pays for it in
addition, which the datapath performs on every term of every inner product.
Fixed point is under-provisioned in the opposite direction: addition is free but
scale multiplication is not, unless the scale is frozen at compile time.

The restriction of `Z[phi]` coincides with the restriction the ternary datapath
already has. That coincidence is the whole result.

## What this does not claim

- It is not an area win over APoT. That was measured and withdrawn: with a frozen
  scale APoT costs 26 LUTs against our unrolled 256, and at the shift width the
  workload needs, 130 against 199.
- It is not an accuracy win. APoT-2 is 15x more accurate on the scale grid.
- It is not a claim that `Z[phi]` beats fixed point where the scale is frozen. It
  does not; there is nothing to beat, because a frozen scale is wiring.

It is a claim about **which system matches the datapath's operation profile**,
and it holds precisely where the scale is not frozen -- a shared engine serving
many layers, or a composition whose depth is a runtime quantity.

## Composition, and where it is actually free

**T-4 (compile-time composition is free).** If all `d` scales of a chain are
known before execution, their product is known too, and any representation
applies it at the cost of a single scale. The term growth `n^(d+1)` occurs if and
only if `d` or the scales themselves become known only at runtime.

This removes three of the four cases where we had claimed a depth advantage:
low-rank `W = UV`, folded convolution and batch norm, and a residual branch
scalar are all known after training, so their product is precomputed and no
composition happens in hardware at all.

**One case survives:** accumulation along a mesh route without renormalisation,
where the hop count is a runtime quantity. That is the tri-net datapath, not the
neural network. The depth advantage is real and it lives there.

## Reading of the night

Five withdrawals in five iterations, each because a favourable number came from a
comparison whose terms we had chosen. What is left is smaller, and it is the
first claim tonight that names its own boundary before being asked: `Z[phi]` is
the matched system for a datapath that multiplies only by powers of its base, and
that is a statement about a class of datapaths rather than about a format's
superiority.
