#!/bin/zsh
# Decoder alone, with the WHOLE 32-bit output observed.
#
# The previous isolated run observed q[7:0] ^ q[31:24] -- sixteen of thirty-two
# bits. Synthesis removes logic not reaching an observed output, so half the
# decode could be pruned, and unequally: a decoder whose output bits are cheap in
# the unobserved half loses less than one whose cost is spread evenly.
#
# Here every output bit folds into the observed reduction, so the pruning is the
# same for all of them.
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {
cat > w_$1.v <<V
\`default_nettype none
module w_$1 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  $2
  reg [31:0] q;
  always @(posedge clk) q <= !rst_n ? 32'b0 : fp;
  assign led = q[3:0] ^ q[7:4] ^ q[11:8] ^ q[15:12] ^ q[19:16] ^ q[23:20] ^ q[27:24] ^ q[31:28];
endmodule
V
yosys -q -p "read_verilog w_$1.v $3; synth_xilinx -flatten -nodsp -top w_$1 -json w_$1.json" > wy_$1.log 2>&1
[ -f w_$1.json ] || { echo "$1|СИНТЕЗ_НЕ_ПРОШЁЛ"; return; }
FS=""
for S in 1 2 3 4 5; do
  $NP --chipdb $CDB --xdc bench.xdc --json w_$1.json --seed $S --write /dev/null > ws_$1_$S.log 2>&1
  FS="$FS $(grep -oE "Max frequency for clock .[^']*.: [0-9.]+" ws_$1_$S.log|tail -1|grep -oE "[0-9.]+$")"
done
L=$(grep -oE "SLICE_LUTX: *[0-9]+" ws_$1_1.log|tail -1|grep -oE "[0-9]+$")
echo "$1|$L|$FS"
}
run baseline "assign fp = lf[31:0];" ""
run int8    "int8_decode dec (.x(lf[7:0]), .fp32_out(fp));" "fp8_decode.v"
run gfternary "gfternary_decode dec (.gft_in(lf[1:0]), .fp32_out(fp));" "gfternary_decode.v"
run tnf16   "tnf16_decode dec (.x(lf[15:0]), .fp32_out(fp));" "bnf_decode.v"
run bnf16   "bnf16_decode dec (.x(lf[15:0]), .fp32_out(fp));" "bnf_decode.v"
run bin16   "binary16_decode dec (.b16_in(lf[15:0]), .fp32_out(fp), .is_zero(), .is_inf(), .is_nan());" "binary16_decode.v"
run bin32   "binary32_decode dec (.binary32_in(lf[31:0]), .fp32_out(fp), .is_zero());" "binary32_decode.v"
run posit8  "posit8_es2_decode dec (.posit_in(lf[7:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit8_es2_decode.v posit16_decode.v"
run posit16 "posit16_decode dec (.posit_in(lf[15:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit16_decode.v"
run posit32 "posit32_decode dec (.posit_in(lf[31:0]), .fp32_out(fp), .is_zero(), .is_nar());" "posit32_decode.v"
run ibmhfp  "ibm_hfp32_decode dec (.ibm_in(lf[31:0]), .fp32_out(fp), .is_zero());" "ibm_hfp32_decode.v"
run lns16   "lns16_decode dec (.lns_in(lf[15:0]), .fp32_out(fp));" "lns16_decode.v"
