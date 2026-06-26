# =============================================================================
# rx_echo_hb_ax7203 constraints — ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# RX-direction isolator on CFGMCLK (no 200 MHz — intentionally isolated). Pins:
# rst_n (reset), uart_rx (P20, host->FPGA), uart_tx (N15, FPGA->host).
# Per-port IOSTANDARD (nextpnr requirement). Bridge = /dev/cu.usbserial-120.
# =============================================================================

set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6      [get_ports rst_n]

set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]
set_property PACKAGE_PIN P20     [get_ports uart_rx]

set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property PACKAGE_PIN N15     [get_ports uart_tx]
