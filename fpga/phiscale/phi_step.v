// One Fibonacci step, bare combinational logic -- the matched counterpart to
// apot_requant, which is also bare. Comparing the iterative controller against
// a combinational requantiser would repeat tonight's error in our own favour's
// opposite direction: an unmatched comparison is wrong whichever way it points.
module phi_step #(parameter integer W = 32)(
    input  wire                clk,
    input  wire                dir,        // 0 = multiply by phi, 1 = divide
    input  wire signed [W-1:0] a, b,
    output reg  signed [W-1:0] oa, ob
);
    always @(posedge clk) begin
        if (dir) begin oa <= b - a; ob <= a;     end
        else     begin oa <= b;     ob <= a + b; end
    end
endmodule
