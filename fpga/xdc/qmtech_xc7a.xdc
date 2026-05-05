## QMTech XC7A100T/200T Starter Kit -- Validated XDC
## Commit: a63d3fb8  |  IDCODE: 0x13631093 (XC7A200T v1)
## STAT: 0x401079FC  DONE=1  EOS=1  GWE=1  MMCM_LOCK=1
## phi^2 + phi^-2 = 3  |  trios#380 App.I

## ============================================================
## CLOCK  -- 50 MHz on-board oscillator
## ============================================================
set_property PACKAGE_PIN U18 [get_ports clk_50mhz]
set_property IOSTANDARD  LVCMOS33 [get_ports clk_50mhz]
create_clock -period 20.000 -name clk50 [get_ports clk_50mhz]

## ============================================================
## UART  -- P1 expansion header
## ============================================================
set_property PACKAGE_PIN D20 [get_ports uart_tx]
set_property IOSTANDARD  LVCMOS33 [get_ports uart_tx]

set_property PACKAGE_PIN E19 [get_ports uart_rx]
set_property IOSTANDARD  LVCMOS33 [get_ports uart_rx]

## ============================================================
## LEDs  -- active HIGH
## ============================================================
set_property PACKAGE_PIN R14 [get_ports {led[0]}]
set_property PACKAGE_PIN P14 [get_ports {led[1]}]
set_property PACKAGE_PIN N16 [get_ports {led[2]}]
set_property PACKAGE_PIN M16 [get_ports {led[3]}]
set_property IOSTANDARD  LVCMOS33 [get_ports led]

## ============================================================
## Timing false paths (async outputs -- no setup/hold needed)
## ============================================================
set_false_path -to [get_ports uart_tx]
set_false_path -to [get_ports led]
