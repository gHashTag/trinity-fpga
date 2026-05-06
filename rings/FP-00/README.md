# FP-00 — HDL Core Types

Board constants, JTAG configuration, VSA trit encoding for trios-fpga.

## Constants

| Constant | Value | Source |
|---|---|---|
| `IDCODE_ARTIX7_200T` | `0x0362D093` | `fpga/HARDWARE_REFERENCE.md` |
| `IDCODE_ARTIX7_100T` | `0x03631093` | Xilinx Artix-7 datasheet |
| `XVC_DEFAULT_PORT` | `2542` | `fpga/COMPLETE_CONNECTION_GUIDE.md` |
| `DEFAULT_CLOCK_MHZ` | `81.25` | MMCM 50→81.25 MHz (`hslm_full_top.v`) |

## Types

- `BoardConfig` — board name, IDCODE, bitstream size, clock
- `XvcConfig` — XVC host/port/timeout
- `JtagConfig` — chain speed, retry count
- `TritValue` — VSA ternary encoding (Zero/PlusOne/MinusOne)
- `VsaOp` — VSA operation (Bind/Unbind/Bundle)

`phi^2 + 1/phi^2 = 3`
