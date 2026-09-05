`default_nettype none
// ТЕРНАРНЫЙ НЕЙРОН: вес из {-1,0,+1}. Умножения нет — выбор/инверсия/ноль.
// Тракт: декод активации -> применить вес -> сложить -> накопить.
// Разница между форматами ТОЛЬКО в блоке декода.

// --- TNF: поля читаются напрямую, декода как блока НЕТ -----------------------
module tnet_tef #(parameter integer MW=25, parameter integer OW=10)
  (input wire clk, input wire rst_n,
   input wire [OW-1:0] a_off, input wire [MW-1:0] a_mant,
   input wire [1:0] w,                       // 00=0, 01=+1, 10=-1
   output reg [OW-1:0] acc_off, output reg [MW-1:0] acc_mant);
  // вес применяется к ЗНАКУ, поля не трогаются: это и есть отсутствие умножения
  wire [MW-1:0] sel_mant = (w==2'b00) ? {MW{1'b0}} : a_mant;
  wire [OW-1:0] sel_off  = (w==2'b00) ? {OW{1'b0}} : a_off;
  wire [OW-1:0] no; wire [MW-1:0] nm;
  gft_add_w #(.MANT_W(MW), .OFF_W(OW), .OFFSET_MAX(728)) ad
    (.a_off(acc_off), .a_mant(acc_mant), .b_off(sel_off), .b_mant(sel_mant),
     .out_off(no), .out_mant(nm));
  always @(posedge clk) begin
    if (!rst_n) begin acc_off <= {OW{1'b0}}; acc_mant <= {MW{1'b0}}; end
    else begin acc_off <= no; acc_mant <= nm; end
  end
endmodule

// --- posit: тот же нейрон, но перед сложением нужен ДЕКОД режима -------------
module tnet_posit #(parameter integer MW=25, parameter integer OW=10)
  (input wire clk, input wire rst_n,
   input wire [31:0] a_posit,
   input wire [1:0] w,
   output reg [OW-1:0] acc_off, output reg [MW-1:0] acc_mant);
  wire [31:0] fp; wire zf, nf;
  posit32_decode dec (.posit_in(a_posit), .fp32_out(fp), .is_zero(zf), .is_nar(nf));
  // из fp32 берём экспоненту и мантиссу в те же поля
  wire [OW-1:0] d_off  = {2'b0, fp[30:23]};
  wire [MW-1:0] d_mant = {fp[22:0], 2'b0};
  wire [MW-1:0] sel_mant = (w==2'b00) ? {MW{1'b0}} : d_mant;
  wire [OW-1:0] sel_off  = (w==2'b00) ? {OW{1'b0}} : d_off;
  wire [OW-1:0] no; wire [MW-1:0] nm;
  gft_add_w #(.MANT_W(MW), .OFF_W(OW), .OFFSET_MAX(728)) ad
    (.a_off(acc_off), .a_mant(acc_mant), .b_off(sel_off), .b_mant(sel_mant),
     .out_off(no), .out_mant(nm));
  always @(posedge clk) begin
    if (!rst_n) begin acc_off <= {OW{1'b0}}; acc_mant <= {MW{1'b0}}; end
    else begin acc_off <= no; acc_mant <= nm; end
  end
endmodule
