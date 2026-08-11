`default_nettype none
// TNF32 and TNF64 at the parameters their specification gives.
//
// The modules these replace implemented different formats: the spec gives
// TNF32 six trits and 25 mantissa bits, the module had twelve and eleven;
// TNF64 is 7 and 52 against 24 and 24. Both held ranks three and four of
// the throughput table on those numbers, and neither had a reference, which
// is why the divergence survived.
//
// A rung's width is its position count 1 + E_t + M. On a binary fabric the
// offset costs ceil(E_t log2 3) bits, so the stored word is wider than the
// name: 36 bits for TNF32, 65 for TNF64.

// tnf32s: E_t=6 (10 bits), M=25, stored width 36
module tnf32s_decode (input wire [35:0] x, output wire [31:0] fp32_out);
  wire        s   = x[35];
  wire [9:0] off = x[34:25];
  wire [24:0] m   = x[24:0];
  wire signed [11:0] e = $signed({1'b0, off}) - 12'sd364;
  wire [7:0] e32 = e[7:0] + 8'd127;   // fp32 window; wider rungs clip
  wire is_zero = (off == 10'd0);
  wire is_spec = (off == 10'd728);
  wire [22:0] mant23 = m[24:2];
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, mant23};
endmodule

// tnf64s: E_t=7 (12 bits), M=52, stored width 65
module tnf64s_decode (input wire [64:0] x, output wire [31:0] fp32_out);
  wire        s   = x[64];
  wire [11:0] off = x[63:52];
  wire [51:0] m   = x[51:0];
  wire signed [13:0] e = $signed({1'b0, off}) - 14'sd1093;
  wire [7:0] e32 = e[7:0] + 8'd127;   // fp32 window; wider rungs clip
  wire is_zero = (off == 12'd0);
  wire is_spec = (off == 12'd2186);
  wire [22:0] mant23 = m[51:29];
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, mant23};
endmodule
// tnf8s: E_t=3 (5 bits), M=4, stored width 10
module tnf8s_decode (input wire [9:0] x, output wire [31:0] fp32_out);
  wire        s   = x[9];
  wire [4:0] off = x[8:4];
  wire [3:0] m   = x[3:0];
  wire signed [9:0] e = $signed({1'b0, off}) - 10'sd13;
  wire [7:0] e32 = e[7:0] + 8'd127;
  wire is_zero = (off == 5'd0);
  wire is_spec = (off == 5'd26);
  wire [22:0] mant23 = {m, 19'b0};
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, mant23};
endmodule
// bnf16s: the binary-exponent sibling of TNF16, at the same field widths.
// E = 7 bits, M = 9, stored width 17. The module this replaces was 16 bits with
// eight mantissa bits -- one short, exactly as TNF16's was.
module bnf16s_decode (input wire [16:0] x, output wire [31:0] fp32_out);
  wire       s = x[16];
  wire [6:0] e = x[15:9];
  wire [8:0] m = x[8:0];
  wire [7:0] e32 = {1'b0, e} - 8'd63 + 8'd127;
  wire is_zero = (e == 7'd0);
  wire is_spec = (e == 7'd127);
  assign fp32_out = is_spec ? {s, 8'hFF, (|m), 22'b0}
                  : is_zero ? {s, 31'b0}
                  :           {s, e32, m, 14'b0};
endmodule
