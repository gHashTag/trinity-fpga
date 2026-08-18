// gft_mul_exact — GFTernary product, exact, with no multiplier and no phi.
//
// The theorem: every digit is phi*t with t in {-1,0,+1}, so a product is
// phi^2 * (t*u). phi^2 is a constant scale on the whole result and never
// interacts with the data, so the only work left is the sign product of two
// balanced-ternary digits. That is combinational logic on four bits.
//
// Codes: 00 = 0, 01 = +, 10 = -, 11 = reserved (= +, matching the decoder).
module gft_mul_exact(input [1:0] a, input [1:0] b, output reg [1:0] y);
    wire a_zero = (a == 2'b00);
    wire b_zero = (b == 2'b00);
    wire a_neg  = (a == 2'b10);
    wire b_neg  = (b == 2'b10);
    always @(*) begin
        if (a_zero || b_zero) y = 2'b00;
        else                  y = (a_neg ^ b_neg) ? 2'b10 : 2'b01;
    end
endmodule
