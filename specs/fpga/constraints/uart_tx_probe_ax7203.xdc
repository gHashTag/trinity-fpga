# =============================================================================
# uart_tx_probe_ax7203 constraints — ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# Design uses STARTUPE2 CFGMCLK (internal config clock) -> no external clock.
# Pins: rst_n (reset), LED1..LED4 (parallel visual), uart_tx (FPGA->host).
# Per-port IOSTANDARD (nextpnr-xilinx does not expand grouped assignments).
# LED standard LVCMOS18 verified working on this board (matches ax7203.xdc /
# gf16_ax7203.xdc). Silkscreen<->pin anchor verified on hardware 2026-06-26:
# LED1=B13, LED2=C13, LED3=D14, LED4=D15.
# =============================================================================

# CPU_RESET_N (active-low)
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6      [get_ports rst_n]

# User LEDs (active-high)
set_property IOSTANDARD LVCMOS18 [get_ports led[0]]
set_property IOSTANDARD LVCMOS18 [get_ports led[1]]
set_property IOSTANDARD LVCMOS18 [get_ports led[2]]
set_property IOSTANDARD LVCMOS18 [get_ports led[3]]
set_property PACKAGE_PIN B13 [get_ports led[0]]
set_property PACKAGE_PIN C13 [get_ports led[1]]
set_property PACKAGE_PIN D14 [get_ports led[2]]
set_property PACKAGE_PIN D15 [get_ports led[3]]

# UART TX (FPGA -> host)
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property PACKAGE_PIN N15     [get_ports uart_tx]
