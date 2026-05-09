// GF(2^4) Multiplication — LUT-based, polynomial x^4 + x + 1 (0x13)
// NO DSP48 — abc9 routing issue workaround (see COMMON_PITFALLS.md)
// L-DPC1 verified on XC7A100T (2026-05-10)
`timescale 1ns/1ps

module gf16_mul (
    input  [3:0] a,
    input  [3:0] b,
    output [3:0] product
);
    // Primitive polynomial: x^4 + x + 1
    // Reduction: if bit 4 set, XOR with 0x3 (x+1)
    wire [6:0] raw;
    wire [3:0] p;

    // Schoolbook multiplication in GF(2)[x] mod (x^4 + x + 1)
    assign raw[0] = a[0] & b[0];
    assign raw[1] = (a[1] & b[0]) ^ (a[0] & b[1]);
    assign raw[2] = (a[2] & b[0]) ^ (a[1] & b[1]) ^ (a[0] & b[2]);
    assign raw[3] = (a[3] & b[0]) ^ (a[2] & b[1]) ^ (a[1] & b[2]) ^ (a[0] & b[3]);
    assign raw[4] = (a[3] & b[1]) ^ (a[2] & b[2]) ^ (a[1] & b[3]);
    assign raw[5] = (a[3] & b[2]) ^ (a[2] & b[3]);
    assign raw[6] = a[3] & b[3];

    // Reduce mod x^4 + x + 1:
    // x^4 = x + 1  => bit4 -> bit1, bit0
    // x^5 = x^2 + x
    // x^6 = x^3 + x^2
    assign product[0] = raw[0] ^ raw[4];
    assign product[1] = raw[1] ^ raw[4] ^ raw[5];
    assign product[2] = raw[2] ^ raw[5] ^ raw[6];
    assign product[3] = raw[3] ^ raw[6];

endmodule
