// One multiply-accumulate lane -- the denominator.
//
// A decoder's LUT count in isolation says nothing about whether it matters. What
// matters is the decode cost as a fraction of the unit it feeds, so this is the
// unit: a signed weight of WW bits times a signed AW-bit activation, accumulated
// into ACC bits.
//
// ACC is deliberately the SAME for both formats. It is then a constant in area
// -- which is what the fraction needs -- but a shared block on the critical path
// is a confound in DELAY, not a constant (DECODER_ISOLATED_2026-08-10.md). Read
// the lane rows for area and treat their Fmax accordingly.
`default_nettype none
module mac_lane #(
    parameter integer WW  = 5,    // signed decoded-weight width
    parameter integer AW  = 8,    // signed activation width
    parameter integer ACC = 32
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire signed [WW-1:0]     w,
    input  wire signed [AW-1:0]     a,
    output reg  signed [ACC-1:0]    acc
);
    wire signed [WW+AW-1:0] p = w * a;
    always @(posedge clk)
        acc <= !rst_n ? {ACC{1'b0}}
                      : acc + {{(ACC-WW-AW){p[WW+AW-1]}}, p};
endmodule
`default_nettype wire
