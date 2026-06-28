# corona_decode_ax7203.xdc — pin constraints for corona_decode_top_ax7203 on AX7203.
# AX7203 = ALINX Artix-7 XC7A200T-2FBG484 (xc7a200tfbg484-2), IDCODE 0x13636093.
# Pins from the verified AX7203 hardware-truth memory (CFGMCLK is INTERNAL via
# STARTUPE2 — no external clock pin). LED bank is LVCMOS18 (NOT LVCMOS33).

# Active-low reset (LVCMOS15)
set_property -dict {PACKAGE_PIN T6  IOSTANDARD LVCMOS15} [get_ports rst_n]

# UART bridge -> on-board CP2102N (/dev/cu.usbserial-120), LVCMOS33
set_property -dict {PACKAGE_PIN P20 IOSTANDARD LVCMOS33} [get_ports uart_rx]
set_property -dict {PACKAGE_PIN N15 IOSTANDARD LVCMOS33} [get_ports uart_tx]

# LEDs B13/C13/D14/D15 — LVCMOS18 (CRITICAL: NOT LVCMOS33, IO-bank damage risk)
set_property -dict {PACKAGE_PIN B13 IOSTANDARD LVCMOS18} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN C13 IOSTANDARD LVCMOS18} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN D14 IOSTANDARD LVCMOS18} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN D15 IOSTANDARD LVCMOS18} [get_ports {led[3]}]
