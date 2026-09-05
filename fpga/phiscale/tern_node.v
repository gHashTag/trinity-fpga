// A complete ternary neuron: fan-in N, weights from {-phi, 0, +phi}, accumulator
// in Z[phi]. This is the number that gets asked from outside -- LUTs per neuron --
// and every part of this work so far measured a piece of it instead.
//
// The weight alphabet is two bits per weight: 00 = zero, 01 = +phi, 11 = -phi.
// Applying +phi to a Z[phi] value (a,b) is the Fibonacci step (b, a+b); applying
// it to a plain integer sample x, taken as the coordinate pair (x,0), gives
// (0,x). So a weight application is a select between (0,x), (0,-x) and (0,0) --
// no arithmetic at all -- and the whole neuron is the accumulation tree.
//
// That is the closure result in hardware: the multiply is a select because the
// product never leaves the lattice the adder tree already works in.
`default_nettype none
module tern_node #(
    parameter integer N   = 16,   // fan-in
    parameter integer W   = 8,    // sample width
    parameter integer ACC = 16    // accumulator component width
)(
    input  wire                    clk,
    input  wire signed [N*W-1:0]   x,     // N samples, ADC-native
    input  wire        [2*N-1:0]   w,     // N weights, 2 bits each
    output reg  signed [ACC-1:0]   acc_a, // accumulator, Z[phi] coordinate a
    output reg  signed [ACC-1:0]   acc_b  //                          and b
);
    // per-weight contribution: (0, +x), (0, -x) or (0, 0)
    wire signed [ACC-1:0] cb [0:N-1];
    genvar i;
    generate
      for (i = 0; i < N; i = i + 1) begin : lane
        wire signed [W-1:0] xi = x[i*W +: W];
        wire [1:0] wi = w[i*2 +: 2];
        assign cb[i] = wi[0] ? (wi[1] ? -{{(ACC-W){xi[W-1]}}, xi}
                                      :  {{(ACC-W){xi[W-1]}}, xi})
                             : {ACC{1'b0}};
      end
    endgenerate
    // A genuine balanced tree. The first version of this file wrote
    //   for (j = 0; j < N; j = j + 1) sum = sum + cb[j];
    // under a comment claiming a balanced tree, and synthesised an N-deep ripple
    // chain: the depth, and therefore the frequency, was an artefact of the loop
    // and not of the format.
    wire signed [ACC-1:0] lvl [0:N-1];
    generate
      genvar s, k;
      for (k = 0; k < N; k = k + 1) begin : leaf
        assign lvl[k] = cb[k];
      end
    endgenerate
    function integer clog2(input integer v); integer r; begin
      r = 0; v = v - 1; while (v > 0) begin r = r + 1; v = v >> 1; end clog2 = r;
    end endfunction
    wire signed [ACC-1:0] tree [0:2*N-2];
    generate
      for (k = 0; k < N; k = k + 1) begin : t0
        assign tree[k] = cb[k];
      end
      for (k = 0; k < N-1; k = k + 1) begin : tn
        assign tree[N+k] = tree[2*k] + tree[2*k+1];
      end
    endgenerate
    wire signed [ACC-1:0] sum = tree[2*N-2];
    always @(posedge clk) begin
        acc_a <= {ACC{1'b0}};
        acc_b <= sum;
    end
endmodule
