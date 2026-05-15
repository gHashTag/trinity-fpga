// GF(2^4) Addition — bitwise XOR
// L-DPC1 verified on XC7A100T (2026-05-10)
`timescale 1ns/1ps

module gf16_add (
    input  [3:0] a,
    input  [3:0] b,
    output [3:0] sum
);
    // GF(2^4) addition is bitwise XOR
    assign sum = a ^ b;

endmodule
