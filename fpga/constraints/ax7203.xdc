## ALINX AX7203 -- XC7A200T-FBG484-2
## Pins verified on hardware, fpga/experience/2026-06-24-ax7203-blinky-openxc7.trinity.md
## nextpnr-xilinx does NOT expand grouped assignments: one port per line.

set_property PACKAGE_PIN R4 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property PACKAGE_PIN T4 [get_ports clk200_n]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]

set_property PACKAGE_PIN T6 [get_ports rst_n]
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]

set_property PACKAGE_PIN B13 [get_ports {led[0]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[0]}]
set_property PACKAGE_PIN C13 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[1]}]
set_property PACKAGE_PIN D14 [get_ports {led[2]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[2]}]
set_property PACKAGE_PIN D15 [get_ports {led[3]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[3]}]

set_property PACKAGE_PIN N15 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property PACKAGE_PIN P20 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]

create_clock -period 5.000 -name clk200 [get_ports clk200_p]
