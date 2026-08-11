`default_nettype none
// Decoder alone, minimal sink: one 32-bit register folded to 4 bits. Every
// output bit is observed. Named solo_* so it cannot collide with the tracked
// d_*.v harnesses -- an earlier version of this file overwrote d_gfternary.v.
module solo_gfternary (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  gfternary_decode dec (.gft_in(lf[1:0]), .fp32_out(fp));
  reg [31:0] r;
  always @(posedge clk) r <= !rst_n ? 32'b0 : fp;
  assign led = r[3:0]^r[7:4]^r[11:8]^r[15:12]^r[19:16]^r[23:20]^r[27:24]^r[31:28];
endmodule
