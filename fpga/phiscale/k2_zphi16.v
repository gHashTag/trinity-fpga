`default_nettype none
module k2_zphi16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [31:0] r0 = 32'h1234_5678, r1 = 32'h9ABC_DEF0, r2 = 32'h0F1E_2D3C, r3 = 32'hDEAD_BEEF;
  always @(posedge clk) begin
    r0 <= !rst_n ? 32'h1234_5678 : {r0[30:0], r0[31]^r0[21]^r0[1]^r0[0]};
    r1 <= !rst_n ? 32'h9ABC_DEF0 : {r1[30:0], r1[31]^r1[29]^r1[25]^r1[24]};
    r2 <= !rst_n ? 32'h0F1E_2D3C : {r2[30:0], r2[31]^r2[27]^r2[15]^r2[3]};
    r3 <= !rst_n ? 32'hDEAD_BEEF : {r3[30:0], r3[31]^r3[19]^r3[11]^r3[2]};
  end
  wire [31:0] keep = r0 ^ r1 ^ r2 ^ r3;
  wire signed [15:0] sa, sb;
  zphi_add16 #(.ACC(16)) u (.clk(clk), .a0(r0[15:0]), .b0(r1[15:0]), .a1(r2[15:0]), .b1(r3[15:0]), .sa(sa), .sb(sb));
  wire [31:0] acc = {sa, sb};
  wire [31:0] tot = acc ^ keep;
  assign led = tot[3:0]^tot[7:4]^tot[11:8]^tot[15:12]^tot[19:16]^tot[23:20]^tot[27:24]^tot[31:28];
endmodule
