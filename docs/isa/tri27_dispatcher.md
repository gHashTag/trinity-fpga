# Native TRI-27 Dispatcher — Vector S-153

**Wave:** TT v21 · **Vector:** S-153 · **Layer:** L1 Compute · **Mapping:** LANG→SI
**Falsification gate:** G-153
**Anchor:** φ² + φ⁻² = 3 · DOI [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)

---

## Register File

3 banks × 9 Coptic registers = **27 registers total**, replacing the v18 baseline 24×16 file.

| Bank | Registers | Width | Role |
|------|-----------|-------|------|
| `BANK_A` | Ⲁ Ⲃ Ⲅ Ⲇ Ⲉ Ⲋ Ⲍ Ⲏ Ⲑ | 16-bit Q3.13 | scalar / GF16 |
| `BANK_B` | Ⲓ Ⲕ Ⲗ Ⲙ Ⲛ Ⲝ Ⲟ Ⲡ Ⲣ | 729-trit hypervector | VSA |
| `BANK_C` | Ⲥ Ⲧ Ⲩ Ⲫ Ⲭ Ⲯ Ⲱ Ⲳ Ϥ | 16-bit signed | microcode / brain |

## Opcode Set — 36 TRI-27 Opcodes

- 16 sacred opcodes (`0xD0..0xE0` and 0xE1..0xE3 brain extension) — see [vsa_opcodes.md](./vsa_opcodes.md)
- 12 arithmetic (`0x00..0x0B`): `TADD TSUB TMUL TDIV TMOD TNEG TINC TDEC TSAT TCMP TMIN TMAX`
- 4 logic (`0x10..0x13`): `TAND TOR TXOR TNOT`
- 4 control (`0x20..0x23`): `TJMP TBRZ TCALL TRET`

## Reuse

Reuses the **Sacred ALU 352-LUT** design as the inner core (proven on Artix-7 XC7A100T per [SACRED_ALU_SYNTHESIS_REPORT.md](https://github.com/gHashTag/trinity/blob/main/docs/SACRED_ALU_SYNTHESIS_REPORT.md)).

## Falsification gate G-153

> The `tbin` test suite from [t27 CANON.md](https://github.com/gHashTag/t27/blob/master/CANON.md) M1–M6 ceremony passes byte-exactly on the TRI-1 emulator.

## Cross-strand links

- Strand III TRI-27 ISA → S-153 dispatcher
- Strand I GF16 dot4 canon `0x47C0` → BANK_A multiplier seed
- Strand II microcode (S-151) executes from BANK_C

```
φ² + φ⁻² = 3 · 27 = 3³ · NEVER STOP
```
