// One step of the degree-4 multiply-free ladder.
//
// r is the real root of r^4 = -r^3 + r^2 + r + 1 (r = 1.178724...), the
// smallest scale reachable at degree 4 with coefficients in {0,+-1} -- and
// smaller than 2^(1/4) = 1.189207, so the multiply-free ladder is finer here
// than the logarithmic subdivision at the same register count.
//
// Representing a value as x0 + x1 r + x2 r^2 + x3 r^3,
//   r*(x0 + x1 r + x2 r^2 + x3 r^3) = x3 + (x0+x3) r + (x1+x3) r^2 + (x2-x3) r^3
// so the map is (x0,x1,x2,x3) -> (x3, x0+x3, x1+x3, x2-x3): three add/subtracts
// and four registers, against phi's one addition and two. The jump in adder
// count between degree 3 and degree 4 is the price of the finer ladder.
`default_nettype none
module deg4_step #(parameter integer W = 32)(
    input  wire                clk,
    input  wire signed [W-1:0] x0, x1, x2, x3,
    output reg  signed [W-1:0] o0, o1, o2, o3
);
    always @(posedge clk) begin
        o0 <= x3;
        o1 <= x0 + x3;
        o2 <= x1 + x3;
        o3 <= x2 - x3;
    end
endmodule
