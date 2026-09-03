// Arm B -- the same layer with the scale a real multiplier does.
//
// Weights are still ternary, so the inner product is still a select-and-add
// tree and costs the same in both arms. The difference is the layer scale:
// here alpha is a Q1.15 constant and the accumulator is multiplied by it, which
// is what a BitNet-style deployment does today.
//
// The output is a single scalar rather than a pair, so this arm carries fewer
// registers by construction. That is stated rather than hidden: the comparison
// is scale-path area against scale-path area, with the same MAC in front.
`default_nettype none
module tern_layer_mul #(
    parameter integer N   = 16,
    parameter integer W   = 8,
    parameter integer ACC = 24
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [N*W-1:0]   x,
    input  wire        [2*N-1:0]   w,
    input  wire signed [15:0]      alpha,      // Q1.15
    output reg  signed [ACC-1:0]   y,
    output reg                     done
);
    wire signed [ACC-1:0] acc_a, acc_b;
    tern_node #(.N(N), .W(W), .ACC(ACC)) u_mac (
        .clk(clk), .x(x), .w(w), .acc_a(acc_a), .acc_b(acc_b));

    // The b component carries the ternary sum; a is zero by construction here,
    // which is the same signal the phi arm scales.
    wire signed [ACC+15:0] prod = acc_b * alpha;
    always @(posedge clk) begin
        if (rst) begin y <= 0; done <= 1'b0; end
        else begin
            y <= prod[ACC+15:15];
            done <= start;
        end
    end
endmodule
