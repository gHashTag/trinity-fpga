# ============================================================================
# XDC Constraints generated from Trinity Pins DSL
# Design: uart_bridge_fixed
# Board: qmtech_xc7a100t
# FPGA: xc7a100t_fgg676
# ============================================================================
# board.clock.osc50
set_property LOC M22 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]

# board.uart.ft232rl.txd
set_property LOC K20 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]

# board.uart.ft232rl.rxd
set_property LOC L20 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]

# board.led.status
set_property LOC T23 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]

# Bitstream config
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
