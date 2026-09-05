# Digilent Arty A7-35T. Pins transcribed from prjxray's own harness
# (prjxray-db/artix7/harness/arty-a7/swbut/design.txt), so they are known good.
# IDENTICAL in build A and build B -- that is the point.

set_property PACKAGE_PIN E3  [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

set_property PACKAGE_PIN A8  [get_ports d]
set_property IOSTANDARD LVCMOS33 [get_ports d]

set_property PACKAGE_PIN H5  [get_ports q1]
set_property IOSTANDARD LVCMOS33 [get_ports q1]

set_property PACKAGE_PIN J5  [get_ports q2]
set_property IOSTANDARD LVCMOS33 [get_ports q2]

