// Smoke-test the 5 Corona decoders (correctness of the copied source in iverilog).
// Known golden values: int8(0x05)=int32 5; int8(0xFF)=int32 -1;
// bf16(0x3F80)=fp32 1.0 (0x3F800000); bf16(0xBF80)=fp32 -1.0 (0xBF800000).
`timescale 1ns/1ps
`default_nettype none
module tb_corona_decoders_smoke;
    reg  [7:0]  i8; wire [31:0] i8o; wire i8z;
    int8_decode  u_i8 (.int8_in(i8), .int32_out(i8o), .is_zero(i8z));
    reg  [15:0]  bf; wire [31:0] bfo; wire bfz,bfi,bfn;
    bf16_decode  u_bf (.bf16_in(bf), .fp32_out(bfo), .is_zero(bfz), .is_inf(bfi), .is_nan(bfn));
    integer fails = 0;
    task chk32(input [255:0] name, input [31:0] got, input [31:0] exp);
      begin if (got !== exp) begin fails=fails+1; $display("FAIL %0s got=0x%08h exp=0x%08h", name, got, exp); end
            else $display("ok   %0s = 0x%08h", name, got); end
    endtask
    initial begin
        i8=8'h05; #1; chk32("int8(0x05)",   i8o, 32'h0000_0005);
        i8=8'hFF; #1; chk32("int8(0xFF=-1)",i8o, 32'hFFFF_FFFF);
        bf=16'h3F80; #1; chk32("bf16(0x3F80=1.0)",  bfo, 32'h3F80_0000);
        bf=16'hBF80; #1; chk32("bf16(0xBF80=-1.0)", bfo, 32'hBF80_0000);
        $display("SMOKE %0d fails", fails);
        $finish;
    end
endmodule
`default_nettype wire
