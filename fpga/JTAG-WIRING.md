# JTAG Wiring — ESP32 to QMTech XC7A200T (FGG676)

## Pin Mapping

| Wire   | Color    | ESP32 Pin       | FPGA JTAG Pin |
|--------|----------|-----------------|---------------|
| GND    | Black    | GND (IO pin 3)  | Pin 2 (GND)   |
| TCK    | Yellow   | IO19 (SPI pin 2)| Pin 3 (TCK)   |
| TMS    | Orange   | IO18 (SPI pin 3)| Pin 6 (TMS)   |
| TDI    | Green    | IO23 (SPI pin 1)| Pin 5 (TDI)   |
| TDO    | Blue     | IO35 (IO pin 2) | Pin 4 (TDO)   |
| VCC    | Red      | 3.3V            | Pin 1 (VREF)  |

## QMTech JTAG Header (6-pin, silkscreen order)

```
Pin 1 — VCC 3.3V  (red, required for transceiver)
Pin 2 — GND       (black)
Pin 3 — TCK       (yellow)
Pin 4 — TDO       (blue)
Pin 5 — TDI       (green)
Pin 6 — TMS       (orange)
```

## ESP32 Pin Selection Notes

- GPIO35: input-only, no internal pull-up. Suitable for TDO read.
- GPIO18, 19, 23: standard GPIO with output capability for TMS, TCK, TDI.
- VCC (Pin 1) must be connected — without it the JTAG transceiver has wrong voltage levels (yellow LED instead of green).

## Critical Findings

1. VCC must be connected for the JTAG I/O buffer to function.
2. The original kholia/xvc-esp32 firmware had multiple bugs (stack overflow, missing "ift:" protocol read, wrong TDI buffer offset). A custom firmware was written.
3. The XVC shift length field must be parsed as little-endian for openFPGALoader compatibility.
4. TDO is read after TCK rising edge with 2us delay — sufficient for Artix-7 TAP.
