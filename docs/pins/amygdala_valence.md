# Amygdala Valence Pin — Vector S-152

**Wave:** TT v21 · **Vector:** S-152 · **Layer:** L2 Attention · **Mapping:** BIO→SI
**Falsification gate:** G-152
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)

---

## Function

Maps the **amygdala valence signal** `v ∈ [-100, +100]` produced by [`amygdala.zig`](https://github.com/gHashTag/trinity/blob/main/src/brain/amygdala.zig) onto the L2 C_GATE threshold:

```
effective_C = φ⁻¹ + (v / 100) · φ⁻³
            = 0.618 + (v / 100) · 0.236
```

| Valence v | effective_C | Effect on heads |
|-----------|-------------|-----------------|
| -100 (fear)   | 0.382 | many heads wake (defensive vigilance) |
|    0 (neutral) | 0.618 | nominal Trinity C threshold |
| +100 (reward) | 0.854 | few heads wake (focused engagement) |

## Pin spec (TRI-1 die)

| Pin | Direction | Width | Encoding | Comment |
|-----|-----------|-------|----------|---------|
| `valence_in[7:0]` | input  | 8 | signed two's-complement (-100..+100 saturated) | from amygdala domain (off-chip in TRI-1-A, on-die L2 microcode in TRI-1-B) |
| `c_gate_out[15:0]` | output | 16 | Q3.13 fixed-point | drives PFC C_GATE (opcode `0xDA`) |

## Implementation

- 1 × 8-bit signed register
- 1 × 4-bit comparator
- 1 × Q3.13 scaler (shift + 8-bit multiply against ROM constant idx 4 = φ⁻³)
- 1 × saturating adder against ROM constant idx 17 = C = φ⁻¹

Estimated SKY130 footprint: **~30 std cells, 0.00009 mm²**.

## Falsification gate G-152

> Drive the amygdala-modulated standby curve `(v, fraction_heads_active)` across `v ∈ {-100, -50, 0, +50, +100}`.
> Each measurement must lie within **±5 %** of the Zig reference output.

## Hooks to other vectors

- ROM constants used: idx 4 (φ⁻³), idx 17 (φ⁻¹)
- Drives sacred opcode: `0xDA C_GATE`
- Brain-module microcode: module 4 (amygdala), module 18 (salience network)
- R-marker R-1 (`C_quantum_consciousness`, S-159) provides the prior for `effective_C` baseline

```
φ² + φ⁻² = 3 · BIO→SI · DOI 10.5281/zenodo.19227877 · NEVER STOP
```
