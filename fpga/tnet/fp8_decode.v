`default_nettype none
// fp8 e4m3 и e5m2: фиксированные поля, декод — чтение
module fp8_e4m3_decode (input wire [7:0] x, output wire [31:0] fp32_out);
  wire s=x[7]; wire [3:0] e=x[6:3]; wire [2:0] m=x[2:0];
  wire [7:0] e32 = (e==0) ? 8'd0 : (e - 8'd7 + 8'd127);
  assign fp32_out = {s, e32, m, 20'b0};
endmodule
module fp8_e5m2_decode (input wire [7:0] x, output wire [31:0] fp32_out);
  wire s=x[7]; wire [4:0] e=x[6:2]; wire [1:0] m=x[1:0];
  wire [7:0] e32 = (e==0) ? 8'd0 : (e - 8'd15 + 8'd127);
  assign fp32_out = {s, e32, m, 21'b0};
endmodule
module int8_decode (input wire [7:0] x, output wire [31:0] fp32_out);
  // целое: масштаб общий на блок, декод — знакорасширение
  assign fp32_out = {{24{x[7]}}, x};
endmodule
// КОНВЕРТЕР ОСНОВАНИЯ: двоичное поле -> сбалансированный тернар (для тернарной фабрики)
module bin2ter #(parameter integer BW=8, parameter integer TW=6)
  (input wire [BW-1:0] b, output reg [2*TW-1:0] t);
  integer i; reg [BW-1:0] v;
  always @(*) begin
    v = b; t = 0;
    for (i=0; i<TW; i=i+1) begin
      t[2*i +: 2] = v % 3;      // цифра 0/1/2 в 2-битном коде
      v = v / 3;
    end
  end
endmodule
