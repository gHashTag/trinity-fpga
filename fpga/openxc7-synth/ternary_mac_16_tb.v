// Ternary MAC Testbench — BENCH-006
// Tests: zero vectors, all-ones, sparse, alternating signs

`default_nettype none

`timescale 1ns/1ps

module ternary_mac_16_tb;

    // ========================================================================
    // DUT Signals
    // ========================================================================
    reg clk;
    reg rst_n;
    reg valid;
    wire ready;
    reg [31:0] w;
    reg [31:0] x;
    wire [15:0] y;
    wire overflow;
    wire led;

    // ========================================================================
    // Test State
    // ========================================================================
    integer test_num;
    integer error_count;
    reg signed [15:0] expected;

    // ========================================================================
    // Ternary Encoding Helpers
    // ========================================================================
    // 10 = -1, 00 = 0, 01 = +1

    function [1:0] enc_neg;
        input [0:0] unused;
        enc_neg = 2'b10;
    endfunction

    function [1:0] enc_zero;
        input [0:0] unused;
        enc_zero = 2'b00;
    endfunction

    function [1:0] enc_pos;
        input [0:0] unused;
        enc_pos = 2'b01;
    endfunction

    // Build 32-bit vector from 16 trits
    function [31:0] make_trits;
        input [31:0] pattern;  // 2 bits per trit: 00=zero, 01=pos, 10=neg
        make_trits = pattern;
    endfunction

    // ========================================================================
    // DUT Instantiation
    // ========================================================================
    ternary_mac_16_top #(
        .LATENCY(2)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .valid(valid),
        .ready(ready),
        .w(w),
        .x(x),
        .y(y),
        .overflow(overflow),
        .led(led)
    );

    // ========================================================================
    // Clock Generation (10 MHz)
    // ========================================================================
    initial begin
        clk = 0;
        forever #50 clk = ~clk;
    end

    // ========================================================================
    // Test Sequence
    // ========================================================================
    initial begin
        // Initialize
        $display("═══════════════════════════════════════════════════════════════");
        $display("Ternary MAC-16 Testbench — BENCH-006");
        $display("═══════════════════════════════════════════════════════════════");

        test_num = 0;
        error_count = 0;
        rst_n = 0;
        valid = 0;
        w = 32'h0;
        x = 32'h0;

        // Reset
        #100;
        rst_n = 1;
        #100;

        // --------------------------------------------------------------------
        // Test 1: Zero vectors → y = 0
        // --------------------------------------------------------------------
        test_num = 1;
        $display("\n[Test %0d] Zero vectors", test_num);
        w = 32'h0;
        x = 32'h0;
        expected = 0;
        drive_and_check(32'h0, 32'h0, 0);

        // --------------------------------------------------------------------
        // Test 2: All +1 weights, all +1 inputs → y = 16
        // --------------------------------------------------------------------
        test_num = 2;
        $display("\n[Test %0d] All +1 → y = 16", test_num);
        w = {16{enc_pos(0)}};
        x = {16{enc_pos(0)}};
        drive_and_check(w, x, 16);

        // --------------------------------------------------------------------
        // Test 3: All +1 weights, all -1 inputs → y = -16
        // --------------------------------------------------------------------
        test_num = 3;
        $display("\n[Test %0d] w=+1, x=-1 → y = -16", test_num);
        w = {16{enc_pos(0)}};
        x = {16{enc_neg(0)}};
        drive_and_check(w, x, -16);

        // --------------------------------------------------------------------
        // Test 4: Half +1, half -1 (alternating) → y = 0
        // --------------------------------------------------------------------
        test_num = 4;
        $display("\n[Test %0d] Alternating +1/-1 → y = 0", test_num);
        w = {8{enc_pos(0), enc_neg(0)}};
        x = {16{enc_pos(0)}};
        drive_and_check(w, x, 0);

        // --------------------------------------------------------------------
        // Test 5: Sparse: 4 non-zero → y = 4
        // --------------------------------------------------------------------
        test_num = 5;
        $display("\n[Test %0d] Sparse: 4 non-zero → y = 4", test_num);
        w = {12{enc_zero(0)}, 4{enc_pos(0)}};
        x = {12{enc_zero(0)}, 4{enc_pos(0)}};
        drive_and_check(w, x, 4);

        // --------------------------------------------------------------------
        // Test 6: All zeros in weights → y = 0
        // --------------------------------------------------------------------
        test_num = 6;
        $display("\n[Test %0d] All zero weights → y = 0", test_num);
        w = {16{enc_zero(0)}};
        x = {16{enc_pos(0)}};
        drive_and_check(w, x, 0);

        // --------------------------------------------------------------------
        // Test 7: Single +1 pair → y = 1
        // --------------------------------------------------------------------
        test_num = 7;
        $display("\n[Test %0d] Single +1 pair → y = 1", test_num);
        w = {15{enc_zero(0)}, enc_pos(0)};
        x = {15{enc_zero(0)}, enc_pos(0)};
        drive_and_check(w, x, 1);

        // --------------------------------------------------------------------
        // Test 8: Pattern: ++--++-- (4x +1, 4x -1) → y = 0
        // --------------------------------------------------------------------
        test_num = 8;
        $display("\n[Test %0d] Pattern ++--++-- → y = 0", test_num);
        w = {4{enc_pos(0), enc_pos(0), enc_neg(0), enc_neg(0)}};
        x = {16{enc_pos(0)}};
        drive_and_check(w, x, 0);

        // --------------------------------------------------------------------
        // Test 9: Accumulation test (2 cycles)
        // --------------------------------------------------------------------
        test_num = 9;
        $display("\n[Test %0d] Accumulation: 8 + 8 = 16", test_num);
        // First cycle: 8 pairs of +1
        w = {8{enc_pos(0), enc_zero(0)}};
        x = {8{enc_pos(0), enc_zero(0)}};
        drive_and_wait(w, x);
        // Second cycle: another 8 pairs
        @(posedge clk);
        valid = 1;
        #100;
        valid = 0;
        repeat(2) @(posedge clk);
        if ($signed(y) !== 16'sd16) begin
            $display("  ❌ FAIL: expected 16, got %0d", $signed(y));
            error_count = error_count + 1;
        end else begin
            $display("  ✅ PASS: y = %0d", $signed(y));
        end

        // --------------------------------------------------------------------
        // Summary
        // --------------------------------------------------------------------
        #100;
        $display("\n═══════════════════════════════════════════════════════════════");
        if (error_count == 0) begin
            $display("✅ ALL TESTS PASSED (%0d/%0d)", test_num - error_count, test_num);
        end else begin
            $display("❌ TESTS FAILED: %0d/%0d errors", error_count, test_num);
        end
        $display("═══════════════════════════════════════════════════════════════");

        $finish;
    end

    // ========================================================================
    // Task: Drive inputs and check output
    // ========================================================================
    task drive_and_check;
        input [31:0] w_val;
        input [31:0] x_val;
        input signed [15:0] expected_val;

        begin
            drive_and_wait(w_val, x_val);
            // Wait for latency + 1
            repeat(3) @(posedge clk);

            if ($signed(y) !== expected_val) begin
                $display("  ❌ FAIL: expected %0d, got %0d", expected_val, $signed(y));
                error_count = error_count + 1;
            end else begin
                $display("  ✅ PASS: y = %0d", $signed(y));
            end
        end
    endtask

    // ========================================================================
    // Task: Drive inputs and wait
    // ========================================================================
    task drive_and_wait;
        input [31:0] w_val;
        input [31:0] x_val;

        begin
            @(posedge clk);
            w = w_val;
            x = x_val;
            valid = 1;
            #100;
            valid = 0;
            @(posedge clk);
        end
    endtask

    // ========================================================================
    // Timeout Watchdog
    // ========================================================================
    initial begin
        #100000;
        $display("\n❌ TIMEOUT after 100us");
        $finish;
    end

endmodule
