// Applying the shared E8M0 exponent, once per block.
//
// This is the piece that genuinely amortises. The block's 32 products are summed
// in the block's own integer scale; the shared exponent enters once, as an
// alignment shift of the finished block sum before it joins the layer
// accumulator. One barrel shifter per 32 elements, not per element.
//
// It depends only on E8M0 and not at all on the element table, so it is
// identical for E2M1 and for an arbitrary codebook and cancels out of the
// comparison. It is measured here so the amortisation denominator is a number
// rather than a claim.
`default_nettype none
module blk_scale #(
    parameter integer ACC = 32,
    parameter integer OUT = 40
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire signed [ACC-1:0]  blk,     // finished block sum, block scale
    input  wire        [7:0]      e8m0,    // shared exponent of this block
    input  wire        [7:0]      emax,    // layer alignment reference
    output reg  signed [OUT-1:0]  y
);
    wire [7:0] sh = emax - e8m0;                       // >= 0 by construction
    wire signed [OUT-1:0] wide = {{(OUT-ACC){blk[ACC-1]}}, blk};
    wire signed [OUT-1:0] al = wide >>> (sh[5:0]);     // 40-bit arithmetic barrel
    always @(posedge clk) y <= !rst_n ? {OUT{1'b0}} : (sh[7:6] != 2'b00 ? {OUT{blk[ACC-1]}} : al);
endmodule
`default_nettype wire
