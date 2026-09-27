# =============================================================================
# eth_arp_icmp_ax7203 constraints -- ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# Ethernet step E3 (conformance/NODE_ETHERNET_PLAN.md, draft section in
# conformance/E3_DRAFT_SECTION.md). Built, NOT flashed.
#
# Pins and IOSTANDARDs: those of eth_phy_status_ax7203.xdc (E2), unchanged.
# E2 and the one-bit fix e2z ran on the board with them (MDIO answered, PHY ID
# 00221622, link 100 FD); VCCO_16 itself is still not read off the schematic.
# One pin per line: nextpnr's XDC parser does not expand [*] or {..}.
#
# New in E3: the six transmit pins now carry frames (TXC 25 MHz, TXD/TX_CTL
# nibbles). SLEW FAST on them: 12 mA LVCMOS33 at the default SLOW slew has
# edges of several ns, which eat into the 20 ns half period the design leaves
# around each TXC edge (header of fpga/vivado/eth_arp_icmp_ax7203.v).
# No clock constraint on TXC: it is a LUT output of the RXC domain.
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

# RGMII transmit: 100BASE-TX frames, TXC derived from RXC (no ODDR)
set_property IOSTANDARD LVCMOS33 [get_ports eth_txc]
set_property PACKAGE_PIN E18     [get_ports eth_txc]
set_property SLEW FAST           [get_ports eth_txc]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txctl]
set_property PACKAGE_PIN F18     [get_ports eth_txctl]
set_property SLEW FAST           [get_ports eth_txctl]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[0]]
set_property PACKAGE_PIN C20     [get_ports eth_txd[0]]
set_property SLEW FAST           [get_ports eth_txd[0]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[1]]
set_property PACKAGE_PIN D20     [get_ports eth_txd[1]]
set_property SLEW FAST           [get_ports eth_txd[1]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[2]]
set_property PACKAGE_PIN A19     [get_ports eth_txd[2]]
set_property SLEW FAST           [get_ports eth_txd[2]]
set_property IOSTANDARD LVCMOS33 [get_ports eth_txd[3]]
set_property PACKAGE_PIN A18     [get_ports eth_txd[3]]
set_property SLEW FAST           [get_ports eth_txd[3]]
