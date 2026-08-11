`default_nettype none
// Ladder rungs rebuilt on the low-waste k of Corollary (the good rungs).

// tnf17e: E_t=5 (8 bits, 243 of 256 used, waste 5.1%),
// M=8, stored width 17. Chosen by Corollary (the good rungs): least w(k)
// among the k whose range 3^k/2 covers the class. Out-of-specification offsets
// are reserved, so no code decodes to a plausible value it does not mean.
module tnf17e_decode (input wire [16:0] x, output wire [31:0] fp32_out,
                      output wire invalid);
  wire       s   = x[16];
  wire [7:0] off = x[15:8];
  wire [7:0] m   = x[7:0];
  wire signed [15:0] e = $signed({1'b0, off}) - 16'sd121;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign invalid = (off > 8'd242);
  assign fp32_out = invalid              ? {1'b0, 8'hFF, 1'b1, 22'b0}
                  : (off == 8'd242) ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 8'd0)      ? {s, 31'b0}
                  :                        {s, e32, {m[7:0], 15'b0}};
endmodule

// tnf64b: E_t=8 (13 bits, 6561 of 8192 used, waste 19.9%),
// M=51, stored width 65. Chosen by Corollary (the good rungs): least w(k)
// among the k whose range 3^k/2 covers the class. Out-of-specification offsets
// are reserved, so no code decodes to a plausible value it does not mean.
module tnf64b_decode (input wire [64:0] x, output wire [31:0] fp32_out,
                      output wire invalid);
  wire       s   = x[64];
  wire [12:0] off = x[63:51];
  wire [50:0] m   = x[50:0];
  wire signed [15:0] e = $signed({1'b0, off}) - 16'sd3280;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign invalid = (off > 13'd6560);
  assign fp32_out = invalid              ? {1'b0, 8'hFF, 1'b1, 22'b0}
                  : (off == 13'd6560) ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 13'd0)      ? {s, 31'b0}
                  :                        {s, e32, m[50:28]};
endmodule

// tnf64b_bare: the same E_t=8 rung WITHOUT the guard, so the k change and
// the reservation cost can be separated. One variable per experiment.
module tnf64b_bare_decode (input wire [64:0] x, output wire [31:0] fp32_out,
                      output wire invalid);
  wire       s   = x[64];
  wire [12:0] off = x[63:51];
  wire [50:0] m   = x[50:0];
  wire signed [15:0] e = $signed({1'b0, off}) - 16'sd3280;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign fp32_out = (off == 13'd6560) ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 13'd0)      ? {s, 31'b0}
                  :                        {s, e32, m[50:28]};
endmodule

// tnf17e_bare: same E_t=5 rung without the guard, so the k change and the
// reservation cost separate at 17 bits as they did at 65.
module tnf17e_bare_decode (input wire [16:0] x, output wire [31:0] fp32_out);
  wire       s   = x[16];
  wire [7:0] off = x[15:8];
  wire [7:0] m   = x[7:0];
  wire signed [15:0] e = $signed({1'b0, off}) - 16'sd121;
  wire [7:0] e32 = e[7:0] + 8'd127;
  assign fp32_out = (off == 8'd242) ? {s, 8'hFF, (|m), 22'b0}
                  : (off == 8'd0)      ? {s, 31'b0}
                  :                        {s, e32, {m[7:0], 15'b0}};
endmodule

`default_nettype wire
