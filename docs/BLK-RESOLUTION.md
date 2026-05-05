# BLK-001..005 Quick Resolution Reference

**φ² + φ⁻² = 3** | trios#380 App.J

| ID | Blocker | Root Cause | Fix | Status |
|---|---|---|---|---|
| BLK-001 | DLC10 fails on macOS Sonoma | Apple FTDI stub driver claims FT2232H, blocks libftdi | ESP32 XVC WiFi bridge (no kernel ext needed) | ✅ Resolved |
| BLK-002 | TDO stuck HIGH | GPIO34 has internal pull-up; floats HIGH when FPGA Hi-Z | Switch to GPIO35 (input-only, no pull-up) + 1kΩ pull-down | ✅ Resolved |
| BLK-003 | IDCODE 4 bits wrong (pos 14,15,16,28) | 32-bit word shift + XVC LSB-first = endianness mismatch | Rewrite `handle_shift()` as bit-serial loop | ✅ Resolved |
| BLK-004 | IDCODE `0x13631093` ≠ expected `0x0362D093` | Board labelled 100T, die is actually XC7A200T v1 | No action — design fits either device | ✅ N/A |
| BLK-005 | UART RX framing errors | Ground loop: ESP32 WiFi noise couples into shared USB ground | 100Ω series on RX + separate USB port for ESP32 | ✅ Resolved |

## Final State

```
IDCODE : 0x13631093  (XC7A200T v1)
STAT   : 0x401079FC
DONE   : 1  ✅
```

Date: 2026-05-05 | Ko Samui +07
