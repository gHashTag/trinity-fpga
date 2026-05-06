`timescale 1ns / 1ps

module PLLE2_BASE (
    input  wire CLKIN1,
    input  wire CLKFBIN,
    input  wire RST,
    input  wire PWRDWN,
    output wire CLKOUT0,
    output wire CLKOUT1,
    output wire CLKOUT2,
    output wire CLKOUT3,
    output wire CLKOUT4,
    output wire CLKOUT5,
    output wire CLKFBOUT,
    output wire LOCKED
);

    parameter CLKIN1_PERIOD    = 20.0;
    parameter CLKFBOUT_MULT    = 13;
    parameter CLKOUT0_DIVIDE   = 8;
    parameter DIVCLK_DIVIDE    = 1;

    localparam FOUT = (1.0 / (CLKIN1_PERIOD * 1e-9)) * CLKFBOUT_MULT / (CLKOUT0_DIVIDE * DIVCLK_DIVIDE);
    localparam PERIOD_NS = 1.0e9 / FOUT;

    reg clk_out = 0;
    reg locked_reg = 0;

    initial begin
        #500;
        locked_reg = 1;
    end

    always #(PERIOD_NS / 2.0) clk_out = ~clk_out;

    assign CLKOUT0  = clk_out;
    assign CLKOUT1  = 1'b0;
    assign CLKOUT2  = 1'b0;
    assign CLKOUT3  = 1'b0;
    assign CLKOUT4  = 1'b0;
    assign CLKOUT5  = 1'b0;
    assign CLKFBOUT = clk_out;
    assign LOCKED   = locked_reg;

endmodule
