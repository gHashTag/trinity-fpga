# EXPERIENCE: DSLogic + FT232RL + QMTech J2 (UART, no JTAG)
Date: 2026-04-01
Board: QMTech XC7A100T
Host: macOS ARM (MacBook)
Tools: DSLogic U2basic, FT232RL, DSView 1.3.2, FNIRSI 2C23T

## Goal
Verify physical UART and clock wiring without working JTAG firmware.

## Final truth (source of truth)

### J2 header numbering (IMPORTANT)
- On board labeled: **2 = top row, 1 = bottom row**.
- Count holes **left to right**.
- Bottom row (1): pin1, pin3, pin5, pin7, ...
- Top row (2): pin2, pin4, pin6, pin8, ...

### FT232RL → J2
- Black = GND → **J2 pin1 (bottom row, 1st hole)**.
- White = RXD (cable listens) → **J2 pin5 (bottom row, 3rd hole)**.
- Green = TXD (cable sends) → **J2 pin6 (top row, 3rd hole)**.
- Red = VCC (~5.5 V) → **DO NOT CONNECT ANYWHERE**.
- Blue = 2 V (CTS/RTS) → not used.
- Yellow = 3.3 V (DTR) → not used.

### DSLogic U2basic (right slot "0-3")
DSLogic numbering right to left: [CK/TI/TO] [12–15] [8–11] [4–7] [0–3].

Group **0–3** (rightmost slot):
- Colors in my kit: **black – purple – blue – green – yellow**.
- Black = common GND for group.
- Yellow = **CH0**.
- Green = **CH1**.
- Others (purple, blue) = CH2/CH3, currently unused.

DSLogic connection:
- Black (GND) → **same J2 pin1 pin** where black FT232RL is.
- Yellow (CH0) → **same pin5 pin** where white FT232RL is.
- Green (CH1) → **same pin6 pin** where green FT232RL is.

### Verified fact (FNIRSI + DSLogic)
- FNIRSI in DMM mode:
  - Black probe on black FT232RL → reading 0 V.
  - White and green = ~3.3 V (UART idle HIGH).
  - Red = ~5.5 V (power, dangerous for J2).
- FNIRSI in OSC mode:
  - CH1 on J2 pin6 + GND → when sending `aaaa` via `/dev/cu.usbserial-2140` see UART pulses.
- DSView:
  - CH0/CH1 — flat lines when no traffic.
  - CH2/CH3 (when separately connected) see 50 MHz and 81.25 MHz, meaning clocks are alive.

## Known limits / TODO
- JTAG (DLC10) doesn't work on macOS ARM (neither Xilinx nor openFPGALoader): libusb/FTDI errors.
- Cannot flash new bitstreams with current hardware set.
- Next step: add either Linux host with Xilinx/xc3sprog, or RP2040/ESP32/CH341A.

## Pitfalls (what not to repeat)
- DON'T:
  - Connect **red 5.5 V** FT232RL wire to J2.
  - Confuse top/bottom J2: **2 = top, 1 = bottom**.
  - Trust DSLogic colors without verification — in future always confirm via DSView (short to GND).
