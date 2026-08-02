# 2026-08-02 — posit8 (es=2) decode core, simulation only

**Board:** none used. This iteration is simulation and cross-validation; nothing was
flashed and no Tier-E chain was produced.

## Why

The posit8 board proof recorded in issue #199 used
`external/tt-trinity-corona/src/rtl/posit8_decode.v`, whose header reads
*"Posit8(es=0) -> FP32 decode"*. The catalogue's `posit8_conformance_v0.json` declares
*"Posit Standard 2022, n=8, es=2"*. Those are different formats — posit(8,0) tops out at
2⁶ = 64, posit(8,2) at 2²⁴ = 16,777,216 — and at the same 8-bit code they disagree on
252 of 255 values.

The pack is the correct one: it matches SoftPosit, the posit reference implementation,
on all 255 comparable codes. So the silicon proved a format the pack does not describe.

## What was built

`fpga/openxc7-synth/posit8_es2_decode.v` — a wrapper, not new arithmetic.

At a fixed es, posit codes are prefix-coded: an n-bit posit is the wider one with zero
bits appended. Measured rather than assumed, against SoftPosit:

```
posit8(es=2)[c] == posit16(es=2)[c << 8]     all 256 codes, 0 differ
```

SoftPosit's own `positX` family relies on this, left-aligning an n-bit code in a 32-bit
container. `posit16_decode.v` is already es = 2 and already correct, so the new core
hands it the code in the high bits and does nothing else.

**Duplicating the regime counter is how the two cores drifted apart in the first place.**
This one cannot drift, because there is only one implementation of the arithmetic.

## Simulation

```
iverilog -g2012 -o /tmp/tb fpga/openxc7-synth/tb_posit8_es2_decode.v \
         fpga/openxc7-synth/posit8_es2_decode.v \
         fpga/openxc7-synth/posit16_decode.v && /tmp/tb > rtl.txt
python3 research/crossval_posit8_es2_rtl.py --rtl rtl.txt --ref spx8.tsv
```

| | |
|---|---|
| codes compared | 256 |
| bit-identical | **255** |
| NaR, correctly flagged | **1** |
| differing | **0** |

Every posit8 value is exactly representable in FP32 — checked in the comparison rather
than assumed — so this is bit equality, not a tolerance.

The testbench asserts nothing on its own. It prints code and FP32 bit pattern; the
verdict comes from SoftPosit. A testbench that decides its own correctness against a
model written by the same hand is not a second witness.

## What remains, and it needs the board

Not done, and not claimable:

- synthesis through the openXC7 flow with a public CI run URL
- the bitstream SHA-256
- a UART log reading `HW RESULT: N/N bit-exact (fails=0)` at 160000 baud
- IDCODE `0x13636093` from the physical part

Simulation is explicitly **not** one of the four by this project's own standard, so
until the board runs, the honest position is unchanged: the Tier-E row `posit8 256/256`
proves posit(8,0), and the count of packs with board-verified decode is **45, not 46**.

## Measured 2026-08-03 — the risk below did not bite

| core | es | LUTs |
|---|---|---|
| `posit8_decode` (legacy, `external/tt-trinity-corona`) | 0 | **45** |
| **`posit8_es2_decode`** (this one) | **2** | **103** |
| `posit16_decode` alone | 2 | 98 |

Yosys 0.63, `synth_xilinx -abc9 -nodsp`, whole-design totals.

So the correct-format core costs **58 LUTs more** than the legacy one — 2.3×, which
sounds like a lot and is not. The XC7A200T has 134,600 LUTs; 103 is **0.08 %** of the
part. There is no area argument against decoding the format the pack describes.

The 103-vs-98 gap is the wrapper's own boundary, not waste: tying the low byte to zero
lets yosys fold some of the 16-bit path, and the 8-bit port adds a little back.

**This settles handover question 1.** The choice was: re-synthesise an es=2 core, or
record that the silicon proves posit(8,0) and drop board-verified decode from 46 to 45.
Re-synthesis costs 58 LUTs. Take it.

What still needs the board: a CI run URL, the bitstream SHA-256, a UART log and the
IDCODE. Simulation and synthesis are neither of the four.

## Original risk note, kept for the record

The wrapper instantiates the full 16-bit datapath to decode 8 bits, so the LUT cost will
be `posit16_decode`'s, not a smaller posit8's. If area matters on the part, that is the
trade — and it is the right trade, because the alternative is a second regime counter
that can drift from the first. Record the actual LUT count when it synthesises; do not
estimate it here.
