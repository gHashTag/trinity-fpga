// Minimal dump TB: drive gf_adder_param (GF8) over all 65536 (a,b), $fwrite each
// "a b out_y" so the Python golden can cross-check (2nd oracle). Local iverilog only.
`timescale 1ns/1ps
`default_nettype none
module gf8_dut_dump_tb;
    localparam EXP_BITS=3, MANT_BITS=4, TOTAL=8;
    reg clk=0, rst=1, in_valid=0, out_ready=1;
    reg  [TOTAL-1:0] in_a, in_b;
    wire in_ready, out_valid;
    wire [TOTAL-1:0] out_y;
    integer a, b;
    integer fd;
    gf_adder_param #(.EXP_BITS(EXP_BITS), .MANT_BITS(MANT_BITS)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready));
    always #5 clk = ~clk;
    initial begin
        fd = $fopen("/tmp/gf8_dut_dump.txt", "w");
        in_a=0; in_b=0;
        @(posedge clk); #1; rst=0;
        @(posedge clk); #1;
        for (a=0; a<256; a=a+1) begin
            for (b=0; b<256; b=b+1) begin
                in_a=a[TOTAL-1:0]; in_b=b[TOTAL-1:0]; in_valid=1'b1;
                @(posedge clk); #1;
                $fdisplay(fd, "%0d %0d %0d", a, b, out_y);
            end
        end
        $fclose(fd);
        $finish;
    end
endmodule
`default_nettype wire
