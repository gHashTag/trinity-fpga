#!/bin/zsh
# The twenty-row throughput table, re-measured with the WHOLE accumulator
# observed. The harness it was first measured on ended with
#     assign led = ao[7:0] ^ am[7:0];
# which shows 8 of 10 offset bits and 8 of 25 mantissa bits, so synthesis was
# free to prune up to 68% of the logic feeding the accumulator -- and to prune
# it by different amounts for different formats. That is the same defect this
# paper already records for the decoder tables; this table was never re-run.
#
# Here every bit of both registers folds into the observed output, and five
# placement seeds are swept instead of one.
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {
cat > f_$1.v <<V
\`default_nettype none
module f_$1 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  $2
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
V
yosys -q -p "read_verilog f_$1.v $3 gft_add_w.v; synth_xilinx -flatten -nodsp -top f_$1 -json f_$1.json" > fy_$1.log 2>&1
[ -f f_$1.json ] || { echo "$1|СИНТЕЗ_НЕ_ПРОШЁЛ"; return; }
FS=""
for S in 1 2 3 4 5; do
  $NP --chipdb $CDB --xdc bench.xdc --json f_$1.json --seed $S --write /dev/null > fs_$1_$S.log 2>&1
  FS="$FS $(grep -oE "Max frequency for clock .[^']*.: [0-9.]+" fs_$1_$S.log|tail -1|grep -oE '[0-9.]+$')"
done
L=$(grep -oE "SLICE_LUTX: *[0-9]+" fs_$1_1.log|tail -1|grep -oE '[0-9]+$')
echo "$1|$L|$FS"
}
run bnf16s    "bnf16s_decode dec (.x(lf[16:0]), .fp32_out(fp));" "tnf_spec_decode.v"
