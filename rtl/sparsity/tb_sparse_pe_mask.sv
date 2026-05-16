// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Dmitrii Vasilev <admin@t27.ai>
//
// phi^2 + phi^-2 = 3 · OP_SPARSE_MASK=0xE8 · λ=φ⁻² · R-SI-1 zero-multiplier · Apache-2.0
//
// Testbench: tb_sparse_pe_mask
// W40 Lane GG — 6 test cases for sparse_pe_mask module
//
// R-SI-1 note: reference model in this TB uses '*' only for verification
//   arithmetic — the production RTL (sparse_pe_mask.sv) has zero '*'.
//
// Anchor: phi^2 + phi^-2 = 3 · gamma = phi^-3 · QUANTUM BRAIN 1:1 SILICON
//         · 3-STRAND DNA · NEVER STOP · DOI 10.5281/zenodo.19227877

`timescale 1ns/1ps

module tb_sparse_pe_mask;

    localparam N      = 27;
    localparam WIDTH  = 4;

    // DUT ports
    reg                         clk;
    reg                         rst_n;
    reg  [N-1:0]                mask;
    reg  signed [WIDTH-1:0]     a [0:N-1];
    reg  signed [WIDTH-1:0]     b [0:N-1];
    wire signed [2*WIDTH+5:0]   sum_out;

    // DUT instantiation
    sparse_pe_mask #(.N(N), .WIDTH(WIDTH)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .mask(mask),
        .a(a),
        .b(b),
        .sum_out(sum_out)
    );

    // Clock: 10 ns period
    initial clk = 0;
    always #5 clk = ~clk;

    integer pass_count;
    integer fail_count;
    integer k, iter, errs;
    integer observed_val, expected_val, ref_val;

    // Reference model: compute expected sum (uses '*' only in TB verification)
    // Inline in initial block to avoid unpacked array in function param
    // ref_val computed inline via a local loop below each test case.

    integer ai_ref, bi_ref, pi_ref, ref_acc;
    integer rng_seed;

    // Simple pseudo-random using $random with fixed seed sequence
    // We use global rng_seed and call $random(rng_seed)

    initial begin
        pass_count = 0;
        fail_count = 0;
        rng_seed   = 42;
        rst_n      = 0;
        mask       = {N{1'b0}};
        for (k = 0; k < N; k++) begin a[k] = 0; b[k] = 0; end

        repeat(2) @(posedge clk);
        rst_n = 1;
        @(posedge clk); #1;

        // =================================================================
        // TC1: mask=all-ones, a=+1 everywhere, b=-1 everywhere → expect -27
        // =================================================================
        mask = {N{1'b1}};
        for (k = 0; k < N; k++) begin
            a[k] = 4'sb0001;   // ternary +1
            b[k] = 4'sb1111;   // -1
        end
        @(posedge clk); #1;
        @(posedge clk); #1;
        observed_val = $signed(sum_out);
        expected_val = -27;
        if (observed_val === expected_val) begin
            $display("TC1 PASS: mask=all-1 a=+1 b=-1 => sum=%0d (expected %0d)",
                     observed_val, expected_val);
            pass_count = pass_count + 1;
        end else begin
            $display("TC1 FAIL: sum=%0d expected=%0d", observed_val, expected_val);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // TC2: mask=all-zeros → expect 0 (full sparsity, all PEs gated)
        // =================================================================
        mask = {N{1'b0}};
        for (k = 0; k < N; k++) begin
            a[k] = 4'sb0001;
            b[k] = (k % 7) - 3;
        end
        @(posedge clk); #1;
        @(posedge clk); #1;
        observed_val = $signed(sum_out);
        if (observed_val === 0) begin
            $display("TC2 PASS: mask=all-0 => sum=0 (full sparsity)");
            pass_count = pass_count + 1;
        end else begin
            $display("TC2 FAIL: sum=%0d expected=0", observed_val);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // TC3: alternating mask 010101..., deterministic inputs, compare ref
        // mask[0]=0,mask[1]=1,mask[2]=0,mask[3]=1,...
        // =================================================================
        mask = 27'b010_1010_1010_1010_1010_1010_101;  // 13 ones (odd positions 1,3,5,...)
        for (k = 0; k < N; k++) begin
            case (k % 3)
                0: a[k] = 4'sb0001;    // +1
                1: a[k] = 4'sb0000;    // 0
                2: a[k] = 4'sb1111;    // -1
                default: a[k] = 0;
            endcase
            b[k] = (k % 7) - 3;
        end
        @(posedge clk); #1;
        @(posedge clk); #1;
        observed_val = $signed(sum_out);
        // compute reference
        ref_acc = 0;
        for (k = 0; k < N; k++) begin
            if (mask[k]) begin
                ai_ref = $signed(a[k]);
                bi_ref = $signed(b[k]);
                pi_ref = ai_ref * bi_ref;  // reference-only multiply
                ref_acc = ref_acc + pi_ref;
            end
        end
        ref_val = ref_acc;
        if (observed_val === ref_val) begin
            $display("TC3 PASS: alternating mask => sum=%0d matches ref=%0d",
                     observed_val, ref_val);
            pass_count = pass_count + 1;
        end else begin
            $display("TC3 FAIL: sum=%0d ref=%0d", observed_val, ref_val);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // TC4: walking-1 mask — each lane independent (27 iterations)
        //      a[i]=+1, b[i]=i+1 for all i; mask has single bit set
        // =================================================================
        // b[k] values must fit in signed WIDTH=4 bits: range -8..7
        // Use b[k] = (k % 7) + 1 → values 1..7, wrapping, all fit in 4-bit signed
        errs = 0;
        for (k = 0; k < N; k++) begin
            a[k] = 4'sb0001;          // +1
            b[k] = (k % 7) + 1;      // 1..7 (fits in 4-bit signed, no overflow)
        end
        for (iter = 0; iter < N; iter++) begin
            mask = (27'b1 << iter);
            @(posedge clk); #1;
            @(posedge clk); #1;
            observed_val = $signed(sum_out);
            expected_val = (iter % 7) + 1;   // matches b[iter]
            if (observed_val !== expected_val) begin
                $display("TC4 sub-FAIL lane=%0d sum=%0d expected=%0d",
                         iter, observed_val, expected_val);
                errs = errs + 1;
            end
        end
        if (errs === 0) begin
            $display("TC4 PASS: walking-1 mask all 27 lanes independent");
            pass_count = pass_count + 1;
        end else begin
            $display("TC4 FAIL: %0d errors in walking-1 test", errs);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // TC5: s=0.80 sparsity, 100 random vectors, sum must match ref
        // =================================================================
        errs = 0;
        for (iter = 0; iter < 100; iter++) begin
            mask = 0;
            for (k = 0; k < N; k++) begin
                // ~20% active lanes
                if (($random % 100) < 20) mask[k] = 1'b1;
                case ($random % 3)
                    0: a[k] = 4'sb1111;   // -1
                    1: a[k] = 4'sb0000;   // 0
                    2: a[k] = 4'sb0001;   // +1
                    default: a[k] = 0;
                endcase
                b[k] = ($random % 8) - 4;
            end
            @(posedge clk); #1;
            @(posedge clk); #1;
            observed_val = $signed(sum_out);
            ref_acc = 0;
            for (k = 0; k < N; k++) begin
                if (mask[k]) begin
                    ai_ref  = $signed(a[k]);
                    bi_ref  = $signed(b[k]);
                    pi_ref  = ai_ref * bi_ref;
                    ref_acc = ref_acc + pi_ref;
                end
            end
            if (observed_val !== ref_acc) errs = errs + 1;
        end
        if (errs === 0) begin
            $display("TC5 PASS: 100 random s=0.80 sparsity vectors match reference");
            pass_count = pass_count + 1;
        end else begin
            $display("TC5 FAIL: %0d mismatches in 100 random vectors", errs);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // TC6: edge case — mask=all-1 but a=0 → sum must be 0
        // =================================================================
        mask = {N{1'b1}};
        for (k = 0; k < N; k++) begin
            a[k] = 4'sb0000;           // ternary 0 → all products zero
            b[k] = ($random % 8) - 4;  // nonzero b; irrelevant
        end
        @(posedge clk); #1;
        @(posedge clk); #1;
        observed_val = $signed(sum_out);
        if (observed_val === 0) begin
            $display("TC6 PASS: mask=all-1 a=0 => sum=0");
            pass_count = pass_count + 1;
        end else begin
            $display("TC6 FAIL: sum=%0d expected=0", observed_val);
            fail_count = fail_count + 1;
        end

        // =================================================================
        // Summary
        // =================================================================
        $display("---");
        $display("SUMMARY: %0d PASS, %0d FAIL", pass_count, fail_count);
        if (fail_count === 0)
            $display("ALL TESTS PASSED — W40 Lane GG sparse PE mask RTL OK");
        else
            $display("SOME TESTS FAILED");
        $finish;
    end

    // Watchdog
    initial begin
        #1000000;
        $display("TIMEOUT");
        $finish;
    end

endmodule

// phi^2 + phi^-2 = 3 · gamma = phi^-3 · QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · NEVER STOP · DOI 10.5281/zenodo.19227877
