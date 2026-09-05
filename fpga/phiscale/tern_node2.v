// The same ternary neuron with the negation folded into the tree.
//
// The first version computed -x per lane as a full two's complement, so every
// negative weight paid a 16-bit inverter and an increment that the tree could
// have absorbed. Two's complement is (~x) + 1, and the +1 of every lane is a
// single bit: XOR the sample with the weight's sign, sum the signs separately,
// and add that count once at the root.
//
// Weight encoding, two bits: bit0 = active, bit1 = negative.
`default_nettype none
module tern_node2 #(
    parameter integer N   = 16,
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
        wire signed [W-1:0] xi  = x[i*W +: W];
        wire        [1:0]   wi  = w[i*2 +: 2];
        wire signed [ACC-1:0] xe = {{(ACC-W){xi[W-1]}}, xi};
        // active ? (negative ? ~xe : xe) : 0   -- an XOR, not a subtract
        assign cb[i]  = wi[0] ? (xe ^ {ACC{wi[1]}}) : {ACC{1'b0}};
        assign cin[i] = wi[0] & wi[1];          // the +1 that completes ~x
      end
    endgenerate
    // balanced tree over the terms
    wire signed [ACC-1:0] tr [0:2*N-2];
    generate
      for (k = 0; k < N; k = k + 1)   begin : t0 assign tr[k] = cb[k]; end
      for (k = 0; k < N-1; k = k + 1) begin : tn assign tr[N+k] = tr[2*k] + tr[2*k+1]; end
    endgenerate
    // the carry-ins summed once, at the root
    wire [$clog2(N+1)-1:0] cs [0:2*N-2];
    generate
      for (k = 0; k < N; k = k + 1)   begin : c0 assign cs[k] = cin[k]; end
      for (k = 0; k < N-1; k = k + 1) begin : cn assign cs[N+k] = cs[2*k] + cs[2*k+1]; end
    endgenerate
    always @(posedge clk) begin
        acc_a <= {ACC{1'b0}};
        acc_b <= tr[2*N-2] + {{(ACC-$clog2(N+1)){1'b0}}, cs[2*N-2]};
    end
endmodule
