// Behavioral mock of Xilinx STARTUPE2 for iverilog simulation.
// Provides CFGMCLK (~71 MHz sim clock) + EOS=1 so the design's rst deasserts.
// (Real primitive only in Vivado/UNISIM; this mock lets iverilog elaborate
//  CFGMCLK-based AX7203 designs like gf8_clean / corona_decode_top.)
module STARTUPE2 #(
    parameter PROG_USR = "FALSE",
    parameter SIM_CCLK_FREQ = 0.0
)(
    output CFGCLK,
    output reg CFGMCLK,
    output EOS,
    input CLK, input GSR, input GTS, input KEYCLEARB, input PACK,
    input USRCCLKO, input USRCCLKTS, input USRDONEO, input USRDONETS
);
    initial CFGMCLK = 1'b0;
    always #7 CFGMCLK = ~CFGMCLK;   // ~71 MHz simulation clock
    assign CFGCLK = 1'b0;
    assign EOS = 1'b1;              // end-of-startup -> rst deasserts
endmodule
