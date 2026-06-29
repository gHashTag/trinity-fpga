// Combined exhaustive decode TB: drives all codes of fp8_e4m3/fp6_e2m3/fp6_e3m2/
// fp4/int4 and $displays "tag code fp32_out" per decoder. Parsed by
// conformance/decode_verify.py, which dispatches an independent oracle per tag.
`timescale 1ns / 1ps
`default_nettype none
module decode_tb;
    reg [7:0] code;
    wire [31:0] e4m3_out; wire e4m3_z, e4m3_nan;
    wire [31:0] e2m3_out; wire e2m3_z;
    wire [31:0] e3m2_out;
    wire [31:0] fp4_out;
    wire [31:0] i4_out;   wire i4_z;
    wire [31:0] posit_out; wire posit_z, posit_nar;
    wire        lns_sign; wire [15:0] lns_mag; wire lns_z;

    fp8_e4m3_fnuz_decode u_e4m3 (.e4m3_in(code[7:0]), .fp32_out(e4m3_out), .is_zero(e4m3_z), .is_nan(e4m3_nan));
    fp6_e2m3_decode       u_e2m3 (.fp6_in(code[5:0]), .fp32_out(e2m3_out), .is_zero(e2m3_z));
    fp6_e3m2_decode       u_e3m2 (.fp6_in(code[5:0]), .fp32_out(e3m2_out));
    fp4_decode            u_fp4  (.fp4_in(code[3:0]), .fp32_out(fp4_out));
    int4_decode           u_i4   (.int4_in(code[3:0]), .int32_out(i4_out), .is_zero(i4_z));
    posit8_decode         u_posit(.posit_in(code[7:0]), .fp32_out(posit_out), .is_zero(posit_z), .is_nar(posit_nar));
    lns8_decode           u_lns  (.lns_in(code[7:0]), .sign_out(lns_sign), .magnitude(lns_mag), .is_zero(lns_z));
    wire [31:0] i8_out; wire i8_z;
    int8_decode           u_i8   (.int8_in(code[7:0]), .int32_out(i8_out), .is_zero(i8_z));

    integer i;
    initial begin
        for (i = 0; i < 256; i = i + 1) begin
            code = i[7:0]; #1;
            $display("fp8_e4m3 %02x %08x", code[7:0], e4m3_out);
            if (i < 64)  $display("fp6_e2m3 %02x %08x", code[5:0], e2m3_out);
            if (i < 64)  $display("fp6_e3m2 %02x %08x", code[5:0], e3m2_out);
            if (i < 16)  $display("fp4_e2m1 %02x %08x", code[3:0], fp4_out);
            if (i < 16)  $display("int4     %02x %08x", code[3:0], i4_out);
            $display("posit8   %02x %08x", code[7:0], posit_out);
            $display("lns8     %02x %04x", code[7:0], lns_mag);
            $display("int8     %02x %08x", code[7:0], i8_out);
        end
        $finish;
    end
endmodule
`default_nettype wire
