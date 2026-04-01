# DSLogic U2basic Connection Guide — QMTech XC7A100T

## Overview

**Goal**: Connect DSLogic U2basic 16-channel Logic Analyzer to QMTech XC7A100T-FGG676 FPGA for full signal analysis (UART + JTAG + SPI + Clock tree).

---

## Equipment

| Item | Description | Purpose | Notes |
|------|-------------|---------|-------|
| DSLogic U2basic | Logic analyzer, 16 channels @ 400 MS/s | Main analysis tool | Color-coded wires |
| QMTech XC7A100T-FGG676 | FPGA board (Artix-7) | Target board | |
| FT232RL JTAG cable | USB-to-JTAG cable (DLC10 clone) | For FPGA flashing/JTAG | Converts to USB-UART for testing |
| Test hooks | Small grabbers | For thin pins (JTAG) | For JTAG header |
| Crocodile clips | Alligator clips | For GND and large contacts | |

## 🎨 DSLogic Wire Color Coding (CONFIRMED by measurements!)

| DSLogic Color | Wire | Connect To | Signal | Label on J2 |
|--------------|------|------------|--------|-------------|
| **⬛ Black** | GND for group | Ground | Any pin 1 |
| **🟡 Yellow** | CH0 | J2 pin 5 (top row, 3rd hole) | FPGA TX (K20) |
| **🟢 Green** | CH1 | J2 pin 6 (bottom row, 3rd hole) | FPGA RX (L20) |
| **🔵 Blue** | CH2 | M22 (board, pin next to JTAG) | 50 MHz clock |
| **🟣 Purple** | CH3 | U22 (board) | MMCM 81.25 MHz |
| **🔴 Red** | CH4 | T23 (board, LED D5) | LED output |
| Orange | CH5 | J21 (reserved) | SPI_SCK |
| White | CH6 | H21 (reserved) | SPI_MISO |
| Gray | CH7 | G22 (reserved) | SPI_MOSI |
| Pink | CH8 | F22 (reserved) | SPI_CS |
| Brown | CH9 | JTAG TCK (test hook) | JTAG Clock |
| Beige | CH10 | JTAG TDI (test hook) | JTAG Data In |
| Lime | CH11 | JTAG TDO (test hook) | JTAG Data Out |
| Turquoise | CH12 | JTAG TMS (test hook) | JTAG Mode |
| Dark Blue | CH13 | D26 (reserved) | UART TX ALT |
| Dark Green | CH14 | E26 (reserved) | UART RX ALT |
| Dark Red | CH15 | GND | Trigger Ref |

### 🔬 CRITICAL CONFIRMATION RULES:

1. **CH0 = Yellow = FPGA TX** — measured on board ✅
2. **CH1 = Green = FPGA RX** — measured on board ✅
3. **GND always to J2 pin 1 (bottom row)**
4. **FT232RL TXD (green) — DO NOT insert into J2!** Not needed for DSLogic tests
5. **FT232RL RXD (white) → TOP row, J2 pin 5** for same GND
6. **5V and 3V wires from FT232RL — don't touch in J2 at all** (let them hang)

---

## Physical Layout

### DSLogic U2basic (Top View)

```
┌─────────────────────────────────────────────────────────────────┐
│  [USB]                                              │
│   │                                                 │
│   └──► to MacBook                                    │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  GND  CH0   CH1   CH2   CH3   CH4   CH5     │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●     │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●     │   │
│  │  GND  0     1     2     3     4     5        │   │
│  │                                                 │
│  │  CH6   CH7   CH8   CH9   CH10  CH11  CH12    │   │
│  │  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    │   │
│  │   6     7     8     9     10    11    12     │   │
│  │                                                 │
│  │  CH13  CH14  CH15  [Trigger]                  │   │
│  │  ●●●   ●●●   ●●●   ●●●                         │   │
│  │  ●●●  ●●●   ●●●   ●●●                         │   │
│  │   13    14    15    TRIG                        │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### QMTech XC7A100T (Top View)

```
        JTAG Header (6 pin)              J2 Header (64 pin)
        ┌──────────┐                    ┌──────────────────┐
        │ VCC GND  │                    │  [1] [3] [5]...  │ ← Top row
        │ TCK TDO  │                    │   ▲        ▲      │
        │ TDI TMS  │                    └──────────────────┘
        └────┬─────┘
             │
             ▼
        ┌─────────┐
        │  M22    │ ← 50 MHz oscillator
        │  U22    │ ← MMCM output
        │  T23    │ ← LED (D5)
        └─────────┘
```

---

## Connection Diagram

### Minimal UART Setup (4 wires) — Fast Start

```
┌─────────────────────────────────────────────────────────────────────┐
│           DSLogic U2basic               ←WIRE→              QMTech FPGA    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                       ┌─────────────┐                       │
│  │   DSLogic   │                       │   QMTech    │                       │
│  │   U2basic   │                       │  XC7A100T   │                       │
│  │             │                       │   Board     │                       │
│  │  ┌───────┐  │                       │             │                       │
│  │  │ CH0   │  │ ─────────────────────►│  J2 Pin 5   │  (K20 = FPGA TX)     │
│  │  │ CH1   │  │ ─────────────────────►│  J2 Pin 6   │  (L20 = FPGA RX)     │
│  │  │ CH2   │  │ ─────────────────────►│  M22        │  (50 MHz Clock)      │
│  │  │       │  │                       │             │                       │
│  │  │ GND   │  │ ─────────────────────►│  J2 Pin 1   │  (⬛ GND)            │
│  │  └───────┘  │                       │             │                       │
│  │             │                       │             │                       │
│  │  USB cable  │ ─────────────────────►│  MacBook    │                       │
│  └─────────────┘                       └─────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Full 16-Channel Setup

| DSLogic Channel | Recommended Color | FPGA Location | Signal | Purpose |
|----------------|-------------------|---------------|--------|---------|
| **GND** | ⬛ Black | J2 Pin 1 (top row, 1st hole) | Ground | MANDATORY! Doesn't work without it |
| **CH0** | 🟡 Yellow | J2 Pin 5 (top row, 3rd hole) | FPGA TX (K20) | UART data from FPGA |
| **CH1** | 🟢 Green | J2 Pin 6 (bottom row, 3rd hole) | FPGA RX (L20) | UART data to FPGA |
| **CH2** | 🔵 Blue | M22 (board, pin next to JTAG) | 50 MHz | Base oscillator |
| **CH3** | 🟣 Purple | U22 (board) | MMCM 81.25 MHz | System clock |
| **CH4** | 🔴 Red | T23 (board, LED D5) | LED output | Visual indication |
| **CH5** | Orange | [Spare - J21] | SPI_SCK | Reserved for SPI |
| **CH6** | White | [Spare - H21] | SPI_MISO | Reserved for SPI |
| **CH7** | Gray | [Spare - G22] | SPI_MOSI | Reserved for SPI |
| **CH8** | Pink | [Spare - F22] | SPI_CS | Reserved for SPI |
| **CH9** | Brown | JTAG TCK (via test hook) | JTAG Clock | For JTAG analysis |
| **CH10** | Beige | JTAG TDI (via test hook) | JTAG Data In | For JTAG analysis |
| **CH11** | Lime | JTAG TDO (via test hook) | JTAG Data Out | For JTAG analysis |
| **CH12** | Turquoise | JTAG TMS (via test hook) | JTAG Mode | For JTAG analysis |
| **CH13** | Dark Blue | [Spare - D26] | J2 Pin 5 alt | Pin mapping verification |
| **CH14** | Dark Green | [Spare - E26] | J2 Pin 6 alt | Pin mapping verification |
| **CH15** | Dark Red | [Spare] | Trigger Ref | Trigger reference |

---

## Step-by-Step Connection Guide

### ⚠️ CRITICAL RULES

1. **GND FIRST!** Always connect black wire (GND) first and disconnect last. Without ground, measurements won't work.
2. **Be careful with pins!** Don't short adjacent pins with metal probe.
3. **Test hooks for JTAG** — use small hooks for thin pins (JTAG header).
4. **Crocodile clips for GND** — use alligator clips for ground and large contacts.
5. **NEVER connect DSLogic and Xilinx JTAG to same JTAG header simultaneously!** Use test hooks to connect DSLogic to pins UNDER the cable.

### Phase 1: UART Only (Minimal Setup) — 4 wires

This is minimal setup for basic UART debugging:

```
1. 📌 Connect:
   GND  → J2 Pin 1 (⬛ black)       ← ALWAYS FIRST!
   CH0  → J2 Pin 5 (🟡 yellow)      = FPGA TX
   CH1  → J2 Pin 6 (🟢 green)       = FPGA RX
   CH2  → M22        (🔵 blue)       = 50 MHz Clock

2. 💻 Configure DSView:
   - Sample rate: 400 MS/s
   - Channels: 0, 1, 2, 3, 4 (GND on CH15 for trigger)
   - Trigger: Rising edge on CH0 (UART TX)

3. ▶️ Start capture:
   - Send UART command (e.g., PING 0x03)
   - Should see bytes on CH0 (TX) and response on CH1 (RX)

4. ✅ Verify:
   - CH0 shows data from FPGA (TX)
   - CH1 shows data from FT232RL (RX)
   - CH2 shows stable 50 MHz clock
```

### Phase 2: Full Signal Analysis — All 16 Channels

```
1. 📌 Connect all wires (see table above):
   - GND always first and last!
   - Check each connection

2. 💻 Configure DSView:
   - Sample rate: 400 MS/s (maximum)
   - Channels: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
   - Trigger: Pulse width on CH2 (50MHz, min 18ns)
   - Thresholds: 3.3V (LVCMOS33)

3. 🧪 For JTAG (if Xilinx Cable connected):
   ⚠️ ATTENTION! JTAG header is SINGLE for two sources!
   - Option A: Disconnect Xilinx Cable, connect DSLogic
   - Option B: Use test hooks to connect UNDER the cable
   - NEVER connect both TCK sources simultaneously!

   JTAG connection:
   JTAG TCK (pin 3) ──► DSLogic CH9 (brown)
   JTAG TDO (pin 4) ──► DSLogic CH11 (lime)
   JTAG TDI (pin 5) ──► DSLogic CH10 (beige)
   JTAG TMS (pin 6) ──► DSLogic CH12 (turquoise)

4. ▶️ Start capturing all signals

5. ✅ Verify all channels:
   - CH0-CH1: UART TX/RX
   - CH2: 50 MHz stable
   - CH3: MMCM clock (81.25 MHz)
   - CH4: LED indication
   - CH9-CH12: JTAG signals (if connected)
```

---

## Troubleshooting

### Problem: "No signal captured"

**Symptoms**:
- CH0-CH4 always LOW or HIGH (no changes)
- UART data not visible

**Solutions**:
1. Check GND connection (mandatory!)
2. Make sure wire didn't come off pin
3. Check voltage threshold in DSView (set 3.3V for LVCMOS33)
4. Try different wire or test hook instead of crocodile clip

### Problem: "Wrong channel shows UART"

**Symptoms**:
- CH13 or CH14 shows UART instead of CH0/CH1

**Solutions**:
1. This indicates incorrect pin mapping (D26/E26 vs K20/L20)
2. Use `tri fpga dslogic-pins` to verify mapping
3. Update `fpga/constraints/uart_bridge_j2.xdc` if error found
4. Rebuild bitstream: `tri fpga build-uart`

### Problem: "JTAG signals not visible"

**Symptoms**:
- CH9-CH12 always LOW or not changing

**Solutions**:
1. Check that Xilinx JTAG Cable is disconnected before connecting DSLogic
2. Make sure test hooks are properly connected to pins
3. JTAG header is small — use test hooks
4. Check that TCK isn't shorted to ground

### Problem: "Clock unstable"

**Symptoms**:
- CH2 (50 MHz) shows jitter or wrong frequency

**Solutions**:
1. Check that M22 is correct pin (next to JTAG)
2. Make sure 50 MHz oscillator is working
3. Check signal level (should be LVCMOS33)
4. Measure frequency at M22 directly with multimeter if possible

---

## DSView Configuration Tips

### Basic Settings

```
Channel Setup:
- Input mode: Digital
- Threshold: 3.3V (for LVCMOS33)
- Sample rate: 400 MS/s (maximum for U2basic)

Trigger Setup:
- Type: Pulse Width
- Channel: CH2 (50 MHz)
- Min width: 18ns (one period of 50 MHz)
- Direction: Rising
```

### Protocol Decoding

```
UART:
- Baud rate: 115200
- Data bits: 8
- Parity: None
- Stop bits: 1

JTAG:
- Protocol: JTAG
- TCK frequency: Auto

SPI:
- Clock polarity: CPOL=0
- Clock phase: CPHA=0
```

---

## Quick Reference

### What each channel monitors

| CH | Signal | Expected | Notes |
|----|--------|----------|-------|
| 0 | FPGA TX (K20) | UART out from FPGA |
| 1 | FPGA RX (L20) | UART in to FPGA |
| 2 | 50 MHz (M22) | Base clock reference |
| 3 | MMCM (U22) | System clock (81.25 MHz) |
| 4 | LED (T23) | Visual feedback |
| 5-8 | SPI (if implemented) | Future use |
| 9-12 | JTAG | Timing reference only |
| 13-14 | Alt mapping | Pin verification |
| 15 | Trigger | Reference |

### Expected timings at 115200 baud

```
Byte width @ 115200 baud = 8.68 µs
Bit period @ 115200 baud = 8.68 µs / 8 = 1.085 µs

Expected UART frame:
START (0) + 8 DATA bits + STOP (1) = 10 bits
Total: 8.68 µs per byte @ 115200
```

---

## Next Steps

After connection:

1. Run diagnostics: `tri fpga dslogic-connect`
2. Capture signals: `tri fpga dslogic-capture --preset full_analysis`
3. Analyze UART: `tri fpga dslogic-uart`
4. Check pin mapping: `tri fpga dslogic-pins`
5. Log results to: `.trinity/fpga/experience.json`

---

## Safety Notes

1. ⚠️ **Disconnect GND last** — disconnect ground last
2. ⚠️ **No power while wiring** — don't power board during connection
3. ⚠️ **Double-check before powering** — make sure there are no shorts
4. ⚠️ **One JTAG source** — never connect Xilinx Cable and DSLogic to same JTAG header simultaneously

---

φ² + 1/φ² = 3 = TRINITY
