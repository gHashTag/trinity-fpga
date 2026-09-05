// Exhaustive bench for ternary_mul_top: all 9 input pairs, compared.
//
// The bench this replaces, ternary_ops_tb.v, prints
//     [4] MUL: -1 * -1 = -2 (expected +1)
//     === TERNARY_OPS_TB: ALL TESTS PASSED (8 tests) ===
// on the same run. It interpolates $signed(...) into a string and emits the
// verdict unconditionally: nothing is compared, so nothing can fail. Two
// separate faults hid behind that, and only one was a design fault:
//
//   (a) it waits #20 -- one clock -- for a design that registers both its input
//       and its output, so every sample it prints is stale;
//   (b) ternary_mul_top's b_is_zero compared against 2'b10, which is +1 in the
//       INPUT encoding. Four of nine cases were wrong.
//
// THE TRAP THAT MADE THE FIRST AUDIT REPORT THE WRONG COUNT, recorded because
// it is the same class of error as the bug: this module uses TWO DIFFERENT
// ENCODINGS, and both are documented, ten lines apart --
//     INPUT   00 = -1, 01 =  0, 10 = +1     (port declarations)
//     OUTPUT  01 = -1, 10 =  0, 11 = +1     (mul_result)
// Decoding the output with the input table gives 7 errors before the fix and 9
// after it, i.e. it makes the fix look like a regression. Both tables are
// written out below rather than assumed.
//
//   iverilog -g2012 -o /tmp/tmt ternary_mul_exhaustive_tb.v ternary_mul_top.v && /tmp/tmt
//
// Exits non-zero on any mismatch, so an exit-code gate reads it correctly.
`timescale 1ns/1ps
`default_nettype none

module ternary_mul_exhaustive_tb;
    reg clk = 0, rst_n = 0;
    reg  [1:0] a, b;
    wire [1:0] result;
    wire led;

    ternary_mul_top dut (.clk(clk), .rst_n(rst_n), .a(a), .b(b),
                         .result(result), .led(led));
    always #5 clk = ~clk;

    function integer dec_in (input [1:0] v);
        dec_in = (v == 2'b00) ? -1 : (v == 2'b01) ? 0 : (v == 2'b10) ? 1 : 99;
    endfunction
    function integer dec_out (input [1:0] v);
        dec_out = (v == 2'b01) ? -1 : (v == 2'b10) ? 0 : (v == 2'b11) ? 1 : 99;
    endfunction

    integer i, j, errors, checked;
    reg [1:0] code [0:2];

    initial begin
        code[0] = 2'b00; code[1] = 2'b01; code[2] = 2'b10;
        errors = 0; checked = 0;
        @(posedge clk); rst_n = 1; @(posedge clk);

        for (i = 0; i < 3; i = i + 1)
            for (j = 0; j < 3; j = j + 1) begin
                a = code[i]; b = code[j];
                // input register, then output register, then one for margin
                @(posedge clk); @(posedge clk); @(posedge clk);
                checked = checked + 1;
                if (dec_out(result) !== dec_in(code[i]) * dec_in(code[j])) begin
                    errors = errors + 1;
                    $display("  FAIL  %0d * %0d should be %0d, got %b = %0d",
                             dec_in(code[i]), dec_in(code[j]),
                             dec_in(code[i]) * dec_in(code[j]),
                             result, dec_out(result));
                end
            end

        // The count is asserted, not assumed: a loop that exits early would
        // otherwise report zero errors over zero comparisons.
        if (checked != 9) begin
            $display("  ABORT: %0d comparisons, 9 required", checked);
            $fatal(1);
        end
        if (errors != 0) begin
            $display("  ternary_mul_top: %0d/9 wrong -- BROKEN", errors);
            $fatal(1);
        end
        $display("  ternary_mul_top: 9/9 exhaustive, 0 errors -- CORRECT");
        $finish;
    end
endmodule
