# JTAG Wiring — ESP32 → QMTech XC7A FPGA

**φ² + φ⁻² = 3** | trios#380 App.I

## 5-Wire Harness

| JTAG Signal | ESP32 GPIO | FPGA P2 Pin | Wire Colour | Direction |
|---|---|---|---|---|
| TMS | **GPIO18** | P2-3 | 🟡 Yellow | ESP32 → FPGA |
| TCK | **GPIO19** | P2-5 | 🔵 Blue | ESP32 → FPGA |
| TDI | **GPIO23** | P2-7 | 🟢 Green | ESP32 → FPGA |
| TDO | **GPIO35** | P2-9 | ⚪ White | FPGA → ESP32 |
| GND | GND | P2-2 | ⚫ Black | Common |

## Critical Notes

- **GPIO35** on ESP32 is **input-only** — no internal pull-up. This is *correct* for TDO. Using any GPIO with a pull-up causes BLK-002 (TDO stuck HIGH).
- Add a **1kΩ pull-down** on the TDO wire near the FPGA header to prevent floating when FPGA output is Hi-Z.
- **100Ω series resistor** on UART RX prevents ground-loop noise from ESP32 WiFi radio (BLK-005).
- Power ESP32 from a **separate USB port** than the FPGA board to avoid shared-ground interference.

## Wiring Diagram (ASCII)

```
 ESP32 DevKit          QMTech XC7A
 ┌──────────┐          ┌──────────┐
 │ GPIO18 ──┼─YEL─────►│ TMS(P2-3)│
 │ GPIO19 ──┼─BLU─────►│ TCK(P2-5)│
 │ GPIO23 ──┼─GRN─────►│ TDI(P2-7)│
 │ GPIO35 ◄─┼─WHT──────│ TDO(P2-9)│
 │ GND    ──┼─BLK─────►│ GND(P2-2)│
 └──────────┘          └──────────┘
     WiFi 802.11
  192.168.1.30:2542
       XVC TCP
```

## Validation

After wiring, check IDCODE:
```bash
cd fpga/xvc-esp32
# Flash firmware, then:
python3 tools/idcode_test.py --host 192.168.1.30 --port 2542
# Expected output:
# IDCODE: 0x13631093  (XC7A200T v1)  ✅
```
