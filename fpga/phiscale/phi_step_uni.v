// One Fibonacci step, forward only -- the matched counterpart to plastic_step,
// which has no direction mux either. Comparing the bidirectional phi_step
// against a unidirectional plastic_step would charge phi for a feature the
// other does not have.
`default_nettype none
module phi_step_uni #(parameter integer W = 32)(
    input  wire                clk,
    input  wire signed [W-1:0] a, b,
    output reg  signed [W-1:0] oa, ob
);
    always @(posedge clk) begin oa <= b; ob <= a + b; end
endmodule
