// Exhaustive fp8_e5m2_decode TB: drive all 256 codes, $display "code fp32_out".
// Parsed by conformance/fp8_e5m2_verify.py and compared to an INDEPENDENT oracle
// (value computed via Python float, re-encoded to fp32 via struct — a different
// code path than the RTL's integer bit-shifts).
`timescale 1ns / 1ps
`default_nettype none
module fp8_e5m2_decode_tb;
    reg  [7:0] code;
    wire [31:0] fp32_out;
    wire is_zero, is_inf, is_nan;
    integer i;
    fp8_e5m2_decode dut (
        .e5m2_in(code), .fp32_out(fp32_out),
        .is_zero(is_zero), .is_inf(is_inf), .is_nan(is_nan));
    initial begin
        for (i = 0; i < 256; i = i + 1) begin
            code = i[7:0]; #1;
            $display("%02x %08x", code, fp32_out);
        end
        $finish;
    end
endmodule
`default_nettype wire
