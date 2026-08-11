`default_nettype none
// fp8 e4m3 and e5m2 with the subnormal path the measured modules omitted.
//
// The modules in the throughput table read the exponent field and mapped a zero
// exponent to a zero fp32 exponent, placing the mantissa as if normal. That
// makes every subnormal decode to a denormal fp32 instead of its value: 14 of
// 256 codes wrong for e4m3, 6 for e5m2, exactly the subnormal range. An
// unimplemented case is unsynthesised logic, so the omission made the module
// smaller than a complete one -- the comparison flattered the competitor, and
// this removes that.
//
// A subnormal is (m / 2^M) * 2^(1-bias). Normalising it for fp32 means finding
// the leading one of m and shifting.
module fp8_e4m3_full (input wire [7:0] x, output wire [31:0] fp32_out);
  wire       s = x[7];
  wire [3:0] e = x[6:3];
  wire [2:0] m = x[2:0];
  // leading-one position of a 3-bit mantissa
  wire [1:0] lz = m[2] ? 2'd0 : m[1] ? 2'd1 : 2'd2;
  wire [2:0] msh = m << lz;                 // normalised, msb set
  // subnormal value = m * 2^(1-7-3) = m * 2^-9; after normalising by lz the
  // exponent is (1-7) - lz = -6 - lz, and fp32 bias is 127
  wire [7:0] e_sub = 8'd127 - 8'd7 - {6'b0, lz};   // (1+frac)*2^(-7-lz)
  wire [7:0] e_nrm = {4'b0, e} - 8'd7 + 8'd127;
  wire is_zero = (e == 4'd0) && (m == 3'd0);
  wire is_sub  = (e == 4'd0) && (m != 3'd0);
  assign fp32_out = is_zero ? {s, 31'b0}
                  : is_sub  ? {s, e_sub, msh[1:0], 21'b0}
                  :           {s, e_nrm, m, 20'b0};
endmodule
module fp8_e5m2_full (input wire [7:0] x, output wire [31:0] fp32_out);
  wire       s = x[7];
  wire [4:0] e = x[6:2];
  wire [1:0] m = x[1:0];
  wire       lz = ~m[1];
  wire [1:0] msh = m << lz;
  wire [7:0] e_sub = 8'd127 - 8'd15 - {7'b0, lz};  // (1+frac)*2^(-15-lz)
  wire [7:0] e_nrm = {3'b0, e} - 8'd15 + 8'd127;
  wire is_zero = (e == 5'd0) && (m == 2'd0);
  wire is_sub  = (e == 5'd0) && (m != 2'd0);
  assign fp32_out = is_zero ? {s, 31'b0}
                  : is_sub  ? {s, e_sub, msh[0], 22'b0}
                  :           {s, e_nrm, m, 21'b0};
endmodule
