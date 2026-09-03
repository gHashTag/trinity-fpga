# The operands moved on-chip, and most of the advantage went with them

Every measurement in this directory fed `x` and `w` through the interface, so
the pin count grew with fan-in: at N=32 the layer needs 332 input bits on a
206-pin package and place-and-route stops. That happened for **both** arms, so
it was never a property of the lattice — only of the harness.

A deployed layer does not receive its weights from outside. They are stored.
`tern_layer_mem.v` puts `x` and `w` in on-chip memory behind a narrow load port,
so the interface is an address and a result: **56 pins at every fan-in**.

## Correctness first

Six rows loaded lane by lane, run, and compared against a golden model computed
independently in integers: **6 checks, 0 errors**. Dropping one term from the φ
reconstruction makes the bench fail, so the pass is not vacuous.

## Measured — nextpnr-ice40, hx8k ct256, ACC=16, ROWS=16

| arm | N | LC | SB_IO | RAM | Fmax |
|---|---:|---:|---:|---:|---:|
| φ | 16 | **1746** | 56 | 10 | 56.59 MHz |
| multiplier | 16 | 2014 | 56 | 10 | 56.23 MHz |
| φ | 32 | **2994** | 57 | 20 | 48.67 MHz |
| multiplier | 32 | 3264 | 57 | 20 | 47.17 MHz |
| φ | 64 | 5502 | 58 | 40 | — |
| multiplier | 64 | 5772 | 58 | 40 | — |

Fan-in 64 does not fit: it needs **40 block RAMs on a part with 32**. Logic is
not the limit there (5502 of 7680 cells) and the shortfall is identical for both
arms.

## What this does to the claim

**The area advantage is 1.13× at fan-in 16 and 1.09× at 32** — a constant ~270
cells, which is the multiplier, against a layer now dominated by the MAC and the
memory. **The frequency advantage is gone**: 56.59 against 56.23, and 48.67
against 47.17. The memory read is the critical path for both arms.

That is the fourth consecutive narrowing of the same number as more of the real
design entered the measurement:

| what was measured | ratio |
|---|---|
| the scale block alone | 7.1× |
| a layer, operands on pins, pair output | 1.53× |
| the same with the scalar reconstruction inside | 1.31× |
| **the same with operands in memory** | **1.13×** |

Each step is T47 again — removing a fixed-cost block saves a constant, and the
ratio falls as the surround grows. The honest statement is not a multiple at
all: **the φ arm removes about 270 logic cells and three DSP blocks, and needs
no DSP at any fan-in.**

## What this does not establish

iCE40, not the Artix-7 this work targets, and iCE40 has no DSP blocks so the
multiplier is maximally penalised — on a part with DSPs the multiplier arm is
smaller in LUTs. One output element per row, no accumulation across rows, no
activation streaming, and no board.
