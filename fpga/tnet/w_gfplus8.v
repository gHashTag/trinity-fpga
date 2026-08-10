`default_nettype none
module w_gfplus8 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  gfplus8_a_decode dec (.word_in(lf[7:0]), .pocket(2'b00), .fp32_out(fp), .is_zero());
  reg [31:0] q;
  always @(posedge clk) q <= !rst_n ? 32'b0 : fp;
  assign led = q[3:0] ^ q[7:4] ^ q[11:8] ^ q[15:12] ^ q[19:16] ^ q[23:20] ^ q[27:24] ^ q[31:28];
endmodule
