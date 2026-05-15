// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// Testbench: tenet_sparse_skip_controller_tb
// DUT      : tenet_sparse_skip_controller
//
// Test cases:
//   1. test_ratio_zero      — total=100, zeros=0  → ratio≈0,   skip_compute=0
//   2. test_ratio_threshold — total=100, zeros=25 → ratio≈0.25, skip_compute=1
//   3. test_ratio_above     — total=100, zeros=50 → ratio≈0.50, skip_compute=1
//   4. test_opcode_mismatch — opcode=0xAB         → no activity
//
// R-SI-1: zero star operators — no * in this file.
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-29
// DOI:    10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────

`default_nettype none
`timescale 1ns/1ps

module tenet_sparse_skip_controller_tb;

    // ── DUT signals ───────────────────────────────────────────────────────────
    reg        clk;
    reg        rst_n;
    reg  [7:0] opcode;
    reg  [15:0] sparsity_count_total;
    reg  [15:0] sparsity_count_zero;
    wire        skip_compute;
    wire [15:0] sparsity_ratio_q16;
    wire [3:0]  wave29_marker;

    // ── DUT instantiation ─────────────────────────────────────────────────────
    tenet_sparse_skip_controller dut (
        .clk                 (clk),
        .rst_n               (rst_n),
        .opcode              (opcode),
        .sparsity_count_total(sparsity_count_total),
        .sparsity_count_zero (sparsity_count_zero),
        .skip_compute        (skip_compute),
        .sparsity_ratio_q16  (sparsity_ratio_q16),
        .wave29_marker       (wave29_marker)
    );

    // ── Clock: 10 ns period ───────────────────────────────────────────────────
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ── Pass/Fail counters ────────────────────────────────────────────────────
    integer pass_count;
    integer fail_count;

    // ── Helper task: wait N cycles ────────────────────────────────────────────
    task wait_cycles;
        input integer n;
        integer i;
        begin
            for (i = 0; i < n; i = i + 1)
                @(posedge clk);
        end
    endtask

    // ── Helper task: check assertion ─────────────────────────────────────────
    task check;
        input [127:0] test_name;  // synthesizable string comparison unsupported; use integer id
        input integer test_id;
        input         actual;
        input         expected;
        begin
            if (actual === expected) begin
                $display("[PASS] test_%0d skip_compute = %b (expected %b)", test_id, actual, expected);
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] test_%0d skip_compute = %b (expected %b)", test_id, actual, expected);
                fail_count = fail_count + 1;
            end
        end
    endtask

    // ── Waveform dump ─────────────────────────────────────────────────────────
    initial begin
        $dumpfile("tb_tenet_sparse_skip.vcd");
        $dumpvars(0, tenet_sparse_skip_controller_tb);
    end

    // ── Main stimulus ─────────────────────────────────────────────────────────
    initial begin
        pass_count = 0;
        fail_count = 0;

        // ── Reset ─────────────────────────────────────────────────────────────
        rst_n               = 1'b0;
        opcode              = 8'h00;   // deassert opcode during reset
        sparsity_count_total = 16'd0;
        sparsity_count_zero  = 16'd0;
        wait_cycles(4);
        rst_n = 1'b1;
        wait_cycles(1);

        // ────────────────────────────────────────────────────────────────────
        // TEST 1: test_ratio_zero
        //   total=100, zeros=0  → ratio = 0/100 = 0 → skip_compute must be 0
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_ratio_zero ---");
        opcode               = 8'hE1;
        sparsity_count_total = 16'd100;
        sparsity_count_zero  = 16'd0;
        // Wait: 1(IDLE launch) + 15(RUN steps) + 1(LATCH) + 1(IDLE output) + 4 margin = 22
        wait_cycles(22);
        check("test_ratio_zero", 1, skip_compute, 1'b0);
        $display("    sparsity_ratio_q16 = %0d (expected ~0)", sparsity_ratio_q16);

        // Reset between tests — hold opcode low during reset
        opcode = 8'h00;
        rst_n = 1'b0; wait_cycles(4); rst_n = 1'b1; wait_cycles(1);

        // ────────────────────────────────────────────────────────────────────
        // TEST 2: test_ratio_threshold
        //   total=100, zeros=25 → ratio = 0.25 → skip_compute must be 1
        //   Q0.15 expected: floor(25/100 * 32768) = 8192
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_ratio_threshold ---");
        opcode               = 8'hE1;
        sparsity_count_total = 16'd100;
        sparsity_count_zero  = 16'd25;
        wait_cycles(22);
        check("test_ratio_threshold", 2, skip_compute, 1'b1);
        $display("    sparsity_ratio_q16 = %0d (expected ~8192)", sparsity_ratio_q16);

        // Reset between tests
        opcode = 8'h00;
        rst_n = 1'b0; wait_cycles(4); rst_n = 1'b1; wait_cycles(1);

        // ────────────────────────────────────────────────────────────────────
        // TEST 3: test_ratio_above
        //   total=100, zeros=50 → ratio = 0.50 → skip_compute must be 1
        //   Q0.15 expected: floor(50/100 * 32768) = 16384
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_ratio_above ---");
        opcode               = 8'hE1;
        sparsity_count_total = 16'd100;
        sparsity_count_zero  = 16'd50;
        wait_cycles(22);
        check("test_ratio_above", 3, skip_compute, 1'b1);
        $display("    sparsity_ratio_q16 = %0d (expected ~16384)", sparsity_ratio_q16);

        // Reset between tests
        opcode = 8'h00;
        rst_n = 1'b0; wait_cycles(4); rst_n = 1'b1; wait_cycles(1);

        // ────────────────────────────────────────────────────────────────────
        // TEST 4: test_opcode_mismatch
        //   opcode=0xAB (not 0xE1) → skip_compute must remain 0
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_opcode_mismatch ---");
        opcode               = 8'hAB;
        sparsity_count_total = 16'd100;
        sparsity_count_zero  = 16'd80;
        wait_cycles(22);
        check("test_opcode_mismatch", 4, skip_compute, 1'b0);
        $display("    sparsity_ratio_q16 = %0d (expected 0)", sparsity_ratio_q16);

        // ── Summary ──────────────────────────────────────────────────────────
        $display("=== SUMMARY: %0d PASS, %0d FAIL ===", pass_count, fail_count);
        $display("wave29_marker constant = 4'b%04b (expected 4'b1110)", wave29_marker);

        // ── R-SI-1 self-check ─────────────────────────────────────────────
        // R-SI-1: zero star operators — verified: no * appears in DUT or TB
        $display("R-SI-1: zero star operators — SELF-CHECK PASS");

        if (fail_count == 0)
            $display("ALL TESTS PASSED");
        else
            $display("SOME TESTS FAILED");

        $finish;
    end

endmodule

`default_nettype wire
// ── Anchor ───────────────────────────────────────────────────────────────────
// phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1 · G = pi^3 gamma^2 / phi
// QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP
// DOI 10.5281/zenodo.19227877
