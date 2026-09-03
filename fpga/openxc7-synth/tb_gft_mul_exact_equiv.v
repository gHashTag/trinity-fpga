// Do the fp32 path and the exact 13-cell unit compute the same function?
// Every one of the 16 input pairs, driven through the fp32 pipeline's
// handshake and compared against the combinational unit.
`timescale 1ns/1ps
module tb_equiv;
    reg clk = 0, rst = 1, valid = 0;
    reg [1:0] a = 0, b = 0;
    wire [1:0] y_fp32, y_exact;
    integer i, j, mismatches = 0, checked = 0;
    integer guard;

    always #5 clk = ~clk;

    fp32_path      u_fp32 (.clk(clk), .rst(rst), .valid(valid), .a(a), .b(b), .y(y_fp32));
    gft_mul_exact  u_ex   (.a(a), .b(b), .y(y_exact));

    initial begin
        repeat (4) @(posedge clk);
        rst = 0;
        repeat (2) @(posedge clk);
        for (i = 0; i < 4; i = i + 1) begin
            for (j = 0; j < 4; j = j + 1) begin
                a = i[1:0]; b = j[1:0];
                @(posedge clk); valid = 1;
                @(posedge clk); valid = 0;
                // The multiplier is pipelined; wait it out rather than guessing.
                guard = 0;
                while (u_fp32.ov !== 1'b1 && guard < 200) begin
                    @(posedge clk); guard = guard + 1;
                end
                @(posedge clk);
                checked = checked + 1;
                if (y_fp32 !== y_exact) begin
                    mismatches = mismatches + 1;
                    $display("  MISMATCH a=%b b=%b : fp32=%b exact=%b", a, b, y_fp32, y_exact);
                end else begin
                    $display("  a=%b b=%b -> %b   (both)", a, b, y_exact);
                end
                repeat (3) @(posedge clk);
            end
        end
        $display("\n  %0d/%0d input pairs agree", checked - mismatches, checked);
        if (mismatches == 0) $display("  the 13-cell unit computes the same function as the fp32 path");
        else                 $display("  THEY DIFFER — the theorem does not describe this RTL");
        $finish;
    end
endmodule
