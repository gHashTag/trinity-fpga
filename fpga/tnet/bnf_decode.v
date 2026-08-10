`default_nettype none
// BNF: двоичное поле экспоненты, ширина под диапазон, все позиции потрачены.
// TNF: тернарное поле той же ёмкости. Различие РОВНО в этом.
module bnf16_decode (input wire [15:0] x, output wire [31:0] fp32_out);
  wire s = x[15]; wire [6:0] e = x[14:8]; wire [7:0] m = x[7:0];
  wire [7:0] e32 = (e == 0) ? 8'd0 : ({1'b0,e} - 8'd63 + 8'd127);
  assign fp32_out = {s, e32, m, 15'b0};
endmodule
module tnf16_decode (input wire [15:0] x, output wire [31:0] fp32_out);
  wire s = x[15]; wire [6:0] off = x[14:8]; wire [7:0] m = x[7:0];
  // 4 трита упакованы в 7 бит; смещение читается напрямую, как и у BNF
  wire [7:0] e32 = ({1'b0,off} - 8'd40 + 8'd127);
  assign fp32_out = {s, e32, m, 15'b0};
endmodule
