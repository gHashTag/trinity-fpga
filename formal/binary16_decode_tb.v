// Exhaustive binary16_decode TB: drive all 65536 codes, $display "code fp32_out".
// Parsed by conformance/binary16_verify.py and compared to the C-library
// binary16 (struct 'e') -> fp32 bits (independent oracle).
`timescale 1ns / 1ps
`default_nettype none
module binary16_decode_tb;
    reg  [15:0] code;
    wire [31:0] fp32_out;
    wire is_zero, is_inf, is_nan;
    integer i;
    binary16_decode dut (
        .b16_in(code), .fp32_out(fp32_out),
        .is_zero(is_zero), .is_inf(is_inf), .is_nan(is_nan));
    initial begin
        for (i = 0; i < 65536; i = i + 1) begin
            code = i[15:0];
            #1;
            $display("%04x %08x", code, fp32_out);
        end
        $finish;
    end
endmodule
`default_nettype wire
