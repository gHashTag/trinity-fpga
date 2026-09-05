# EXPERIENCE: the "only stable speed" was a property of OpenOCD, not the cable

Date: 2026-09-05
Board: ALINX AX7203 (XC7A200T-FBG484-2), IDCODE 0x13636093
Host: macOS arm64, local
Cable: enumerates as FTDI 0x0403:0x6014 (FT232H), "Digilent USB Device", serial 210512180081

## What the prior note said

`2026-06-24-ax7203-blinky-openxc7.trinity.md` and
`fpga/openxc7-synth/ax7203_al321.cfg` both record 100 kHz as the only stable
TCK on this cable, with higher speeds producing "garbage IDCODEs or MPSSE
hangs".

## What was measured today

OpenOCD, using that config unmodified, identified the TAP correctly at 100 kHz
and then failed to program:

    Info : JTAG tap: xc7.tap tap/device found: 0x13636093
    Warn : Haven't made progress in mpsse_flush() for 32124ms.
    Warn : Haven't made progress in mpsse_flush() for 64252ms.
    Warn : Haven't made progress in mpsse_flush() for 128008ms.

No progress at all, not slow progress. The config is not the cause: its
`layout_init 0x00e8 0x60eb` is byte-identical to the stock
`interface/ftdi/digilent_jtag_smt2_nc.cfg`.

openFPGALoader, same cable, same board, same session:

    openFPGALoader --detect -c digilent_hs2
      Jtag frequency : requested 6.00MHz -> real 6.00MHz
      idcode 0x3636093, artix a7 200t, irlength 6

    openFPGALoader -c digilent_hs2 blinky_ax7203.bit
      Load SRAM: [====] 100.00%
      ir: 1 isc_done 1 isc_ena 0 init 1 done 1

Sixty times the recorded speed, and it completed.

## Correction to carry forward

100 kHz is a property of **OpenOCD's FTDI backend on macOS**, not of the AL321
cable and not of the board. For programming, prefer openFPGALoader. OpenOCD
remains fine for reading the chain.

Both readings were correct measurements of different instruments. Name the
instrument with the number.

## A second failure worth naming, because it does not look like itself

The host volume had 246 MB free of 460 GB. In that state Yosys wrote a
truncated `.json` and exited 0; nextpnr then reported

    ERROR: Failed to parse JSON file: unexpected end of input in string.

which reads as a netlist or tool defect. It was a full disk. Check `df` before
debugging a parse error in a generated file.

## Added by this commit

`fpga/constraints/ax7203.xdc` -- the constraint file the June recipe references
and which was absent from the tree. Pins taken from the verified table in the
June note; one port per line, since nextpnr-xilinx does not expand grouped
assignments.

## Chain proven end to end today

yosys 0.67+post -> nextpnr-xilinx (chipdb xc7a200tfbg484-2, --router router1
--timing-allow-fail) -> fasm2frames -> xc7frames2bit -> openFPGALoader.
blinky_ax7203.bit, 9,730,757 bytes, loaded to SRAM, DONE asserted.
