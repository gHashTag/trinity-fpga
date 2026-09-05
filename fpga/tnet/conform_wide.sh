#!/bin/zsh
# The wide formats, sampled. A 32- or 64-bit sweep cannot be exhaustive, but an
# undefined output does not hide: a pseudorandom walk over 40,000 codes finds an
# X module as surely as an exhaustive one, and that is what this check is for.
run() {  # $1 name  $2 width  $3 instance  $4 sources
cat > tw_$1.v <<V
\`timescale 1ns/1ps
module tw_$1;
  reg [$(($2-1)):0] x; wire [31:0] fp;
  reg clk = 1'b0;
  $3
  integer i; reg [63:0] r, r2;
  initial begin
    r = 64'h2545F4914F6CDD1D; r2 = 64'h853C49E6748FEA9B;
    for (i = 0; i < 40000; i = i + 1) begin
      r = r * 64'd6364136223846793005 + 64'd1442695040888963407;
      r2 = r2 * 64'd3935559000370003845 + 64'd2691343689449507681;
      // A 64-bit generator cannot fill a wider input. tnf64s is 65 bits, and
      // driving x[64] from nothing left it undefined -- which printed as 'x'
      // in the code column, so the checker read the whole file as "swept
      // nothing" and the real 40,000 samples were never examined.
      x = {r2, r};
      // A clocked module needs an edge. takum16_decode is a BRAM LUT behind
      // 'always @(posedge clk)', and the harness fed it a constant, so its
      // output was X on all 40,000 codes by construction -- the module was
      // never exercised at all. Combinational modules ignore this clock.
      #1; clk = 1'b1; #1; clk = 1'b0; #1;
      \$display("%0d %08x", x, fp);
    end
    \$finish;
  end
endmodule
V
iverilog -o /tmp/cw_$1 -g2012 tw_$1.v ${=4} 2>tw_$1.err && vvp /tmp/cw_$1 > cf_$1.txt 2>/dev/null \
  && echo "$1 OK" || echo "$1 СБОЙ $(head -1 tw_$1.err 2>/dev/null | cut -c1-56)"
}
run binary32 32 "binary32_decode dec (.binary32_in(x), .fp32_out(fp), .is_zero());" "binary32_decode.v"
run vaxf     32 "vax_f_decode dec (.vax_in(x), .fp32_out(fp));" "vax_f_decode.v"
run ibmhfp   32 "ibm_hfp32_decode dec (.ibm_in(x), .fp32_out(fp));" "ibm_hfp32_decode.v"
run posit32  32 "posit32_decode dec (.posit_in(x), .fp32_out(fp), .is_zero(), .is_nar());" "posit32_decode.v"
run posit8    8 "posit8_es2_decode dec (.posit_in(x), .fp32_out(fp), .is_zero(), .is_nar());" "posit8_es2_decode.v posit16_decode.v"
run takum16  16 "takum16_decode dec (.clk(clk), .takum16_in(x), .fp32_out(fp));" "takum16_decode.v"
run tnf64s   65 "tnf64s_decode dec (.x(x), .fp32_out(fp));" "tnf_spec_decode.v"
