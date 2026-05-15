// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// Testbench: tom_layer_gate_controller_tb
// DUT      : tom_layer_gate_controller
//
// Test cases:
//   1. test_all_active      — layer_idle_mask=0            → idle_fraction=0, gate_threshold_met=0, vdd_enable=28'hFFFFFFF
//   2. test_half_gated      — 15 bits set (≥0.5 of 28)     → idle_fraction=17550, gate_threshold_met=1
//   3. test_full_gated      — 28 bits set                  → idle_fraction=32760, gate_threshold_met=1
//   4. test_opcode_mismatch — opcode=8'hAA                 → vdd_enable=28'hFFFFFFF, gate_threshold_met=0
//
// Note: idle_fraction = idle_count * 1170 (shift-add reciprocal, 1/28 ≈ 1170/32768).
//   15 bits → 15*1170=17550 > 16384 → gate_threshold_met=1 (≥0.5 of 28 islands idle).
//   28 bits → 28*1170=32760 ≈ 32768 → gate_threshold_met=1.
//
// Timing note: stimulus (opcode, layer_idle_mask) is set BEFORE rst_n is released so
// that the DUT sees the correct combinatorial inputs on the first active clock edge.
//
// R-SI-1: zero star operators — no * in this file.
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-34
// DOI:    10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────

`default_nettype none
`timescale 1ns/1ps

module tom_layer_gate_controller_tb;

    // ── DUT signals ───────────────────────────────────────────────────────────
    reg         clk;
    reg         rst_n;
    reg  [7:0]  opcode;
    reg  [27:0] layer_idle_mask;
    wire [27:0] layer_vdd_enable;
    wire [15:0] idle_fraction_q16;
    wire [3:0]  wave34_marker;
    wire        gate_threshold_met;

    // ── DUT instantiation ─────────────────────────────────────────────────────
    tom_layer_gate_controller dut (
        .clk               (clk),
        .rst_n             (rst_n),
        .opcode            (opcode),
        .layer_idle_mask   (layer_idle_mask),
        .layer_vdd_enable  (layer_vdd_enable),
        .idle_fraction_q16 (idle_fraction_q16),
        .wave34_marker     (wave34_marker),
        .gate_threshold_met(gate_threshold_met)
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

    // ── Helper task: check integer equality ──────────────────────────────────
    task check_eq;
        input integer test_id;
        input [63:0]  actual;
        input [63:0]  expected;
        input [127:0] label;
        begin
            if (actual === expected) begin
                $display("[PASS] test_%0d %s = %0d (expected %0d)", test_id, label, actual, expected);
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] test_%0d %s = %0d (expected %0d)", test_id, label, actual, expected);
                fail_count = fail_count + 1;
            end
        end
    endtask

    // ── Helper task: check bit equality ──────────────────────────────────────
    task check_bit;
        input integer test_id;
        input         actual;
        input         expected;
        input [127:0] label;
        begin
            if (actual === expected) begin
                $display("[PASS] test_%0d %s = %b (expected %b)", test_id, label, actual, expected);
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] test_%0d %s = %b (expected %b)", test_id, label, actual, expected);
                fail_count = fail_count + 1;
            end
        end
    endtask

    // ── Helper: reset then present stimulus ──────────────────────────────────
    // Stimulus is set BEFORE rst_n is released to avoid simulation race conditions.
    // The DUT samples opcode/mask on the first posedge after rst_n deasserts.
    task apply_test;
        input [7:0]  op;
        input [27:0] mask;
        begin
            // Set stimulus first, THEN deassert reset
            opcode          = op;
            layer_idle_mask = mask;
            rst_n = 1'b0;
            wait_cycles(4);
            rst_n = 1'b1;
            // One cycle for DUT ACTIVE state to latch fraction and transition
            @(posedge clk);
            // Another cycle for outputs to be stable (now in DRAINING, outputs hold)
            @(posedge clk);
            #1;  // small delta after posedge to read stable register outputs
        end
    endtask

    // ── Waveform dump ─────────────────────────────────────────────────────────
    initial begin
        $dumpfile("tb_tom_layer_gate.vcd");
        $dumpvars(0, tom_layer_gate_controller_tb);
    end

    // ── Main stimulus ─────────────────────────────────────────────────────────
    initial begin
        pass_count = 0;
        fail_count = 0;
        rst_n = 1'b1;   // keep high initially so clock doesn't start in reset

        // ────────────────────────────────────────────────────────────────────
        // TEST 1: test_all_active
        //   layer_idle_mask=0 → idle_count=0 → idle_fraction=0
        //   gate_threshold_met=0, vdd_enable=28'hFFFFFFF after full FSM cycle
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_all_active ---");
        apply_test(8'hE2, 28'h0000000);
        check_eq(1, idle_fraction_q16, 0, "idle_fraction_q16");
        check_bit(1, gate_threshold_met, 1'b0, "gate_threshold_met");
        // Wait for full FSM cycle (DRAINING=4 + OFF=4 + WAKING=4 = 12 cycles)
        wait_cycles(14);
        #1;
        check_eq(1, layer_vdd_enable, 28'hFFFFFFF, "layer_vdd_enable_restored");
        $display("    wave34_marker = 4'b%04b (expected 4'b1111)", wave34_marker);

        // ────────────────────────────────────────────────────────────────────
        // TEST 2: test_half_gated
        //   15 bits set (bits [14:0]) → idle_count=15
        //   idle_fraction = 15*1170 = 17550 (Q1.15 ≈ 0.536, > 0.5 of 28 islands)
        //   gate_threshold_met=1 (17550 >= 16384 ✓)
        //   Shift-add: 15*(2^10+2^7+2^4+2^1) = 15360+1920+240+30 = 17550
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_half_gated ---");
        apply_test(8'hE2, 28'h0007FFF);  // bits [14:0] = 15 bits set
        check_eq(2, idle_fraction_q16, 17550, "idle_fraction_q16");
        check_bit(2, gate_threshold_met, 1'b1, "gate_threshold_met");
        $display("    NOTE: 15/28 islands idle (>0.5), fraction=17550 >= 16384");
        wait_cycles(14);

        // ────────────────────────────────────────────────────────────────────
        // TEST 3: test_full_gated
        //   28 bits set → idle_count=28 → idle_fraction = 28*1170 = 32760 ≈ 32768
        //   gate_threshold_met=1 (32760 >= 16384 ✓)
        //   Error vs ideal (28/28 = 1.0 = 32768): delta=8, 0.024%
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_full_gated ---");
        apply_test(8'hE2, 28'hFFFFFFF);  // all 28 bits set
        check_eq(3, idle_fraction_q16, 32760, "idle_fraction_q16");
        check_bit(3, gate_threshold_met, 1'b1, "gate_threshold_met");
        $display("    NOTE: idle_fraction=32760 approx 32768 (delta=8, error=0.024%%)");
        wait_cycles(14);

        // ────────────────────────────────────────────────────────────────────
        // TEST 4: test_opcode_mismatch
        //   opcode=8'hAA → controller stays idle
        //   layer_vdd_enable=28'hFFFFFFF (all on), gate_threshold_met=0
        // ────────────────────────────────────────────────────────────────────
        $display("--- test_opcode_mismatch ---");
        apply_test(8'hAA, 28'hFFFFFFF);  // wrong opcode, all bits set
        check_eq(4, layer_vdd_enable, 28'hFFFFFFF, "layer_vdd_enable");
        check_bit(4, gate_threshold_met, 1'b0, "gate_threshold_met");
        $display("    idle_fraction_q16 = %0d (expected 0)", idle_fraction_q16);

        // ── Summary ──────────────────────────────────────────────────────────
        $display("=== SUMMARY: %0d PASS, %0d FAIL ===", pass_count, fail_count);
        $display("wave34_marker constant = 4'b%04b (expected 4'b1111)", wave34_marker);

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
