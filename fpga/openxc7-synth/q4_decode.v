`default_nettype none
`timescale 1ns / 1ps
// q4_decode — Q4 fixed-point (4-bit, 4 fractional bits, signed) → FP32.
// Value = signed_4bit / 16. Range: [-0.5, +0.4375].
module q4_decode (
    input  wire [3:0] q4_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    assign is_zero = (q4_in == 4'd0);

    wire signed [3:0] val = q4_in;
    wire        neg  = val[3];
    wire [3:0]  abs  = neg ? (~q4_in + 4'd1) : q4_in;

    // abs * 2^(-4) → FP32. Since abs ≤ 8, exp is small.
    // Find leading bit of 4-bit abs to normalize.
    reg [1:0] lzc;
    always @(*) begin
        casez (abs)
            4'b1???: lzc = 2'd0;
            4'b01??: lzc = 2'd1;
            4'b001?: lzc = 2'd2;
            default: lzc = 2'd3;
        endcase
    end

    wire [3:0] norm  = abs << lzc;
    wire [2:0] mant  = norm[2:0];
    // Was `wire [3:0] exp_r = 4'd123 - {2'b0, lzc}`: two defects in one line.
    // 123 does not fit four bits and truncated to 11, and the use below reads
    // exp_r[7:0] from a four-bit wire, so the top half of the fp32 exponent was
    // constant zero. Both are silent; iverilog reported the first.
    wire [7:0] exp_r = 8'd123 - {6'b0, lzc};  // 127 - 4 - lzc

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else
            fp32_out = {neg, exp_r[7:0], mant, 20'b0};
    end
endmodule
`default_nettype wire
