// APoT requantisation at runtime -- what the mesh case actually forces.
//
// Composing scales without renormalisation grows APoT terms as n^(d+1). The
// answer an APoT designer would give is: requantise each hop back to two terms.
// Where the composition is compile-time that is free (precompute). Where the
// depth is a RUNTIME quantity -- a mesh route whose hop count is not known until
// the packet arrives -- it must happen in hardware.
//
// Requantising a value to 2^p +- 2^q at runtime means: find the leading one,
// subtract that power, find the leading one of the residue. Two priority
// encoders and a subtractor.
module apot_requant #(parameter integer W = 32, parameter integer SW = 6)(
    input  wire                clk,
    input  wire [W-1:0]        v,
    output reg  [SW-1:0]       p,
    output reg  [SW-1:0]       q,
    output reg                 sgn
);
    integer i;
    reg [SW-1:0] lead;
    reg [W-1:0]  res;
    reg [SW-1:0] lead2;
    always @(*) begin
        lead = 0;
        for (i = 0; i < W; i = i + 1) if (v[i]) lead = i[SW-1:0];
        res  = v - (1 << lead);
        lead2 = 0;
        for (i = 0; i < W; i = i + 1) if (res[i]) lead2 = i[SW-1:0];
    end
    always @(posedge clk) begin p <= lead; q <= lead2; sgn <= 1'b0; end
endmodule
