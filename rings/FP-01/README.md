# FP-01 — Synthesis Engine

RTL synthesis via Yosys + nextpnr + openxc7 Docker toolchain.

## Pipeline

```text
RTL (*.v) + XDC -> Yosys -> JSON -> nextpnr -> FASM -> xc7frames2bit -> .bit
```

## API

- `OpenXc7Runner::synthesize()` — full synthesis pipeline
- `OpenXc7Runner::generate_chipdb()` — generate nextpnr chipdb for target device
- `SynthConfig::for_board()` — configure synthesis for a specific board

## Replaces

- `generate_bitstream.sh`
- `build_uart_bridge.sh`
- `docker_uart_synth.sh`

`phi^2 + 1/phi^2 = 3`
