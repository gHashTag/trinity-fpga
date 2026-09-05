# Digilent Arty A7-35T. Pins transcribed from prjxray's own harness
# (prjxray-db/artix7/harness/arty-a7/swbut/design.txt), the same source the
# IDDR probe used, so they are known good.
#
# The part matches the goldens in nextpnr-xilinx#150, so a Vivado reference
# build of this probe needs no re-pinning.

set_property PACKAGE_PIN E3 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

# LED0 on the Arty A7. An output pin rather than an LED is the point: the
# ODDR that drives it is the OLOGIC flop the regional clock has to reach.
set_property PACKAGE_PIN H5 [get_ports clk_out]
set_property IOSTANDARD LVCMOS33 [get_ports clk_out]
