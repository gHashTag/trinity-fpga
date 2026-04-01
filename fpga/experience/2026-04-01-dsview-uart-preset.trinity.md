# DSVIEW PRESET: UART Debug for QMTech XC7A100T + J2
Date: 2026-04-01
Target: QMTech XC7A100T-FGG676
Tools: DSView 1.3.2, DSLogic U2basic

## Quick Setup (2 minutes)

### 1. Launch DSView
```bash
open -a DSView
# Or from Applications
```

### 2. Basic Settings
| Parameter | Value |
|-----------|-------|
| Sample Rate | 400 MS/s (or less to start) |
| Channels | 0, 1, 2, 15 |
| Trigger | None (for now) |
| Threshold | 3.3V (LVCMOS33) |

### 3. Connect DSLogic to J2
| DSLogic | Color | J2 Pin | Signal |
|---------|-------|--------|--------|
| GND | ⬛ Black | pin 1 (bottom, 1st) | Ground |
| CH0 | 🟡 Yellow | pin 5 (bottom, 3rd) | FPGA TX |
| CH1 | 🟢 Green | pin 6 (top, 3rd) | FPGA RX |
| CH2 | 🔵 Blue | M22 (board) | 50 MHz clock |

### 4. UART Decoder
In DSView add protocol:
1. Right click → Add → Protocol Decoder → UART
2. Settings:
   - Baud rate: 115200
   - Data bits: 8
   - Parity: None
   - Stop bits: 1
3. Bind to CH0 or CH1

## Expected Signals
### When sending `aaaa` via `/dev/cu.usbserial-2140`:
```
CH1 (FT232RL TX): ──╦╩╦╩╩╦╩╦──  ← 115200 baud UART
CH0 (FPGA RX):   ─────────────  ← FPGA doesn't respond (no firmware)
```

### With working uart_bridge on FPGA:
```
CH0 (FPGA TX):    ──╦╩╦╩╩╦╩╦──  ← FPGA responds
CH1 (FPGA RX):    ──╦╩╦╩╩╦╩╦──  ← FT232RL sends
```

## Troubleshooting
| Symptom | Cause | Solution |
|---------|-------|----------|
| All lines noisy | GND not connected | Connect CH15/GND to J2 pin 1 |
| CH0 empty | FPGA not flashed | Flash uart_bridge_j2.bit |
| CH1 empty | FT232RL not sending | Send data via screen/CoolTerm |
| Clock not visible | Wire on wrong pin | Check M22 for CH2 |

## Preset for DSView (save as .json)
```json
{
  "version": "1.0",
  "name": "QMTech J2 UART Debug",
  "sample_rate": "400M",
  "channels": [0, 1, 2, 15],
  "trigger": null,
  "decoders": [
    {
      "protocol": "UART",
      "channel": 0,
      "baud_rate": 115200,
      "data_bits": 8,
      "parity": "none",
      "stop_bits": 1
    }
  ]
}
```
