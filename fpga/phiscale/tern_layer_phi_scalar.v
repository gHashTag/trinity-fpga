// The pipelined phi layer with a scalar output.
//
// The pair representation is what made the arithmetic exact and what needed 217
// pins on a 206-pin package at fan-in 16. This reconstructs one number at the
// boundary -- where a quantised layer requantises anyway -- so the layer fits
// at the fan-in it could not be measured at before.
`default_nettype none
module tern_layer_phi_scalar #(
    parameter integer N     = 16,
    parameter integer W     = 8,
    parameter integer ACC   = 16,
    parameter integer KW    = 4,
    parameter integer K_MAX = 8,
    parameter integer SH    = 4
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire signed [N*W-1:0]   x,
    input  wire        [2*N-1:0]   w,
    input  wire        [KW-1:0]    k,
    output wire signed [W-1:0]     y,
    output wire                    out_valid
);
    wire signed [ACC-1:0] acc_a, acc_b, sa, sb;
    wire sv;
    tern_node #(.N(N), .W(W), .ACC(ACC)) u_mac (
        .clk(clk), .x(x), .w(w), .acc_a(acc_a), .acc_b(acc_b));
    scale_phi_pipe #(.ACC(ACC), .KW(KW), .K_MAX(K_MAX)) u_scale (
        .clk(clk), .rst(rst), .in_valid(in_valid),
        .acc_a(acc_a), .acc_b(acc_b), .k(k),
        .out_a(sa), .out_b(sb), .out_valid(sv));
    zphi_to_scalar #(.ACC(ACC), .W(W), .SH(SH)) u_out (
        .clk(clk), .rst(rst), .in_valid(sv), .a(sa), .b(sb),
        .y(y), .out_valid(out_valid));
endmodule
