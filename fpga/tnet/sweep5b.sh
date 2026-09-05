#!/bin/zsh
# Median-of-five placement seeds. Area is deterministic under seed variation and
# timing is not -- measured at 0.0% against 11.4% on this flow -- so a single-run
# frequency cannot rank rows closer than that. Reports median and spread.
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {
cat > s_$1.v <<V
\`default_nettype none
module s_$1 (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  $2
  wire [1:0] wt = lf[36:35];
  wire [9:0]  d_off = {2'b0, fp[30:23]};
  wire [24:0] d_mant = {fp[22:0], 2'b0};
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
yosys -q -p "read_verilog s_$1.v $3 gft_add_w.v; synth_xilinx -flatten -nodsp -top s_$1 -json s_$1.json" > sy_$1.log 2>&1
[ -f s_$1.json ] || { echo "$1 СИНТЕЗ_НЕ_ПРОШЁЛ"; return; }
FS=""
for S in 1 2 3 4 5; do
  $NP --chipdb $CDB --xdc bench.xdc --json s_$1.json --seed $S --write /dev/null > ss_$1_$S.log 2>&1
  f=$(grep -oE "Max frequency for clock .[^']*.: [0-9.]+" ss_$1_$S.log|tail -1|grep -oE "[0-9.]+$")
  FS="$FS $f"
done
L=$(grep -oE "SLICE_LUTX: *[0-9]+" ss_$1_1.log|tail -1|grep -oE "[0-9]+$")
echo "$1|$L|$FS"
}
run posit8   "posit8_es2_decode dec (.posit_in(lf[7:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit8_es2_decode.v posit16_decode.v"
run posit16  "posit16_decode dec (.posit_in(lf[15:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit16_decode.v"
run posit32  "posit32_decode dec (.posit_in(lf[31:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit32_decode.v"
run takum16  "takum16_decode dec (.clk(clk), .takum16_in(lf[15:0]), .fp32_out(fp));" "takum16_decode.v"
run ibmhfp   "ibm_hfp32_decode dec (.ibm_in(lf[31:0]), .fp32_out(fp), .is_zero());" "ibm_hfp32_decode.v"
run bin16    "binary16_decode dec (.b16_in(lf[15:0]), .fp32_out(fp), .is_zero(), .is_inf(), .is_nan());" "binary16_decode.v"
run bin32    "binary32_decode dec (.binary32_in(lf[31:0]), .fp32_out(fp), .is_zero());" "binary32_decode.v"
run gfplus8  "gfplus8_a_decode dec (.word_in(lf[7:0]), .pocket(2'b00), .fp32_out(fp), .is_zero());" "gfplus8_a_decode.v"
