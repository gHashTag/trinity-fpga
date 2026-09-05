// One plastic-number step -- the degree-3 sibling of phi_step.
//
// rho is the real root of r^3 = r + 1 (rho = 1.3247...). Representing a value
// as a + b*rho + c*rho^2, multiplication by rho is
//   rho(a + b rho + c rho^2) = a rho + b rho^2 + c(rho + 1) = c + (a+c) rho + b rho^2
// so the map is (a,b,c) -> (c, a+c, b): ONE addition, as with phi, but three
// integer components instead of two.
//
// The point of measuring it is that it is NOT obviously worse than phi. Its
// scale ladder is finer -- successive levels differ by 1.3247 against phi's
// 1.618 -- so it buys granularity for a register. Whether that is worth it is a
// question about the network, not about the arithmetic.
`default_nettype none
module plastic_step #(parameter integer W = 32)(
    input  wire                clk,
    input  wire signed [W-1:0] a, b, c,
    output reg  signed [W-1:0] oa, ob, oc
);
    always @(posedge clk) begin
        oa <= c;
        ob <= a + c;
        oc <= b;
    end
endmodule
