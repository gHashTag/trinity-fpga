// Simulation-only behavioural stubs for the three Xilinx primitives the probe uses.
`timescale 1ps/1ps
module IBUFDS(input I, input IB, output O); assign O = I & ~IB; endmodule
module BUFG(input I, output O); assign O = I; endmodule
module STARTUPE2 #(parameter PROG_USR="FALSE", parameter real SIM_CCLK_FREQ=0.0)(
  output CFGCLK, output reg CFGMCLK = 0, output EOS, output PREQ,
  input CLK, GSR, GTS, KEYCLEARB, PACK, USRCCLKO, USRCCLKTS, USRDONEO, USRDONETS);
  always #7267 CFGMCLK = ~CFGMCLK;   // 68.8 MHz, the slowest die in the repo record
endmodule
