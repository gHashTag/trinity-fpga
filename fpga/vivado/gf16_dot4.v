// GF(2^4) Dot Product — 4 elements, phi-constant weights
// weights = [phi0, phi1, phi2, phi3] — configured via parameters
// Default weights = 4'h1 each (identity test for L-DPC1)
// L-DPC1 verified on XC7A100T (2026-05-10)
`timescale 1ns/1ps

module gf16_dot4 #(
    parameter [3:0] W0 = 4'h1,  // phi-constant weight 0
    parameter [3:0] W1 = 4'h2,  // phi-constant weight 1
    parameter [3:0] W2 = 4'h4,  // phi-constant weight 2
    parameter [3:0] W3 = 4'h8   // phi-constant weight 3
) (
    input  [3:0] x0,
    input  [3:0] x1,
    input  [3:0] x2,
    input  [3:0] x3,
    output [3:0] dot
);
    wire [3:0] p0, p1, p2, p3;
    wire [3:0] s01, s23;

    gf16_mul u_mul0 (.a(x0), .b(W0), .product(p0));
    gf16_mul u_mul1 (.a(x1), .b(W1), .product(p1));
    gf16_mul u_mul2 (.a(x2), .b(W2), .product(p2));
    gf16_mul u_mul3 (.a(x3), .b(W3), .product(p3));

    gf16_add u_add01 (.a(p0), .b(p1), .sum(s01));
    gf16_add u_add23 (.a(p2), .b(p3), .sum(s23));
    gf16_add u_add_final (.a(s01), .b(s23), .sum(dot));

endmodule
