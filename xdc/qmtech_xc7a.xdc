// SPDX-License-Identifier: Apache-2.0
################################################################################
# QMTECH XC7A100T (Wukong Board) XDC Constraints File
# For ZeroDSP FPGA Implementation
# phi^2 + 1/phi^2 = 3 | TRINITY
################################################################################
# Board: QMTECH XC7A100T-324 Core Board + Wukong Expansion
# FPGA:  Xilinx Artix-7 XC7A100T-CSG324
# Clock: 12 MHz input clock
################################################################################
# Pin conflict fix: UART changed from 8-bit parallel to 1-bit serial.
# All pins are now unique (no duplicates).
################################################################################

################################################################################
# Clock Constraints
################################################################################

# System clock - 12MHz input
set_property -dict { PACKAGE_PIN E3    IOSTANDARD LVCMOS33 } [get_ports clk]
create_clock -add -name sys_clk -period 83.333 -waveform {0 41.666} [get_ports clk]

# Reset button (active low)
set_property -dict { PACKAGE_PIN C17   IOSTANDARD LVCMOS33 } [get_ports rst_n]

################################################################################
# UART Signals (CP2102 USB-UART bridge) - 1-bit serial, 8N1 @ 115200 baud
################################################################################

# UART RX (FPGA receives from USB-UART)
set_property -dict { PACKAGE_PIN T14   IOSTANDARD LVCMOS33 } [get_ports uart_rx]

# UART TX (FPGA transmits to USB-UART)
set_property -dict { PACKAGE_PIN T15   IOSTANDARD LVCMOS33 } [get_ports uart_tx]

################################################################################
# SPI Master Interface (Pmod Header A - J10)
# Mode 0: CPOL=0, CPHA=0
################################################################################

set_property -dict { PACKAGE_PIN G4    IOSTANDARD LVCMOS33 } [get_ports spi_cs]
set_property -dict { PACKAGE_PIN G3    IOSTANDARD LVCMOS33 } [get_ports spi_sck]
set_property -dict { PACKAGE_PIN G2    IOSTANDARD LVCMOS33 } [get_ports spi_mosi]
set_property -dict { PACKAGE_PIN G6    IOSTANDARD LVCMOS33  PULLUP true } [get_ports spi_miso]

################################################################################
# LED Outputs (8 LEDs on Wukong board)
# No pin conflicts: all unique
################################################################################

set_property -dict { PACKAGE_PIN H17   IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN K15   IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN J13   IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN N14   IOSTANDARD LVCMOS33 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN R18   IOSTANDARD LVCMOS33 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN U18   IOSTANDARD LVCMOS33 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN T13   IOSTANDARD LVCMOS33 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN T11   IOSTANDARD LVCMOS33 } [get_ports { led[7] }]

################################################################################
# MAC Debug Interface (Pmod Header B - J11)
# 8-bit result + done flag for debug visibility
# Full 32-bit accumulator available via UART command protocol
################################################################################

# MAC done flag
set_property -dict { PACKAGE_PIN D5    IOSTANDARD LVCMOS33 } [get_ports mac_done]

# MAC result[7:0] - lower byte for debug LED/view
set_property -dict { PACKAGE_PIN D7    IOSTANDARD LVCMOS33 } [get_ports { mac_result[0] }]
set_property -dict { PACKAGE_PIN E6    IOSTANDARD LVCMOS33 } [get_ports { mac_result[1] }]
set_property -dict { PACKAGE_PIN E5    IOSTANDARD LVCMOS33 } [get_ports { mac_result[2] }]
set_property -dict { PACKAGE_PIN A5    IOSTANDARD LVCMOS33 } [get_ports { mac_result[3] }]
set_property -dict { PACKAGE_PIN A4    IOSTANDARD LVCMOS33 } [get_ports { mac_result[4] }]
set_property -dict { PACKAGE_PIN F4    IOSTANDARD LVCMOS33 } [get_ports { mac_result[5] }]
set_property -dict { PACKAGE_PIN H4    IOSTANDARD LVCMOS33 } [get_ports { mac_result[6] }]
set_property -dict { PACKAGE_PIN B4    IOSTANDARD LVCMOS33 } [get_ports { mac_result[7] }]

# MAC result[15:8] and [31:16] removed: not enough valid CSG324 pins
# Full 32-bit accumulator available via UART command protocol

################################################################################
# Configuration Options
################################################################################

set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]

################################################################################
# Timing Constraints
################################################################################

# Async input: reset is asynchronous
set_false_path -from [get_ports rst_n] -to [all_registers]

# UART is asynchronous input
set_false_path -from [get_ports uart_rx] -to [all_registers]

# SPI MISO is asynchronous input
set_false_path -from [get_ports spi_miso] -to [all_registers]

################################################################################
# I/O Standards
################################################################################

set_property IOSTANDARD LVCMOS33 [current_design]
