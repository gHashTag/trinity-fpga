// SPDX-License-Identifier: Apache-2.0
// tb_posit8_es2_decode — dump all 256 posit8(es=2) decodes for comparison against
// SoftPosit.
//
// The testbench asserts nothing on its own. It prints code and FP32 bit pattern, and
// the comparison is made against SoftPosit's convertPX2ToDouble by
// research/crossval_posit8_es2_rtl.py. A testbench that decides its own correctness
// against a model written by the same hand is not a second witness, and this campaign
// has been caught calling one that before.
//
//     iverilog -g2012 -o /tmp/tb tb_posit8_es2_decode.v posit8_es2_decode.v \
//              posit16_decode.v && /tmp/tb

`timescale 1ns / 1ps

module tb_posit8_es2_decode;

    reg  [7:0]  code;
    wire [31:0] fp32;
    wire        zero, nar;
    integer     i;

    posit8_es2_decode dut (
        .posit_in (code),
        .fp32_out (fp32),
        .is_zero  (zero),
        .is_nar   (nar)
    );

    initial begin
        for (i = 0; i < 256; i = i + 1) begin
            code = i[7:0];
            #1;
            $display("%0d\t%08x\t%0d\t%0d", i, fp32, zero, nar);
        end
        $finish;
    end

endmodule
