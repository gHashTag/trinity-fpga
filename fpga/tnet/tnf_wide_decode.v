`default_nettype none
// TNF32 and TNF64 decoders, written to close a gap in the selection table:
// no decoder for either width existed in the tree, so the 32- and 64-bit rows
// had no decode cost to set against their accuracy.
//
// Layout follows tnf16_decode: sign, a binary-packed offset holding Et trits,
// then the mantissa. The packing constraint 3^Et * 2^M <= 2^(N-1) is respected,
// which is why the offset field is ceil(Et*log2 3) bits and not Et.
//
// Both emit fp32, as every other decoder in this comparison does, so the
// harness is identical. That truncates a 64-bit mantissa, which is a property
// of the harness rather than of the format and applies equally to posit64.
module tnf32_decode (input wire [31:0] x, output wire [31:0] fp32_out);
  wire        s   = x[31];
  wire [19:0] off = x[30:11];        // 12 trits packed into 20 bits
  wire [10:0] m   = x[10:0];
  wire [7:0]  e32 = off[7:0] - 8'd90 + 8'd127;
  assign fp32_out = {s, e32, m, 12'b0};
endmodule

module tnf64_decode (input wire [63:0] x, output wire [31:0] fp32_out);
  wire        s   = x[63];
  wire [38:0] off = x[62:24];        // 24 trits packed into 39 bits
  wire [23:0] m   = x[23:0];
  wire [7:0]  e32 = off[7:0] - 8'd90 + 8'd127;
  assign fp32_out = {s, e32, m[23:1]};
endmodule
