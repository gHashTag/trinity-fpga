`default_nettype none
module f_gfplus8 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  gfplus8_a_decode dec (.word_in(lf[7:0]), .pocket(2'b00), .fp32_out(fp));
  wire [1:0] wt = lf[36:35];
  wire [9:0]  d_off  = {2'b0, fp[30:23]};
  wire [24:0] d_mant = {fp[22:0], 2'b0};
  wire [24:0] sm = (wt==2'b00) ? 25'b0 : d_mant;
  wire [9:0]  so = (wt==2'b00) ? 10'b0 : d_off;
  reg [9:0] ao; reg [24:0] am; wire [9:0] no; wire [24:0] nm;
  tef_add_w #(.MANT_W(25), .OFF_W(10), .OFFSET_MAX(728)) ad
    (.a_off(ao), .a_mant(am), .b_off(so), .b_mant(sm), .out_off(no), .out_mant(nm));
  always @(posedge clk) begin
    if (!rst_n) begin ao<=10'b0; am<=25'b0; end else begin ao<=no; am<=nm; end
  end
  // EVERY bit of both registers reaches the output
  wire [34:0] all = {ao, am};
  assign led = all[3:0]^all[7:4]^all[11:8]^all[15:12]^all[19:16]^all[23:20]
             ^ all[27:24]^all[31:28]^{1'b0,all[34:32]};
endmodule
