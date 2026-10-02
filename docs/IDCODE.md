# FPGA IDCODE Reference

**φ² + φ⁻² = 3** | trios#380 Ch.28

## IDCODE = `0x13636093`

IEEE 1149.1 IDCODE breakdown (32-bit, read LSB-first from JTAG DR):

| Bits | Value | Meaning |
|---|---|---|
| [0] | `1` | Required by IEEE 1149.1 |
| [11:1] | `0x049` | Xilinx manufacturer (JEDEC bank 1, ID 0x49) |
| [27:12] | `0x3636` | Part number → **XC7A200T** |
| [31:28] | `0x1` | Silicon revision 1 |

## Bit-level parse

```
0x13636093 = 0001 0011 0110 0011 0110 0000 1001 0011
             ^^^^ ^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^ ^
             ver  part (0x3636)        mfg (0x049) 1
```

## Note: Board vs Die

The project board is the **ALINX AX7203** (package FBG484) and its die is an
**XC7A200T**: part number `0x3636`, verified via OpenOCD + AL321 on
2026-06-24 — `specs/boards/ax7203_full.t27` and
`fpga/openxc7-synth/ax7203_al321.cfg`.

The bench's XC7A200T devices report the version-0 variant `0x03636093`
(`idcode 0x3636093` in the t27 hardware SSOT, measured on all three boards;
`research/arxiv_tnf/measurements/hardware_scan_2026-08-20.json`). The two
values differ only in the top nibble — the silicon **version** field. Both
are XC7A200T; JTAG practice is to compare the low 28 bits, which is what the
provenance matchers now do (#633).

The physically distinct QMTech Wukong board (package FGG676) is labelled
**XC7A100T** and the silicon confirms it: part number `0x3631` = XC7A100T,
version 1, IDCODE `0x13631093` (version-0 variant `0x03631093`). This
matches the tested value in `t27 cli/dlc10/tests/idcode.rs` and the FPGA SSOT
(`gHashTag/t27/fpga/HARDWARE_SSOT.md`). Do not confuse the two boards.

## Related part IDCODEs (for reference)

| Device   | Part   | Expected IDCODE (ver 1 / ver 0) |
|----------|--------|---------------------------------|
| XC7A35T  | 0x362D | 0x0362D093                      |
| XC7A100T | 0x3631 | 0x13631093 / 0x03631093         |
| XC7A200T | 0x3636 | 0x13636093 / 0x03636093         |
