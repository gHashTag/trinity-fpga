// Addition in Z[phi]: componentwise, two adders, nothing else.
//
// This is the operation an LNS cannot do cheaply.  In a logarithmic number
// system multiplication is free (exponents add) but ADDITION needs
// log(1 + 2^x), i.e. a table.  Our own measurement of takum32_decode put that
// at 10,967 LUTs and 84 RAMB36 tiles.
//
// Z[phi] is closed cheaply under BOTH operations: multiplication by a power of
// phi is the Fibonacci step (one adder), and addition is componentwise (two
// adders).  The restriction is that multiplication is only free for powers of
// phi -- which in a ternary datapath is the only multiplication there is.
module zphi_add16 #(parameter integer ACC = 16)(
    input  wire                  clk,
    input  wire signed [ACC-1:0] a0, b0, a1, b1,
    output reg  signed [ACC-1:0] sa, sb
);
    always @(posedge clk) begin
        sa <= a0 + a1;
        sb <= b0 + b1;
    end
endmodule
