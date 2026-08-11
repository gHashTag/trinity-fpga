`default_nettype none
// Two candidate 16-bit rungs of the TNF ladder, built so the catalogue has a
// width class where one of our formats meets binary16, takum16, LNS16 and
// posit16 at exactly equal storage. Until now our nearest rung was 17 bits and
// every same-width comparison in the paper carried a one-bit apology.
//
// A rung's stored width is 1 + ceil(E_t log2 3) + M. Two assignments hit 16:
//   A  E_t=4 -> 7 offset bits (81 offsets), M=8   -- wide range, coarse steps
//   B  E_t=3 -> 5 offset bits (27 offsets), M=10  -- narrow range, fine steps
// Which is the 16-bit member is a measurement, not a preference.

// tnf16a: E_t=4 (7 bits, 81 ternary offsets), M=8, stored width 16
// Dynamic range 2^-39 .. 2^39. Rung chosen to fill exactly 16 bits.
module tnf16a_decode (input wire [15:0] x, output wire [31:0] fp32_out);
  wire        s   = x[15];
  wire [6:0] off = x[14:8];
  wire [7:0] m   = x[7:0];
  wire signed [10:0] e = $signed({1'b0, off}) - 11'sd40;
  wire [7:0] e32 = e[7:0] + 8'd127;
  wire is_zero = (off == 7'd0);
  wire is_spec = (off == 7'd80);
  wire [22:0] mant23 = {m, 15'b0};
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, mant23};
endmodule

// tnf16b: E_t=3 (5 bits, 27 ternary offsets), M=10, stored width 16
// Dynamic range 2^-12 .. 2^12. Rung chosen to fill exactly 16 bits.
module tnf16b_decode (input wire [15:0] x, output wire [31:0] fp32_out);
  wire        s   = x[15];
  wire [4:0] off = x[14:10];
  wire [9:0] m   = x[9:0];
  wire signed [10:0] e = $signed({1'b0, off}) - 11'sd13;
  wire [7:0] e32 = e[7:0] + 8'd127;
  wire is_zero = (off == 5'd0);
  wire is_spec = (off == 5'd26);
  wire [22:0] mant23 = {m, 13'b0};
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, mant23};
endmodule

// tnf16a_safe: rung A with its out-of-specification offsets reserved.
//
// Four trits name 81 offsets and the field holds 128, so offsets 81..127 are
// outside the format. The unguarded decoder gives each of them a distinct
// finite value, which means a corrupted offset field is indistinguishable from
// a valid one -- and no conformance test can find that, because a decoder that
// answers every input answers every test. Here they signal NaN.
module tnf16a_safe_decode (input wire [15:0] x, output wire [31:0] fp32_out,
                           output wire invalid);
  wire       s   = x[15];
  wire [6:0] off = x[14:8];
  wire [7:0] m   = x[7:0];
  wire signed [10:0] e = $signed({1'b0, off}) - 11'sd40;
  wire [7:0] e32 = e[7:0] + 8'd127;
  wire is_zero = (off == 7'd0);
  wire is_spec = (off == 7'd80);
  assign invalid = (off > 7'd80);
  assign fp32_out = invalid  ? {1'b0, 8'hFF, 1'b1, 22'b0}   // reserved -> qNaN
                  : is_spec  ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero  ? {s, 31'b0}
                  :            {s, e32, {m, 15'b0}};
endmodule

// tnf16c: E_t=5 -> 243 offsets in an 8-bit field, M=7, stored width 16.
//
// 3^k = 2^m has no solution for k,m >= 1, so a ternary exponent never fills a
// binary field exactly and every rung wastes 1 - 3^k/2^ceil(k log2 3). That
// waste is wildly uneven in k: E_t=4 wastes 36.7% and E_t=5 wastes 5.08%. Rung
// A sits on the bad one. This sits on the good one, and its guard therefore
// covers 13 offsets instead of 47.
//
// Both variants are here: unguarded, and with the 13 out-of-specification
// offsets reserved, so the reservation cost can be measured rather than argued.
module tnf16c_decode (input wire [15:0] x, output wire [31:0] fp32_out);
  wire       s   = x[15];
  wire [7:0] off = x[14:7];
  wire [6:0] m   = x[6:0];
  wire signed [10:0] e = $signed({1'b0, off}) - 11'sd121;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign fp32_out = (off == 8'd242) ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 8'd0)   ? {s, 31'b0}
                  :                   {s, e32, {m, 16'b0}};
endmodule

module tnf16c_safe_decode (input wire [15:0] x, output wire [31:0] fp32_out,
                           output wire invalid);
  wire       s   = x[15];
  wire [7:0] off = x[14:7];
  wire [6:0] m   = x[6:0];
  wire signed [10:0] e = $signed({1'b0, off}) - 11'sd121;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign invalid = (off > 8'd242);
  assign fp32_out = invalid          ? {1'b0, 8'hFF, 1'b1, 22'b0}
                  : (off == 8'd242)  ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 8'd0)    ? {s, 31'b0}
                  :                    {s, e32, {m, 16'b0}};
endmodule

`default_nettype wire
