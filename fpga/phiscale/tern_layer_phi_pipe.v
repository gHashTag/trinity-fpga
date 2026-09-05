// The ternary layer with the cycles taken back.
//
// tern_layer_phi.v applies the layer scale by iterating the Fibonacci step k
// times: smallest, highest clock, and 2.15x SLOWER per output element than the
// multiplier at the |k| = 8 a deployed layer needs (FMAX.md). This is the same
// layer with the pipelined scale: one element per cycle, latency K_MAX, and
// still no multiplier anywhere.
`default_nettype none
module tern_layer_phi_pipe #(
    parameter integer N     = 8,
    parameter integer W     = 8,
    parameter integer ACC   = 16,
    parameter integer KW    = 4,
    parameter integer K_MAX = 8
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire signed [N*W-1:0]   x,
    input  wire        [2*N-1:0]   w,
    input  wire        [KW-1:0]    k,
    output wire signed [ACC-1:0]   y_a,
    output wire signed [ACC-1:0]   y_b,
    output wire                    out_valid
);
    wire signed [ACC-1:0] acc_a, acc_b;
    tern_node #(.N(N), .W(W), .ACC(ACC)) u_mac (
        .clk(clk), .x(x), .w(w), .acc_a(acc_a), .acc_b(acc_b));

    scale_phi_pipe #(.ACC(ACC), .KW(KW), .K_MAX(K_MAX)) u_scale (
        .clk(clk), .rst(rst), .in_valid(in_valid),
        .acc_a(acc_a), .acc_b(acc_b), .k(k),
        .out_a(y_a), .out_b(y_b), .out_valid(out_valid));
endmodule
