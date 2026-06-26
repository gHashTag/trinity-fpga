# =============================================================================
# dual_clk_heartbeat_ax7203 constraints — ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# Tests BOTH clocks: 200 MHz differential (IBUFDS->BUFG, raw, no PLL — same as
# gf16) AND STARTUPE2 CFGMCLK. Only rst_n + uart_tx are pinned (no LEDs; the
# UART stream is the observable). Per-port IOSTANDARD (nextpnr requirement).
# =============================================================================

# 200 MHz differential clock (DIFF_SSTL15, NOT LVDS)
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]
set_property PACKAGE_PIN R4 [get_ports clk200_p]
set_property PACKAGE_PIN T4 [get_ports clk200_n]
create_clock -period 5.000 -name clk200 [get_ports clk200_p]

# CPU_RESET_N (active-low)
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6      [get_ports rst_n]

# UART TX (FPGA -> host), bridge = /dev/cu.usbserial-120 (CP2102N)
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property PACKAGE_PIN N15     [get_ports uart_tx]
