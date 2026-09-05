# W982: the divided domain, declared -- same period the five-instance design
# holds (T607). This one carries three GftSmul instances instead of five, so
# 8.85 MHz stands with at least the margin gft_dup_jtag measured.
create_clock -period 113.0 -name slowclk [get_nets slowclk]
