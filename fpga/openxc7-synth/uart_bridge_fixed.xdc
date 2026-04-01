# ============================================================================
# UART Bridge Fixed — Pin Constraints for QMTECH XC7A100T-1FGG676C
# ============================================================================
# VERIFIED: 2026-04-01 — Pins from DSLogic U2basic measurements on board
# FT232RL Wiring (per DSLogic guide, confirmed on PCB):
#   TXD (white)  → J2 pin 5  → K20 → FPGA uart_rx
#   RXD (green)  → J2 pin 6  → L20 → FPGA uart_tx
#   GND (black) → J2 pin 1  → GND
# ============================================================================
# DSLogic Connection Guide:
#   CH0 (Yellow) → J2 pin 5 → K20 (FPGA TX) ✅
#   CH1 (Green)  → J2 pin 6 → L20 (FPGA RX) ✅
# ============================================================================

# Clock input (50 MHz oscillator) — M22
set_property LOC M22 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 20.000 -name sys_clk [get_ports clk]

# UART RX (from FT232RL TXD → FPGA) — K20 (J2 pin 5)
set_property LOC K20 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]

# UART TX (from FPGA → FT232RL RXD) — L20 (J2 pin 6)
set_property LOC L20 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]

# LED (active-low, T23)
set_property LOC T23 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# Bitstream config
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
