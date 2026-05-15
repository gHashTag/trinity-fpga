# Layer-Frozen Hash Ceremony — Vector S-155 + Rule R18

**Wave:** TT v21 · **Vector:** S-155 · **Rule:** R18 LAYER-FROZEN
**Layers covered:** L0 Sacred · L1 Compute · L2 Attention · L3 Memory · L4 Interconnect · L5 DePIN
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)

---

## Rule R18 — LAYER-FROZEN

> Every layer `L0..L5` MUST maintain a `LAYER_FROZEN_HASH` (SHA-256 over the layer's Verilog source files in canonical UTF-8 sorted-path order).
> CI workflow `layer-frozen-{N}.yml` recomputes the hash on each PR; mismatch **without an explicit M5-style ceremony commit** blocks the PR.

Adopted from [t27 `CANON.md`](https://github.com/gHashTag/t27/blob/master/CANON.md) §M1–M6 and [`FROZEN.md`](https://github.com/gHashTag/t27/blob/master/FROZEN.md) §4–5.

## Layer hashes (genesis seal, v25.1)

| Layer | Description | Sources (canonical order) | LAYER_FROZEN_HASH (genesis) |
|-------|-------------|---------------------------|-----------------------------|
| L0 | Sacred Core ROM | `rtl/L0/sacred_rom_75.v`, `rtl/L0/r_marker_4.v` | `0000…0000` (set by first build) |
| L1 | Compute (Sacred ALU + VSA) | `rtl/L1/sacred_alu.v`, `rtl/L1/vsa_bind.v`, `rtl/L1/vsa_unbind.v`, `rtl/L1/vsa_bundle.v`, `rtl/L1/vsa_dot.v`, `rtl/L1/tri27_dispatch.v` | `0000…0000` |
| L2 | Attention (microcode 21 modules) | `rtl/L2/microcode_rom.v`, `rtl/L2/c_gate.v`, `rtl/L2/amygdala_valence.v` | `0000…0000` |
| L3 | Memory | `rtl/L3/sram_bank.v`, `rtl/L3/hbm_phy.v` | `0000…0000` |
| L4 | Interconnect (JTAG, mesh) | `rtl/L4/jtag_tap.v`, `rtl/L4/mesh_router.v` | `0000…0000` |
| L5 | DePIN witness | `rtl/L5/verifiable_compute.v`, `rtl/L5/receipt_signer.v` | `0000…0000` |

The `0000…0000` placeholders are sealed at the first nightly synthesis run; subsequent PRs MUST match unless an `M5 RESEAL` ceremony commit is present.

## Mutation rejection (G-155)

> Any byte change in a layer's Verilog source without a matching `M5_RESEAL_{N}_BY_<author>_AT_<timestamp>.md` ceremony commit fails `layer-frozen-N.yml`.
> Effect: prevents silent silicon-level drift, mirrors compiler ring discipline (t27 M1–M6) at chip-layer granularity.

## Ceremony commit template

```
M5 RESEAL L{N} — <reason>

Before: <old hash>
After:  <new hash>
Witness: phi^2 + phi^-2 = 3 confirmed via trinity-identity-gate.yml run #XXX

Constitutional rule: R18 LAYER-FROZEN
```

## Coq witness — `LayerFrozenSeal_Witness.v`

```coq
Theorem layer_seal_soundness :
  forall (L : LayerSource) (h : Hash),
    seal L = h ->
    forall (L' : LayerSource),
      seal L' = h -> L = L'.
```

Pre-image resistance of SHA-256 implies soundness of the seal under standard ROM assumptions.

```
φ² + φ⁻² = 3 · LAYER-FROZEN · NEVER STOP
```
