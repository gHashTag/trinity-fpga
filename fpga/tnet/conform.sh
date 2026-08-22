#!/bin/zsh
# Does the decoder we measured actually decode?
#
# The throughput table prices twenty-one decoders. Area and frequency say
# nothing about whether the circuit computes the right value, and a decoder that
# is wrong is small for a reason. Every 8- and 16-bit format is swept in full --
# 256 and 65,536 codes -- through the same RTL that was synthesised, and the
# fp32 output is dumped for comparison against the format's reference.
run() {  # $1 name  $2 width  $3 instance  $4 sources
cat > tb_$1.v <<V
\`timescale 1ns/1ps
module tb_$1;
  reg clk = 0; always #1 clk = ~clk;
  reg [$(($2-1)):0] x; wire [31:0] fp;
  $3
  integer i;
  initial begin
    for (i = 0; i < (1<<$2); i = i + 1) begin
      x = i[$(($2-1)):0]; #1; \$display("%0d %08x", i, fp); #1;
    end
    \$finish;
  end
endmodule
V
iverilog -o /tmp/cf_$1 -g2012 tb_$1.v ${=4} 2>tb_$1.err && vvp /tmp/cf_$1 > cf_$1.txt 2>/dev/null \
  && echo "$1 OK $(grep -c . cf_$1.txt) кодов" || echo "$1 СБОЙ $(head -1 tb_$1.err 2>/dev/null | cut -c1-60)"
}
run gfternary 2  "gfternary_decode dec (.gft_in(x), .fp32_out(fp));" "gfternary_decode.v"
run int8      8  "int8_decode dec (.x(x), .fp32_out(fp));" "fp8_decode.v"
run fp8e4m3   8  "fp8_e4m3_decode dec (.x(x), .fp32_out(fp));" "fp8_decode.v"
run fp8e5m2   8  "fp8_e5m2_decode dec (.x(x), .fp32_out(fp));" "fp8_decode.v"
run minifloat 8  "minifloat_decode dec (.mf_in(x), .fp32_out(fp));" "minifloat_decode.v"
run posit8    8  "posit8_es2_decode dec (.posit_in(x), .fp32_out(fp), .is_zero(), .is_nar());" "posit8_es2_decode.v posit16_decode.v"
run gfplus8   8  "gfplus8_a_decode dec (.word_in(x), .pocket(2'b00), .fp32_out(fp));" "gfplus8_a_decode.v"
run gf10     10  "gf10_decode dec (.gf10_in(x), .fp32_out(fp));" "gf10_decode.v"
run gf14     14  "gf14_decode dec (.gf14_in(x), .fp32_out(fp));" "gf14_decode.v"
run tnf16    16  "tnf16_decode dec (.x(x), .fp32_out(fp));" "bnf_decode.v"
run bnf16    16  "bnf16_decode dec (.x(x), .fp32_out(fp));" "bnf_decode.v"
run binary16 16  "binary16_decode dec (.b16_in(x), .fp32_out(fp));" "binary16_decode.v"
run posit16  16  "posit16_decode dec (.posit_in(x), .fp32_out(fp), .is_zero(), .is_nar());" "posit16_decode.v"
run lns16    16  "lns16_decode dec (.lns_in(x), .fp32_out(fp));" "lns16_decode.v"
