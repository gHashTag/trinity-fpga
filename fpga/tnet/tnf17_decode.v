`default_nettype none
// TNF16 at its specified width.
//
// The sixteen-bit module this replaces put the sign at bit 15 and gave the
// mantissa eight bits, and every one of its 65,536 codes disagreed with the
// reference. The reference is 1 sign + 7 offset + 9 mantissa = 17 bits, which
// is also the width the paper derives for a trit-carrying exponent stored as a
// plain binary integer. The sixteen-bit module was the divergence, not the
// reference.
//
//   offset == 0        -> zero
//   offset == 80       -> Inf (mantissa 0) or NaN
//   otherwise          -> (1 + m/512) * 2^(offset - 40)
//
// fp32 exponent is (offset - 40) + 127 = offset + 87.
module tnf17_decode (input wire [16:0] x, output wire [31:0] fp32_out);
  wire       s   = x[16];
  wire [6:0] off = x[15:9];
  wire [8:0] m   = x[8:0];
  wire [7:0] e32 = {1'b0, off} + 8'd87;
  wire is_zero = (off == 7'd0);
  wire is_spec = (off == 7'd80);
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, m, 14'b0};
endmodule
