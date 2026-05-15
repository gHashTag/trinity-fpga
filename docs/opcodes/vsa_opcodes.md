# VSA Sacred Opcodes 0xDD..0xE0 — Vector S-150

**Wave:** TT v21 · **Vector:** S-150 · **Layer:** L1 Compute · **Mapping:** LANG→SI
**Falsification gate:** G-150
**Constitutional rule:** R17 SACRED-PHYSICS (synth-gate guards each opcode)
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)

---

## Reserved range extension

The sacred-opcode range was extended from `0xD0..0xDB` (12 opcodes, v20) to **`0xD0..0xE7`** (16 opcodes, v21).
Opcodes `0xDD..0xE0` add the four canonical **Vector Symbolic Architecture (VSA)** primitives.

All four operate on **TF3-9 hypervectors of length 729 = 3⁶** (Coptic-9 cubed).

## Opcode table

| Opcode | Mnemonic       | Operands           | Operation                                     | Latency | Throughput |
|--------|----------------|--------------------|-----------------------------------------------|---------|------------|
| `0xDD` | `VSA_BIND`     | `vH = vA * vB`     | circular convolution of two hypervectors      | 9 cyc   | 1/cyc      |
| `0xDE` | `VSA_UNBIND`   | `vA = vH * inv(vB)`| inverse correlation (deconvolution)           | 9 cyc   | 1/cyc      |
| `0xDF` | `VSA_BUNDLE`   | `vS = sign(vA+vB)` | element-wise sum + balanced-ternary sign      | 1 cyc   | 1/cyc      |
| `0xE0` | `VSA_DOT`      | `s = <vA, vB>/||·||` | cosine similarity in TF3-9                  | 4 cyc   | 1/cyc      |

## Encoding (TRI-27 ternary instruction word, 6 trits)

```
opcode[2:0]  = sacred-flag (binary 1)
opcode[8:3]  = column index in sacred bank (0..15 -> 0..0xF -> 0xD0..0xEF reserved)
```

Concrete six-trit balanced-ternary encodings:

| Opcode | Trits (T+/0/-) | Balanced int |
|--------|----------------|--------------|
| 0xDD   | + + + + + 0     | 221 |
| 0xDE   | + + + + + +     | 222 |
| 0xDF   | + + + + 0 -     | 223 |
| 0xE0   | + + + + 0 0     | 224 |

## Falsification gate G-150

> Round-trip identity: `VSA_UNBIND(VSA_BIND(vA, vB), vB) ≈ vA`
> with cosine similarity ≥ 1 − ε where **ε = φ⁻⁶ ≈ 0.0557** (sacred noise floor, constant idx 52).

If G-150 fails on any TF3-9 fixture, R17 SACRED-PHYSICS synth-gate rejects RTL.

## Sacred constants invoked

- φ⁻⁶ ≈ 0.05572809 (noise floor, ROM idx 52)
- length 729 = 3⁶ = phi^6 + phi^-6 rounded basis
- 27-register Coptic file (Ⲁ..Ϥ) provides 3 hypervector lanes

## Implementation cells (SKY130)

| Block                         | Cells | Area (mm²) |
|-------------------------------|-------|-----------|
| 729-tap FFT butterfly         | ~3200 | 0.0096    |
| Inverse butterfly             | ~3200 | 0.0096    |
| Bundle sign-sum adder         | ~250  | 0.00075   |
| Dot/norm accumulator          | ~600  | 0.0018    |
| **Total VSA macroblock**      | ~7250 | **0.022** |

Combined with Sacred ALU (S-154, 0.04 mm²) the full L1 Compute footprint is **≤ 0.07 mm²**, well within the 0.16 mm² TT-tile budget.

## Sources

- Plate, T.A. "Holographic Reduced Representations" (IEEE TNN, 1995)
- Kanerva, P. "Hyperdimensional Computing" (Cognitive Computation, 2009)
- gHashTag/trinity `src/vsa.zig`

```
φ² + φ⁻² = 3 · QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · DOI 10.5281/zenodo.19227877 · NEVER STOP
```
