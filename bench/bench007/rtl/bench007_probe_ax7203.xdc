## BENCH-007 probe -- ALINX AX7203, XC7A200T-FBG484-2
## Pins from gHashTag/trinity-fpga fpga/constraints/ax7203.xdc (verified on hardware 2026-06-24).
## nextpnr-xilinx does not expand grouped assignments: one port per line.

set_property PACKAGE_PIN R4 [get_ports clk200_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_p]
set_property PACKAGE_PIN T4 [get_ports clk200_n]
set_property IOSTANDARD DIFF_SSTL15 [get_ports clk200_n]

set_property PACKAGE_PIN N15 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]

set_property PACKAGE_PIN B13 [get_ports {led[0]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[0]}]
set_property PACKAGE_PIN C13 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[1]}]
set_property PACKAGE_PIN D14 [get_ports {led[2]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[2]}]
set_property PACKAGE_PIN D15 [get_ports {led[3]}]
set_property IOSTANDARD LVCMOS18 [get_ports {led[3]}]

## Every clock NET is constrained explicitly: nextpnr-xilinx does not carry a
## port constraint through IBUFDS/BUFG, and an unconstrained clock silently
## gets --freq. Build with --freq 50 so an unconstrained clock shows up as
## "PASS at 50.00 MHz" in the log instead of hiding behind a plausible number.
##   clk200  : crystal, 200 MHz (drives only the /2 toggle)
##   ref_clk : crystal / 2 = 100 MHz (gate counter, UART)
##   dut_clk : CFGMCLK, declared at 100 MHz -- above the 68.8-70.77 MHz the repo
##             measured on three dice, so a PASS here is a PASS at the real clock.
## Build WITHOUT --timing-allow-fail: a bitstream that fails timing is not used.
create_clock -period 5.000 -name clk200_port [get_ports clk200_p]
create_clock -period 5.000 [get_nets clk200]
create_clock -period 10.000 [get_nets ref_clk]
create_clock -period 10.000 [get_nets dut_clk]
