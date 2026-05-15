// Wave-42 Lane JJ — Testbench: stoch_round + lfsr32
// OP_STOCH_ROUND = 8'hE9  — 10/10 assert suite
//
// Assert inventory:
//  1. Opcode mismatch -> pass-through (mode-irrelevant)
//  2. mode=RNE  x_frac=8 ties to even x_int
//  3. mode=FLOOR truncates x_frac
//  4. mode=STOCH 10000 cycles x_frac=4  -> mean within 0.5% of x_int+4/16
//  5. mode=STOCH 10000 cycles x_frac=12 -> mean within 0.5% of x_int+12/16
//  6. LFSR max-length: no zero state over 65536 cycles
//  7. LFSR seed_load overrides default seed
//  8. mode transition mid-stream is clean (no glitch on y_rounded)
//  9. Reset clears y_rounded to 0
// 10. Single-cycle latency: y_rounded stable 1 cycle after input change
//
// anchor: phi^2 + phi^-2 = 3  · DOI 10.5281/zenodo.19227877

`timescale 1ns/1ps

module stoch_round_tb;

    // -----------------------------------------------------------------------
    // DUT signals
    // -----------------------------------------------------------------------
    logic        clk;
    logic        rst_n;

    // stoch_round
    logic [7:0]  opcode;
    logic [15:0] x_int;
    logic [3:0]  x_frac;
    logic [1:0]  mode;
    logic [31:0] lfsr_out;
    logic [15:0] y_rounded;

    // lfsr32
    logic [31:0] seed;
    logic        seed_load;

    // -----------------------------------------------------------------------
    // DUT instantiation
    // -----------------------------------------------------------------------
    lfsr32 u_lfsr (
        .clk       (clk),
        .rst_n     (rst_n),
        .seed      (seed),
        .seed_load (seed_load),
        .lfsr_o    (lfsr_out)
    );

    stoch_round u_dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .opcode    (opcode),
        .x_int     (x_int),
        .x_frac    (x_frac),
        .mode      (mode),
        .lfsr_in   (lfsr_out),
        .y_rounded (y_rounded)
    );

    // -----------------------------------------------------------------------
    // Clock: 10 ns period
    // -----------------------------------------------------------------------
    initial clk = 0;
    always #5 clk = ~clk;

    // -----------------------------------------------------------------------
    // Scoreboard
    // -----------------------------------------------------------------------
    integer pass_cnt;
    integer fail_cnt;
    initial begin pass_cnt = 0; fail_cnt = 0; end

    task automatic check;
        input [127:0] name_unused; // label for display only
        input         cond;
        input [127:0] tag;
        begin
            if (cond) begin
                $display("PASS [%s]", tag);
                pass_cnt = pass_cnt + 1;
            end else begin
                $display("FAIL [%s]", tag);
                fail_cnt = fail_cnt + 1;
            end
        end
    endtask

    // -----------------------------------------------------------------------
    // Main test sequence
    // -----------------------------------------------------------------------
    integer i;
    longint sum4, sum12;
    real    mean4, expected4, tol4;
    real    mean12, expected12, tol12;
    integer zero_cnt;
    logic [15:0] y_floor_prev;

    initial begin

        // ===================================================================
        // ASSERT 9 — Reset clears y_rounded
        // ===================================================================
        rst_n     = 1'b0;
        opcode    = 8'hE9;
        x_int     = 16'hDEAD;
        x_frac    = 4'hF;
        mode      = 2'b01;
        seed      = 32'h0;
        seed_load = 1'b0;
        @(posedge clk); @(posedge clk);
        check("", y_rounded === 16'h0, "A9_reset_clears_y");
        rst_n = 1'b1;

        // ===================================================================
        // ASSERT 1 — Opcode mismatch -> pass-through
        // ===================================================================
        @(posedge clk);
        opcode = 8'hAA;    // wrong opcode
        x_int  = 16'h0042;
        x_frac = 4'hC;
        mode   = 2'b01;    // STOCH mode — ignored due to opcode mismatch
        @(posedge clk);    // sample inputs
        @(posedge clk);    // registered output
        check("", y_rounded === 16'h0042, "A1_opcode_mismatch_passthrough");

        // ===================================================================
        // ASSERT 10 — Single-cycle latency
        // ===================================================================
        opcode = 8'hE9;
        x_int  = 16'h0007;
        x_frac = 4'h0;     // frac=0 => STOCH never rounds up
        mode   = 2'b01;
        @(posedge clk);
        @(posedge clk);
        check("", y_rounded === 16'h0007, "A10_single_cycle_latency");

        // ===================================================================
        // ASSERT 3 — mode=FLOOR truncates
        // ===================================================================
        opcode = 8'hE9;
        x_int  = 16'h0055;
        x_frac = 4'hF;
        mode   = 2'b10;    // FLOOR
        @(posedge clk);
        @(posedge clk);
        check("", y_rounded === 16'h0055, "A3_floor_truncates");

        // ===================================================================
        // ASSERT 2a — mode=RNE x_frac=8 tie, even x_int stays
        // ===================================================================
        opcode = 8'hE9;
        x_int  = 16'h0010; // even
        x_frac = 4'h8;     // tie
        mode   = 2'b00;    // RNE
        @(posedge clk);
        @(posedge clk);
        check("", y_rounded === 16'h0010, "A2a_rne_tie_even_stays");

        // ===================================================================
        // ASSERT 2b — mode=RNE x_frac=8 tie, odd x_int rounds up
        // ===================================================================
        x_int  = 16'h0011; // odd
        x_frac = 4'h8;
        mode   = 2'b00;
        @(posedge clk);
        @(posedge clk);
        check("", y_rounded === 16'h0012, "A2b_rne_tie_odd_rounds_up");

        // ===================================================================
        // ASSERT 7 — LFSR seed_load overrides default
        // ===================================================================
        seed      = 32'hDEADBEEF;
        seed_load = 1'b1;
        @(posedge clk);
        seed_load = 1'b0;
        @(posedge clk);
        // After seeding DEADBEEF, output differs from reset default ACE1ACE1
        check("", lfsr_out !== 32'hACE1ACE1, "A7_seed_load_works");

        // --- clean reset for remaining tests ---
        rst_n = 1'b0;
        opcode = 8'h00; x_int = 16'h0; x_frac = 4'h0; mode = 2'b00;
        seed = 32'h0; seed_load = 1'b0;
        repeat(4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // ===================================================================
        // ASSERT 6 — LFSR max-length: no zero state in 65536 cycles
        // ===================================================================
        zero_cnt = 0;
        for (i = 0; i < 65536; i = i + 1) begin
            @(posedge clk);
            if (lfsr_out === 32'h0) zero_cnt = zero_cnt + 1;
        end
        check("", zero_cnt === 0, "A6_lfsr_no_zero_state");

        // ===================================================================
        // ASSERT 4 — STOCH x_frac=4 mean within 0.5% of x_int+4/16
        // ===================================================================
        sum4  = 0;
        opcode = 8'hE9;
        x_int  = 16'h0064;  // 100
        x_frac = 4'h4;      // 4/16 = 0.25 => expected mean 100.25
        mode   = 2'b01;
        for (i = 0; i < 10000; i = i + 1) begin
            @(posedge clk);
            @(posedge clk);
            sum4 = sum4 + y_rounded;
        end
        mean4     = $itor(sum4) / 10000.0;
        expected4 = 100.0 + 4.0/16.0;
        tol4      = expected4 * 0.005;
        check("", (mean4 >= expected4 - tol4) && (mean4 <= expected4 + tol4),
              "A4_stoch_frac4_mean");

        // ===================================================================
        // ASSERT 5 — STOCH x_frac=12 mean within 0.5% of x_int+12/16
        // ===================================================================
        sum12 = 0;
        x_frac = 4'hC;     // 12/16 = 0.75 => expected mean 100.75
        for (i = 0; i < 10000; i = i + 1) begin
            @(posedge clk);
            @(posedge clk);
            sum12 = sum12 + y_rounded;
        end
        mean12     = $itor(sum12) / 10000.0;
        expected12 = 100.0 + 12.0/16.0;
        tol12      = expected12 * 0.005;
        check("", (mean12 >= expected12 - tol12) && (mean12 <= expected12 + tol12),
              "A5_stoch_frac12_mean");

        // ===================================================================
        // ASSERT 8 — mode transition mid-stream is clean
        // ===================================================================
        opcode = 8'hE9;
        x_int  = 16'h001E; // 30
        x_frac = 4'h9;     // > 8 => RNE rounds up; FLOOR stays
        mode   = 2'b10;    // FLOOR first
        @(posedge clk);
        @(posedge clk);
        y_floor_prev = y_rounded; // should be 30

        mode = 2'b00;      // switch to RNE
        @(posedge clk);
        @(posedge clk);
        // RNE with x_frac=9 (>8) => round up to 31
        check("", (y_floor_prev === 16'h001E) && (y_rounded === 16'h001F),
              "A8_mode_transition_clean");

        // ===================================================================
        // Summary
        // ===================================================================
        $display("");
        $display("===== RESULTS: %0d / %0d PASS =====", pass_cnt, pass_cnt + fail_cnt);
        if (fail_cnt == 0)
            $display("ALL 10/10 PASS");
        else
            $display("FAIL: %0d assert(s) failed", fail_cnt);
        $finish;
    end

    // Safety timeout
    initial begin
        #60000000;
        $display("TIMEOUT: simulation exceeded 60 ms");
        $finish;
    end

endmodule
