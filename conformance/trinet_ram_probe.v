`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// trinet_ram_probe — the node's x RAM template, alone, for portability_check.
//
// WHY THIS FILE EXISTS. The x RAM the batch ops added is a synchronous-read
// inferred RAM: `if (we) mem[wa] <= wd; q <= mem[ra];`. Families split on how
// much of that template's port plumbing their block RAM macro can absorb:
// 7-series folds the whole read port into RAMB36E1 (DOA_REG), while ice40's
// SB_RAM40_4K has no output register, so the same RTL keeps flip-flops
// outside the macro. Measured 2026-09-29 under yosys 0.67+post: this probe
// alone is 138 SB_DFF + 4 SB_RAM40_4K on ice40 and one RAMB36E1 with no
// flip-flops on xilinx — exactly the 138-register spread the full node showed
// between those two families. A design carrying this RAM therefore cannot
// ask ten families for one identical flip-flop count, and the check that
// asserts agreement subtracts this probe's per-family count before
// comparing: every register NOT behind the RAM interface must still agree
// everywhere.
//
// The template is the node's, shape for shape (width 64, depth 256, one
// write port, zero initial contents). If the node's RAM changes shape,
// change this twin with it, or the subtraction stops being honest.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_ram_probe #(
    parameter integer DATA_W = 64,
    parameter integer DEPTH  = 256,
    parameter integer ADDR_W = 8
) (
    input  wire              clk,
    input  wire              we,
    input  wire [ADDR_W-1:0] wa,
    input  wire [DATA_W-1:0] wd,
    input  wire [ADDR_W-1:0] ra,
    output reg  [DATA_W-1:0] q
);
    reg [DATA_W-1:0] mem [0:DEPTH-1];
    integer i;
    initial begin
        for (i = 0; i < DEPTH; i = i + 1) mem[i] = {DATA_W{1'b0}};
    end
    always @(posedge clk) begin
        if (we) mem[wa] <= wd;
        q <= mem[ra];
    end
endmodule
`default_nettype wire
