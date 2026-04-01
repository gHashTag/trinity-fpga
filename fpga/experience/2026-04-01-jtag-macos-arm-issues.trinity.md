# EXPERIENCE: JTAG on macOS ARM — Not Working with DLC10
Date: 2026-04-01
Board: QMTech XC7A100T
Host: macOS ARM (MacBook Pro M-series)
Cable: Xilinx DLC10 Platform Cable USB II (clone)

## Problem
DLC10 JTAG cable **does NOT work** on macOS ARM for FPGA flashing.

## Symptoms
### jtag_program (fpga/tools/jtag_program)
```
sudo ./fpga/tools/jtag_program <bitstream>.bit
libusb_control_transfer(0x28.x)Failed to connect.
Error: LIBUSB_ERROR_ACCESS (Permission Denied)
```
Even with `sudo` — doesn't work.

### openFPGALoader
```bash
openFPGALoader --detect
# → unable to open ftdi device: -3 (device not found)

openFPGALoader -c digilent --bitstream <bitstream>.bit
# → unable to open ftdi device: -3 (device not found)
```
Even after `brew install openfpgaloader` — doesn't see the cable.

## Root Cause
1. **macOS ARM + libusb**: FTDI drivers on arm64 macOS have issues accessing USB devices
2. **DLC10 clone**: Chinese clone may not be supported by official Xilinx drivers
3. **PID switching**: Cable requires fxload (PID 0x0013 → 0x0008), but even after switching libusb cannot connect

## What Works
- ✅ fxload switches cable (PID 0x0013 → 0x0008)
- ✅ system_profiler sees cable after switching
- ❌ jtag_program cannot connect via libusb
- ❌ openFPGALoader doesn't see FTDI device

## What DOESN'T Work
- ❌ `sudo ./fpga/tools/jtag_program` — LIBUSB_ERROR_ACCESS
- ❌ `openFPGALoader -c digilent` — FTDI device not found
- ❌ `openFPGALoader -c xilinx_platform_usb` — cable not found
- ❌ `openFPGALoader --vid 0x03fd --pid 0x0008` — set baudrate failed

## Valid Paths Forward

### Option 1: Linux Host/VM (RECOMMENDED)
- Linux VM (Parallels/VMware/UTM) with Xilinx Vivado
- Or separate Linux PC with xc3sprog
- **Pros**: Reliable, documented, works
- **Cons**: Need separate system

### Option 2: RP2040/ESP32 JTAG Bridge
- Microcontroller as JTAG→USB bridge (XVC protocol)
- Connect GPIO to JTAG pins
- Flash via regular USB-CDC
- **Pros**: Works on macOS without Xilinx drivers
- **Cons**: Need to assemble/write bridge firmware

### Option 3: SPI Flash Programmer
- Flash directly to external SPI flash on board
- Find Winbond/GD25Q chip, connect programmer
- **Pros**: JTAG not needed
- **Cons**: Need to access flash chip

## Workaround for Testing
- DSLogic U2basic works for debugging without flashing
- FT232RL provides UART channel for communication
- HSLM already flashed (clocks visible on DSLogic)

## Files Referenced
- fpga/tools/jtag_program — custom JTAG programmer
- fpga/tools/fxload — FTDI firmware loader
- fpga/tools/xusb_xp2.hex — Xilinx cable firmware
- .trinity/fpga/experience.json — attempt log

## Decision
**Current status**: JTAG flashing on macOS ARM is IMPOSSIBLE with current hardware.
**Solution**: Use Linux host or build RP2040 JTAG bridge.
