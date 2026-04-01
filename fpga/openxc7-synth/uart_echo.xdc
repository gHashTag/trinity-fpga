# ============================================================================
# UART Echo Minimal — Pin Constraints (CORRECTED per README.md)
# ============================================================================
# FT232RL Wiring (README.md canonical):
#   RXD (green)  → J2 pin 5  → K20 → FPGA uart_tx (out)
#   TXD (white)  → J2 pin 6  → L20 → FPGA uart_rx (in)
#   GND (black) → J2 pin 1  → GND
# ============================================================================

# Clock input (50 MHz oscillator) — M22
set_property LOC M22 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 20.000 -name sys_clk [get_ports clk]

# UART TX (from FPGA → FT232RL RXD) — K20 (J2 pin 5, green wire)
set_property LOC K20 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]

# UART RX (from FT232RL TXD → FPGA) — L20 (J2 pin 6, white wire)
set_property LOC L20 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]

# LED (active-low, T23)
set_property LOC T23 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# Bitstream config
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
