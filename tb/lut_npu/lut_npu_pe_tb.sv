// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// Testbench: lut_npu_pe_tb
// DUT      : lut_npu_pe
//
// Test cases (≥9 required by Lane U gate):
//   1. test_reset          — after reset, all outputs zero
//   2. test_opcode_mismatch— opcode=0xAA → dot3_valid=0, dot3_q=0
//   3. test_all_zero       — a=b=c=0 → dot3=0
//   4. test_all_plus_one   — a=b=c=+1 → dot3=+3
//   5. test_all_minus_one  — a=b=c=-1 → dot3=-3
//   6. test_mixed_pos      — a=+1, b=+1, c=0 → dot3=+2
//   7. test_mixed_neg      — a=-1, b=0, c=-1 → dot3=-2
//   8. test_cancel         — a=+1, b=-1, c=0 → dot3=0
//   9. test_lane_zero      — lane_sel=2'b11 → dot3=0 (lane disabled)
//  10. test_reserved_code  — ter_a=2'b11 (reserved) treated as 0 → a=+1,b=+1,c=11 → dot3=+2
//  11. test_exhaustive_27  — all 27 (a,b,c) ternary triplets verified vs reference
//
// R-SI-1: zero star operators — no * in this file.
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-35
// DOI:    10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────

`default_nettype none
`timescale 1ns/1ps

module lut_npu_pe_tb;

    // ── DUT signals ───────────────────────────────────────────────────────────
    reg         clk;
    reg         rst_n;
    reg  [7:0]  opcode;
    reg  [1:0]  lane_sel;
    reg  [1:0]  ter_a;
    reg  [1:0]  ter_b;
    reg  [1:0]  ter_c;
    wire signed [3:0] dot3_q;
    wire [3:0]  wave35_marker;
    wire        dot3_valid;

    // ── DUT instantiation ─────────────────────────────────────────────────────
    lut_npu_pe dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .opcode        (opcode),
        .lane_sel      (lane_sel),
        .ter_a         (ter_a),
        .ter_b         (ter_b),
        .ter_c         (ter_c),
        .dot3_q        (dot3_q),
        .wave35_marker (wave35_marker),
        .dot3_valid    (dot3_valid)
    );

    // ── Clock: 10 ns period ───────────────────────────────────────────────────
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // ── Counters ──────────────────────────────────────────────────────────────
    integer pass_count;
    integer fail_count;

    // ── Reference ternary decode ──────────────────────────────────────────────
    function automatic integer ref_ter;
        input [1:0] t;
        begin
            case (t)
                2'b00:   ref_ter = 0;
                2'b01:   ref_ter = 1;
                2'b10:   ref_ter = -1;
                default: ref_ter = 0; // reserved
            endcase
        end
    endfunction

    function automatic integer ref_dot3;
        input [1:0] a;
        input [1:0] b;
        input [1:0] c;
        begin
            ref_dot3 = ref_ter(a) + ref_ter(b) + ref_ter(c);
        end
    endfunction

    // ── Helper task: apply opcode + ternary, sample after 1 cycle ─────────────
    task apply_and_check;
        input integer test_id;
        input [1:0] in_lane;
        input [1:0] in_a;
        input [1:0] in_b;
        input [1:0] in_c;
        input integer expected;
        input [255:0] label;
        integer act;
        begin
            @(negedge clk);
            opcode   = 8'hE3;
            lane_sel = in_lane;
            ter_a    = in_a;
            ter_b    = in_b;
            ter_c    = in_c;
            @(posedge clk);
            #1;
            act = $signed(dot3_q);
            if (act === expected && dot3_valid === 1'b1) begin
                $display("[PASS] test_%0d %s : dot3=%0d (expected %0d), valid=1",
                         test_id, label, act, expected);
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] test_%0d %s : dot3=%0d (expected %0d), valid=%b",
                         test_id, label, act, expected, dot3_valid);
                fail_count = fail_count + 1;
            end
        end
    endtask

    // ── Test orchestration ────────────────────────────────────────────────────
    integer ai, bi, ci;
    integer total_exhaustive_pass;

    initial begin
        // ── Init ──────────────────────────────────────────────────────────────
        pass_count = 0;
        fail_count = 0;
        total_exhaustive_pass = 0;
        rst_n      = 1'b0;
        opcode     = 8'h00;
        lane_sel   = 2'b00;
        ter_a      = 2'b00;
        ter_b      = 2'b00;
        ter_c      = 2'b00;

        $display("===================================================================");
        $display(" LUT-NPU PE Wave-35 simulation");
        $display(" OP_LUT_NPU=0xE3 | R-SI-1 no-star | R15 opcode chain | wave35_marker=4'b0011");
        $display("===================================================================");

        // ── Hold reset ────────────────────────────────────────────────────────
        #20;
        rst_n = 1'b1;
        @(posedge clk);

        // ── test_1: reset → dot3=0, valid=0 ──────────────────────────────────
        @(negedge clk);
        rst_n  = 1'b0;
        opcode = 8'h00;
        @(posedge clk); #1;
        if (dot3_q === 4'sd0 && dot3_valid === 1'b0) begin
            $display("[PASS] test_1 reset : dot3=0, valid=0");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] test_1 reset : dot3=%0d, valid=%b", $signed(dot3_q), dot3_valid);
            fail_count = fail_count + 1;
        end
        rst_n = 1'b1;

        // ── test_2: opcode mismatch → dot3=0, valid=0 ────────────────────────
        @(negedge clk);
        opcode   = 8'hAA;
        lane_sel = 2'b00;
        ter_a    = 2'b01; ter_b = 2'b01; ter_c = 2'b01;
        @(posedge clk); #1;
        if (dot3_q === 4'sd0 && dot3_valid === 1'b0) begin
            $display("[PASS] test_2 opcode_mismatch : dot3=0, valid=0");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] test_2 opcode_mismatch : dot3=%0d, valid=%b", $signed(dot3_q), dot3_valid);
            fail_count = fail_count + 1;
        end

        // ── test_3..8: scripted dot3 cases (opcode=0xE3, lane=0) ─────────────
        apply_and_check(3, 2'b00, 2'b00, 2'b00, 2'b00,  0, "all_zero");
        apply_and_check(4, 2'b00, 2'b01, 2'b01, 2'b01,  3, "all_plus_one");
        apply_and_check(5, 2'b00, 2'b10, 2'b10, 2'b10, -3, "all_minus_one");
        apply_and_check(6, 2'b00, 2'b01, 2'b01, 2'b00,  2, "mixed_pos");
        apply_and_check(7, 2'b00, 2'b10, 2'b00, 2'b10, -2, "mixed_neg");
        apply_and_check(8, 2'b00, 2'b01, 2'b10, 2'b00,  0, "cancel");

        // ── test_9: lane disable (lane_sel=2'b11) ────────────────────────────
        apply_and_check(9, 2'b11, 2'b01, 2'b01, 2'b01,  0, "lane_disabled");

        // ── test_10: reserved ternary code → treated as 0 ─────────────────────
        // a=+1, b=+1, c=reserved(11)=0  →  dot3 = 1+1+0 = 2
        apply_and_check(10, 2'b00, 2'b01, 2'b01, 2'b11, 2, "reserved_code_as_zero");

        // ── test_11: exhaustive 27 ternary triplets ──────────────────────────
        $display("[INFO] test_11 exhaustive: sweeping 27 triplets...");
        for (ai = 0; ai < 3; ai = ai + 1) begin
            for (bi = 0; bi < 3; bi = bi + 1) begin
                for (ci = 0; ci < 3; ci = ci + 1) begin : exhaustive_loop
                    reg [1:0] enc_a, enc_b, enc_c;
                    integer expected;
                    case (ai) 0: enc_a = 2'b00; 1: enc_a = 2'b01; 2: enc_a = 2'b10; default: enc_a = 2'b00; endcase
                    case (bi) 0: enc_b = 2'b00; 1: enc_b = 2'b01; 2: enc_b = 2'b10; default: enc_b = 2'b00; endcase
                    case (ci) 0: enc_c = 2'b00; 1: enc_c = 2'b01; 2: enc_c = 2'b10; default: enc_c = 2'b00; endcase
                    expected = ref_dot3(enc_a, enc_b, enc_c);
                    @(negedge clk);
                    opcode   = 8'hE3;
                    lane_sel = 2'b00;
                    ter_a    = enc_a;
                    ter_b    = enc_b;
                    ter_c    = enc_c;
                    @(posedge clk); #1;
                    if ($signed(dot3_q) === expected && dot3_valid === 1'b1) begin
                        total_exhaustive_pass = total_exhaustive_pass + 1;
                    end else begin
                        $display("[FAIL] test_11 exhaustive (a=%b b=%b c=%b): got=%0d expected=%0d",
                                 enc_a, enc_b, enc_c, $signed(dot3_q), expected);
                        fail_count = fail_count + 1;
                    end
                end
            end
        end
        if (total_exhaustive_pass == 27) begin
            $display("[PASS] test_11 exhaustive : 27/27 triplets match reference");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] test_11 exhaustive : %0d/27 passed", total_exhaustive_pass);
            fail_count = fail_count + 1;
        end

        // ── test_12: wave35_marker pin verification ──────────────────────────
        if (wave35_marker === 4'b0011) begin
            $display("[PASS] test_12 wave35_marker : 4'b0011");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] test_12 wave35_marker : got %b expected 4'b0011", wave35_marker);
            fail_count = fail_count + 1;
        end

        // ── Summary ───────────────────────────────────────────────────────────
        $display("===================================================================");
        $display("[SUMMARY] PASS=%0d  FAIL=%0d", pass_count, fail_count);
        $display("[SUMMARY] Wave-35 LUT-NPU PE RTL gate: %s",
                 (fail_count == 0) ? "GREEN" : "RED");
        $display(" phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON · NEVER STOP");
        $display(" DOI 10.5281/zenodo.19227877");
        $display("===================================================================");
        if (fail_count > 0) $fatal(1, "lut_npu_pe testbench reported failures");
        $finish;
    end

    // ── Watchdog ──────────────────────────────────────────────────────────────
    initial begin
        #10_000;
        $display("[FATAL] testbench watchdog");
        $fatal(1, "watchdog timeout");
    end

endmodule

`default_nettype wire
