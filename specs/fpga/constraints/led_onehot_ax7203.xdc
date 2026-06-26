# =============================================================================
# led_onehot_ax7203 constraints — ALINX AX7203 (xc7a200tfbg484-2)
# =============================================================================
# NOTE: this design uses STARTUPE2 CFGMCLK (internal config clock), so there is
# NO external clock port. Only the reset button and the 4 user LEDs are pinned.
#
# CRITICAL (nextpnr-xilinx does NOT expand grouped XDC assignments): set
# IOSTANDARD and PACKAGE_PIN per individual port, never grouped.
# =============================================================================

# CPU_RESET_N (active-low)
set_property IOSTANDARD LVCMOS15 [get_ports rst_n]
set_property PACKAGE_PIN T6      [get_ports rst_n]

# User LEDs (active-high)
set_property IOSTANDARD LVCMOS18 [get_ports led[0]]
set_property IOSTANDARD LVCMOS18 [get_ports led[1]]
set_property IOSTANDARD LVCMOS18 [get_ports led[2]]
set_property IOSTANDARD LVCMOS18 [get_ports led[3]]
set_property PACKAGE_PIN B13 [get_ports led[0]]
set_property PACKAGE_PIN C13 [get_ports led[1]]
set_property PACKAGE_PIN D14 [get_ports led[2]]
set_property PACKAGE_PIN D15 [get_ports led[3]]
