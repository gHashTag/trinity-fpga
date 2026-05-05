# FPGA IDCODE Reference

**φ² + φ⁻² = 3** | trios#380 Ch.28

## IDCODE = `0x13631093`

IEEE 1149.1 IDCODE breakdown (32-bit, read LSB-first from JTAG DR):

| Bits | Value | Meaning |
|---|---|---|
| [0] | `1` | Required by IEEE 1149.1 |
| [11:1] | `0x049` | Xilinx manufacturer (JEDEC bank 1, ID 0x49) |
| [27:12] | `0x3631` | Part number → **XC7A200T** |
| [31:28] | `0x1` | Silicon revision 1 |

## Bit-level parse

```
0x13631093 = 0001 0011 0110 0011 0001 0000 1001 0011
             ^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^ ^
             ver  part (0x3631)        mfg (0x049) 1
```

## Note: Board vs Die

The QMTech board is labelled **XC7A100T** but contains **XC7A200T** silicon (version 1). This is a known board variant. The Trinity S³AI design (83 LUT / 27 FF) uses < 0.1% of either device — no resynthesis required.

## XC7A100T expected IDCODE: `0x0362D093`

For reference — this would be read if the board actually contained a 100T die.
