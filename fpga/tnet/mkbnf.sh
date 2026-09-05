#!/bin/zsh
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {
cat > g_$1.v <<V
\`default_nettype none
module g_$1 (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  $2
  wire [1:0] wt = lf[36:35];
  wire [9:0] d_off = {2'b0, fp[30:23]}; wire [24:0] d_mant = {fp[22:0], 2'b0};
  wire [24:0] sm = (wt==2'b00) ? 25'b0 : d_mant;
  wire [9:0]  so = (wt==2'b00) ? 10'b0 : d_off;
  reg [9:0] ao; reg [24:0] am; wire [9:0] no; wire [24:0] nm;
  tef_add_w #(.MANT_W(25), .OFF_W(10), .OFFSET_MAX(728)) ad
    (.a_off(ao), .a_mant(am), .b_off(so), .b_mant(sm), .out_off(no), .out_mant(nm));
  always @(posedge clk) begin
    if (!rst_n) begin ao<=10'b0; am<=25'b0; end else begin ao<=no; am<=nm; end
  end
  assign led = ao[7:0] ^ am[7:0];
endmodule
V
yosys -q -p "read_verilog g_$1.v $3 gft_add_w.v; synth_xilinx -flatten -nodsp -top g_$1 -json g_$1.json" > gy_$1.log 2>&1
[ -f g_$1.json ] && $NP --chipdb $CDB --xdc bench.xdc --json g_$1.json --write gr_$1.json > gs_$1.log 2>&1
echo "$1 LUT=$(grep -oE 'SLICE_LUTX: *[0-9]+' gs_$1.log 2>/dev/null|tail -1|grep -oE '[0-9]+') BRAM=$(grep -oE 'RAMB36E1: *[0-9]+' gs_$1.log 2>/dev/null|tail -1|grep -oE '[0-9]+$') F=$(grep -oE "Max frequency for clock '[^']*': [0-9.]+" gs_$1.log 2>/dev/null|tail -1|grep -oE '[0-9.]+$')"
}
run bnf16  "bnf16_decode dec (.x(lf[15:0]), .fp32_out(fp));"  "bnf_decode.v"
run tnf16x "tnf16_decode dec (.x(lf[15:0]), .fp32_out(fp));"  "bnf_decode.v"
