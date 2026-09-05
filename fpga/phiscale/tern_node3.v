// The folded ternary neuron with one pipeline register inside the adder tree.
//
// The unpipelined version costs 28 LUT per weight at fan-in 8 and closes at
// 87.29 MHz. The critical path is the whole tree: log2(N) levels of ACC-bit
// addition in one cycle. Cutting it once, at the halfway level, should trade a
// cycle of latency and N/2 registers for roughly twice the frequency -- which is
// the standard trade and worth measuring rather than assuming.
//
// Weight encoding, two bits: bit0 = active, bit1 = negative.
`default_nettype none
module tern_node3 #(
    parameter integer N   = 8,
    parameter integer W   = 8,
    parameter integer ACC = 16
)(
    input  wire                    clk,
    input  wire signed [N*W-1:0]   x,
    input  wire        [2*N-1:0]   w,
    output reg  signed [ACC-1:0]   acc_a,
    output reg  signed [ACC-1:0]   acc_b
);
    wire signed [ACC-1:0] cb  [0:N-1];
    wire                  cin [0:N-1];
    genvar i, k;
    generate
      for (i = 0; i < N; i = i + 1) begin : lane
        wire signed [W-1:0]   xi = x[i*W +: W];
        wire        [1:0]     wi = w[i*2 +: 2];
        wire signed [ACC-1:0] xe = {{(ACC-W){xi[W-1]}}, xi};
        assign cb[i]  = wi[0] ? (xe ^ {ACC{wi[1]}}) : {ACC{1'b0}};
        assign cin[i] = wi[0] & wi[1];
      end
    endgenerate

    // level 1: N/2 partial sums, registered -- this is the cut
    localparam integer H = N/2;
    reg signed [ACC-1:0] p [0:H-1];
    reg [$clog2(N+1)-1:0] pc [0:H-1];
    integer j;
    always @(posedge clk) begin
        for (j = 0; j < H; j = j + 1) begin
            p[j]  <= cb[2*j] + cb[2*j+1];
            pc[j] <= cin[2*j] + cin[2*j+1];
        end
    end

    // level 2 onward: combinational tree over the registered partials
    wire signed [ACC-1:0]        tr [0:2*H-2];
    wire [$clog2(N+1)-1:0]       tc [0:2*H-2];
    generate
      for (k = 0; k < H; k = k + 1) begin : t0
        assign tr[k] = p[k]; assign tc[k] = pc[k];
      end
      for (k = 0; k < H-1; k = k + 1) begin : tn
        assign tr[H+k] = tr[2*k] + tr[2*k+1];
        assign tc[H+k] = tc[2*k] + tc[2*k+1];
      end
    endgenerate

    always @(posedge clk) begin
        acc_a <= {ACC{1'b0}};
        acc_b <= tr[2*H-2] + {{(ACC-$clog2(N+1)){1'b0}}, tc[2*H-2]};
    end
endmodule
