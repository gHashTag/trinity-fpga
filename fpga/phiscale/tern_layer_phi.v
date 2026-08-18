// A whole ternary layer, scale included: fan-in N, one output element.
//
// Every earlier file here measured a PIECE -- the neuron (tern_node.v) or the
// scale applier (scale_phi.v) -- and the number asked from outside is the
// layer. This is that layer, so the two arms can be compared as deployables
// rather than as fragments.
//
// Arm A. Weights in {-phi, 0, +phi}, accumulator in Z[phi], layer scale phi^k
// applied by iterating the Fibonacci step. Nothing multiplies and nothing
// rounds: the pair IS the value.
`default_nettype none
module tern_layer_phi #(
    parameter integer N   = 16,
    parameter integer W   = 8,
    parameter integer ACC = 24,
    parameter integer KW  = 5
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [N*W-1:0]   x,
    input  wire        [2*N-1:0]   w,
    input  wire        [KW-1:0]    k,
    output wire signed [ACC-1:0]   y_a,
    output wire signed [ACC-1:0]   y_b,
    output wire                    done
);
    wire signed [ACC-1:0] acc_a, acc_b;
    tern_node #(.N(N), .W(W), .ACC(ACC)) u_mac (
        .clk(clk), .x(x), .w(w), .acc_a(acc_a), .acc_b(acc_b));

    // No pipeline register between the MAC and the scaler, and that is a
    // measured statement rather than an omission.
    //
    // tern_node registers its accumulator, so I expected scale_phi -- which
    // latches acc_* on `start` -- to see the previous sample and inserted a
    // one-cycle delay here. It is not needed: with the delay removed the layer
    // still passes 60 of 60 against an independent golden model.
    //
    // What had actually gone wrong was my testbench, which drove stimulus on
    // the POSEDGE and so raced the flops sampling it. scale_phi_tb.v in this
    // directory drives on the negedge and passes 200 of 200. Two conclusions I
    // drew from that harness -- "the blocks do not compose" and "scale_phi
    // never fires" -- were both false, and both were mine.
    scale_phi #(.ACC(ACC), .KW(KW)) u_scale (
        .clk(clk), .rst(rst), .start(start),
        .acc_a(acc_a), .acc_b(acc_b), .k(k),
        .out_a(y_a), .out_b(y_b), .done(done));
endmodule
