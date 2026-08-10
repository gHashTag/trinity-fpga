// One step of the multiply-free scale r^5 = r + 1.
//
// The family r^d = r + 1 has exactly two non-zero coefficients at every
// degree, so its companion map is ONE addition and d shifts regardless of d:
//   (x0..x4) -> (x4, x0+x4, x1, ..., x3)
//
// Fineness therefore costs registers, not adders. The roots converge to
// 2^(1/d) from above, so any granularity a logarithmic subdivision offers is
// reachable here without a multiplier.
`default_nettype none
module rpow5_step #(parameter integer W = 32)(
    input  wire clk,
    input  wire signed [W-1:0] x0, x1, x2, x3, x4,
    output reg  signed [W-1:0] o0, o1, o2, o3, o4
);
    always @(posedge clk) begin
        o0 <= x4;
        o1 <= x0 + x4;
        o2 <= x1;
        o3 <= x2;
        o4 <= x3;
    end
endmodule
