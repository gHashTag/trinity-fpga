// One step of the multiply-free scale r^8 = r + 1.
//
// The family r^d = r + 1 has exactly two non-zero coefficients at every
// degree, so its companion map is ONE addition and d shifts regardless of d:
//   (x0..x7) -> (x7, x0+x7, x1, ..., x6)
//
// Fineness therefore costs registers, not adders. The roots converge to
// 2^(1/d) from above, so any granularity a logarithmic subdivision offers is
// reachable here without a multiplier.
`default_nettype none
module rpow8_step #(parameter integer W = 32)(
    input  wire clk,
    input  wire signed [W-1:0] x0, x1, x2, x3, x4, x5, x6, x7,
    output reg  signed [W-1:0] o0, o1, o2, o3, o4, o5, o6, o7
);
    always @(posedge clk) begin
        o0 <= x7;
        o1 <= x0 + x7;
        o2 <= x1;
        o3 <= x2;
        o4 <= x3;
        o5 <= x4;
        o6 <= x5;
        o7 <= x6;
    end
endmodule
