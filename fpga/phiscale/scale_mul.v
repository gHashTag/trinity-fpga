// Arm A -- the scale applier BitNet's layout requires.
//
// The layer scale alpha = mean|W| is a real number, so applying it to an
// accumulator is a genuine multiply.  Ternary weights removed the multiplier
// from the inner product; this puts one back at the layer boundary, once per
// output element.
//
// Q1.15 unsigned scale against a 32-bit signed accumulator.
module scale_mul #(
    parameter integer ACC = 32,
    parameter integer AW  = 16          // alpha in Q1.15
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   acc,
    input  wire        [AW-1:0]    alpha,
    output reg  signed [ACC-1:0]   out,
    output reg                     done
);
    wire signed [ACC+AW-1:0] prod = $signed(acc) * $signed({1'b0, alpha});
    always @(posedge clk) begin
        if (rst) begin out <= 0; done <= 1'b0; end
        else begin
            done <= start;
            if (start) out <= prod[ACC+AW-2 -: ACC];   // >> 15, keep ACC bits
        end
    end
endmodule
