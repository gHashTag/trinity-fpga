# UART Echo — FPGA + FT232RL Test

## Connection Diagram (QMTech XC7A100T)

```
FT232RL        →        FPGA XC7A100T
─────────────────────────────────────────
GND (black)   →  J2 pin 1
RXD (green)   →  J2 pin 5  → L20 (FPGA TX)
TXD (white)   →  J2 pin 6  → K20 (FPGA RX)
─────────────────────────────────────────
Xilinx JTAG    →  JTAG header (VCC, GND, TCK, TDO, TDI, TMS)
```

## Recommended Working File

**Use `uart_echo_top.v` + `uart_echo.xdc`**

This file already contains corrected logic:
- ✅ Correct START bit handling
- ✅ START bit check for LOW (line 56-59)
- ✅ LSB-first data reception
- ✅ Explicit idle HIGH state
- ✅ Echo logic with PONG response

## Synthesis (Yosys + NextPNR)

```bash
cd fpga/openxc7-synth
yosys -p synth_xilinx -d no_iobuf -d srl_low_flop \
      uart_echo_top.v -o uart_echo_top.json

nextpnr-xilinx --chipdb /opt/prjxray-db/artix7/device.db \
      --json uart_echo_top.json \
      --xdc uart_echo.xdc \
      --fmax 50 \
      --write uart_echo_top_routed.json \
      --write-bitstream uart_echo_top.bit

# Or using Yosys directly
yosys -p synth_xilinx -d no_iobuf \
      uart_echo_top.v -o uart_echo_top.edif
```

## Flashing via JTAG

```bash
# 1. Initialize JTAG cable (mandatory!)
sudo fxload -v -t fx2 -d 03fd:0013 -i xusb_xp2.hex

# 2. Flash bitstream
sudo ./jtag_program uart_echo_top.bit

# Or use openFPGALoader
openFPGALoader --cable xpc --bit uart_echo_top.bit
```

## UART Test (Python)

```bash
cd fpga
python3 test_uart_echo.py
```

Test will check:
- FT232RL device discovery
- Sending bytes (A, 0x55, 0xAA, "Hello", 0x00, 0xFF)
- Waiting for echo response
- PASS/FAIL statistics

## UART Monitor (optional)

```bash
cd fpga/uart_monitor
python3 uart_monitor.py /dev/cu.usbserial-* --baudrate 115200
```

Interactive monitor with:
- HEX/ASCII display
- Data sending
- Statistics

## Troubleshooting

### 1. No response (0x00/silence)

**Check:**
- [ ] JTAG flash completed successfully?
- [ ] FT232RL connected correctly (colors)?
- [ ] Correct port selected (`python3 test_uart_echo.py`)?

**Actions:**
- Reseat and reconnect wires
- Try different USB port
- Check LED on board (should blink when receiving)

### 2. Getting garbage

**Possible causes:**
- Speed mismatch (115200)
- Noise/interference when connected

**Actions:**
- Disconnect FT232RL when flashing
- Power cycle board

### 3. LED not blinking

**Problem:** FPGA not flashed or wrong pins

**Actions:**
- Reflash with `jtag_program`
- Check `.xdc` (L20 = TX, K20 = RX)

## File Versions

| File | Status |
|-------|---------|
| `uart_echo_top.v` | ✅ Fixed (recommended) |
| `uart_bridge_fixed.v` | ⚠️  Possible bugs (no tx_busy) |
| `uart_bridge_v2.v` | 🆕 New version with tx_busy |

## Next Steps (if uart_echo doesn't work)

1. Simulation in Icarus Verilog
2. Check pin mapping in constraint file
3. Use oscilloscope on pins L20/K20
4. Test FT232RL with loopback (TX → RX directly)
