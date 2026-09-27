# =============================================================================
# eth_phy_status_ax7203 constraints -- ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# Ethernet step E2 (conformance/NODE_ETHERNET_PLAN.md). Built, NOT flashed.
#
# Pins: port 0, KSZ9031RNX, as in ~/trinity/fpga/openxc7-synth/ax7203_rgmii.xdc,
# which matches LiteX's alinx_ax7203 platform on all 15 pins (checked, plan
# doc). One pin per line: nextpnr's XDC parser does not expand [*] or {..}.
#
# IOSTANDARD: LVCMOS33 on the 15 Ethernet pins, as LiteX's alinx_ax7203 sets.
# OPEN BEFORE ANY FLASH: the pins sit in bank 16, and specs/fpga/constraints/
# ax7203.xdc puts the user LEDs on bank 16 too (B13, C13) as LVCMOS18. One bank
# has one VCCO, so one of the two files is wrong. The rgmii file above leaves
# IOSTANDARD out for exactly this reason. Read VCCO_16 off the AX7203
# schematic (or measure it) before this bitstream goes near the board.
# =============================================================================

# CPU_RESET_N key, active low
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6      [get_ports rst_n]

# UART TX to the CP2102N, same pin and standard as the node
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]
set_property PACKAGE_PIN N15     [get_ports uart_tx]

# PHY hardware reset, driven by the FPGA, active low
set_property IOSTANDARD LVCMOS33 [get_ports eth_rst_n]
set_property PACKAGE_PIN D16     [get_ports eth_rst_n]

# Management: MDC out, MDIO bidirectional (IOBUF)
set_property IOSTANDARD LVCMOS33 [get_ports eth_mdc]
set_property PACKAGE_PIN B16     [get_ports eth_mdc]
set_property IOSTANDARD LVCMOS33 [get_ports eth_mdio]
set_property PACKAGE_PIN B15     [get_ports eth_mdio]

# RGMII receive: RXC on SRCC B17 (routes only with nextpnr-xilinx #110)
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxc]
set_property PACKAGE_PIN B17     [get_ports eth_rxc]
create_clock -period 8.000 -name eth_rxc [get_ports eth_rxc]
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxctl]
set_property PACKAGE_PIN A15     [get_ports eth_rxctl]
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxd[0]]
set_property PACKAGE_PIN A16     [get_ports eth_rxd[0]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxd[1]]
set_property PACKAGE_PIN B18     [get_ports eth_rxd[1]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxd[2]]
set_property PACKAGE_PIN C18     [get_ports eth_rxd[2]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_rxd[3]]
set_property PACKAGE_PIN C19     [get_ports eth_rxd[3]]

# RGMII transmit: held at 0 by the design (TX_CTL low = PHY sends nothing).
# Pinned so they are driven, not left floating into the PHY.
set_property IOSTANDARD LVCMOS33 [get_ports eth_txc]
set_property PACKAGE_PIN E18     [get_ports eth_txc]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txctl]
set_property PACKAGE_PIN F18     [get_ports eth_txctl]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[0]]
set_property PACKAGE_PIN C20     [get_ports eth_txd[0]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[1]]
set_property PACKAGE_PIN D20     [get_ports eth_txd[1]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[2]]
set_property PACKAGE_PIN A19     [get_ports eth_txd[2]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[3]]
set_property PACKAGE_PIN A18     [get_ports eth_txd[3]]
