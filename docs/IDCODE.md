# FPGA IDCODE Reference

**φ² + φ⁻² = 3** | trios#380 Ch.28

## IDCODE = `0x13631093`

IEEE 1149.1 IDCODE breakdown (32-bit, read LSB-first from JTAG DR):

| Bits | Value | Meaning |
|---|---|---|
| [0] | `1` | Required by IEEE 1149.1 |
| [11:1] | `0x049` | Xilinx manufacturer (JEDEC bank 1, ID 0x49) |
| [27:12] | `0x3631` | Part number → **XC7A100T** |
| [31:28] | `0x1` | Silicon revision 1 |

## Bit-level parse

```
0x13631093 = 0001 0011 0110 0011 0001 0000 1001 0011
             ^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^ ^
             ver  part (0x3631)        mfg (0x049) 1
```

## Note: Board vs Die

The QMTech Wukong board (package FGG676) is labelled **XC7A100T** and the
silicon confirms it: part number 0x3631 = XC7A100T, version 1. This matches the
tested value in `t27 cli/dlc10/tests/idcode.rs` and the FPGA SSOT
(`gHashTag/t27/fpga/HARDWARE_SSOT.md`).

## Related part IDCODEs (for reference)

| Device   | Part   | Expected IDCODE (ver 1 / ver 0) |
|----------|--------|---------------------------------|
| XC7A35T  | 0x362D | 0x0362D093                      |
| XC7A100T | 0x3631 | 0x13631093 / 0x03631093         |
| XC7A200T | 0x3636 | 0x13636093 / 0x03636093         |

The physically distinct ALINX AX7203 board (package FBG484) carries an XC7A200T
die (0x13636093) — see `fpga/openxc7-synth/ax7203_al321.cfg`. Do not confuse the
two boards.
