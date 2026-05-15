// Wave-41 Lane HH — sparse_gate testbench
// 10 test groups covering all spec assertions
// Sacred opcode OP_SPARSE_SKIP = 8'hE8
// anchor: phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877
`timescale 1ns/1ps

module sparse_gate_tb;

    // DUT signals
    logic        clk;
    logic        rst_n;
    logic [7:0]  opcode;
    logic [15:0] activation;
    logic [7:0]  tau;
    logic        topk_keep;
    logic        skip_o;
    logic        mac_clk_en;

    // Instantiate DUT
    sparse_gate u_dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .opcode     (opcode),
        .activation (activation),
        .tau        (tau),
        .topk_keep  (topk_keep),
        .skip_o     (skip_o),
        .mac_clk_en (mac_clk_en)
    );

    // Clock: 10 ns period
    initial clk = 0;
    always #5 clk = ~clk;

    // Test bookkeeping
    int pass_count;
    int fail_count;
    int sub_fail;

    task sub_assert(input [63:0] got, input [63:0] exp, input string msg);
        if (got !== exp) begin
            $display("    FAIL: %s — got=%0h exp=%0h", msg, got, exp);
            sub_fail++;
        end else begin
            $display("    ok: %s (got=%0h)", msg, got);
        end
    endtask

    task test_result(input string name);
        if (sub_fail == 0) begin
            $display("  PASS: %s", name);
            pass_count++;
        end else begin
            $display("  FAIL: %s (%0d sub-failures)", name, sub_fail);
            fail_count++;
        end
        sub_fail = 0;
    endtask

    // Advance N clock edges and settle
    task clk_tick(input int n);
        repeat(n) @(posedge clk);
        #1;
    endtask

    // Apply inputs and advance one clock; outputs sampled after posedge
    task apply(
        input [7:0]  op,
        input [15:0] act,
        input [7:0]  t,
        input        tk
    );
        opcode     = op;
        activation = act;
        tau        = t;
        topk_keep  = tk;
        clk_tick(1);
    endtask

    // ---------------------------------------------------------------
    initial begin
        pass_count = 0;
        fail_count = 0;
        sub_fail   = 0;

        // Initial state
        rst_n      = 1'b0;
        opcode     = 8'h00;
        activation = 16'h0000;
        tau        = 8'h00;
        topk_keep  = 1'b0;
        clk_tick(3);
        rst_n = 1'b1;
        clk_tick(1);

        // -----------------------------------------------------------
        // TEST 1: opcode mismatch → skip_o=0 regardless of activation
        // Use opcode=0x00, |act|=10 << tau=20 (would skip if opcode matched)
        $display("TEST 1: opcode mismatch → skip=0");
        apply(8'h00, 16'h000A, 8'h14, 1'b0);   // opcode wrong
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "opcode=0x00 skip_o=0");
        apply(8'hAA, 16'h0001, 8'hFF, 1'b0);   // opcode 0xAA wrong
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "opcode=0xAA skip_o=0");
        apply(8'hE7, 16'h0001, 8'hFF, 1'b0);   // opcode 0xE7 (one off) wrong
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "opcode=0xE7 skip_o=0");
        test_result("TEST1 opcode_mismatch");

        // -----------------------------------------------------------
        // TEST 2: |act| < tau, topk_keep=0 → skip_o=1
        // tau=8'h05 → exp=3'b000, mantissa=5'b00101 → tau_decoded=5 ; act_mag=3 < 5
        $display("TEST 2: |act|<tau, topk_keep=0 → skip=1");
        apply(8'hE8, 16'h0003, 8'h05, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b1}, "skip_o=1 when |act|<tau");
        test_result("TEST2 skip_when_below_tau");

        // -----------------------------------------------------------
        // TEST 3: |act| >= tau → skip_o=0
        // tau=8'h05 → tau_decoded=5; act_mag=5 (equal, not less)
        $display("TEST 3: |act|>=tau → skip=0");
        apply(8'hE8, 16'h0005, 8'h05, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "skip_o=0 when |act|==tau");
        // act_mag=10 > tau_decoded=5
        apply(8'hE8, 16'h000A, 8'h05, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "skip_o=0 when |act|>tau");
        test_result("TEST3 no_skip_above_tau");

        // -----------------------------------------------------------
        // TEST 4: topk_keep=1 forces skip_o=0 even if |act|<tau
        // tau_decoded=5, act_mag=2 (would skip) but topk_keep=1
        $display("TEST 4: topk_keep=1 forces skip=0");
        apply(8'hE8, 16'h0002, 8'h05, 1'b1);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "topk_keep=1 skip_o=0");
        test_result("TEST4 topk_keep_override");

        // -----------------------------------------------------------
        // TEST 5: Negative activation magnitude correctness
        // activation bit[15]=1 (sign), bits[14:0]=magnitude
        // activation=16'h8003 → sign=1, mag=3; tau_decoded=5 → |act|=3 < 5 → skip=1
        $display("TEST 5: negative activation magnitude");
        apply(8'hE8, 16'h8003, 8'h05, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b1}, "neg sign |act|=3 < tau=5 skip=1");
        // activation=16'h800A → sign=1, mag=10; tau_decoded=5 → |act|=10 >= 5 → skip=0
        apply(8'hE8, 16'h800A, 8'h05, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "neg sign |act|=10 >= tau=5 skip=0");
        test_result("TEST5 negative_activation");

        // -----------------------------------------------------------
        // TEST 6: tau=0 corner case
        // tau=8'h00 → tau_decoded=0; |act|=0 < 0 is false → skip=0
        // (nothing is less than zero, so no skipping ever at tau=0)
        $display("TEST 6: tau=0 corner case");
        apply(8'hE8, 16'h0000, 8'h00, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "tau=0 act=0: skip=0");
        apply(8'hE8, 16'h0001, 8'h00, 1'b0);
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "tau=0 act=1: skip=0");
        test_result("TEST6 tau_zero_corner");

        // -----------------------------------------------------------
        // TEST 7: mac_clk_en == !skip_o invariant
        $display("TEST 7: mac_clk_en == !skip_o invariant");
        // skip=1 case
        apply(8'hE8, 16'h0001, 8'h05, 1'b0);
        sub_assert({63'b0, mac_clk_en}, {63'b0, ~skip_o}, "mac_clk_en==!skip_o (skip=1)");
        // skip=0 case
        apply(8'hE8, 16'h000F, 8'h05, 1'b0);
        sub_assert({63'b0, mac_clk_en}, {63'b0, ~skip_o}, "mac_clk_en==!skip_o (skip=0)");
        // opcode mismatch (skip=0)
        apply(8'h00, 16'h0001, 8'h05, 1'b0);
        sub_assert({63'b0, mac_clk_en}, {63'b0, ~skip_o}, "mac_clk_en==!skip_o (opcode mismatch)");
        test_result("TEST7 mac_clk_en_invariant");

        // -----------------------------------------------------------
        // TEST 8: sparsity_cnt increments only on skip cycles
        // Force a known reset; count skips over 3 cycles
        $display("TEST 8: sparsity_cnt increments only on skip cycles");
        begin
            logic [31:0] cnt_before, cnt_after;
            // Reset to get clean counter
            rst_n = 1'b0;
            clk_tick(2);
            rst_n = 1'b1;
            clk_tick(1);
            cnt_before = u_dut.sparsity_cnt;
            sub_assert({32'b0, cnt_before}, {64'b0}, "sparsity_cnt=0 after reset");
            // 3 skip cycles: act=1, tau=5, opcode=0xE8
            apply(8'hE8, 16'h0001, 8'h05, 1'b0);
            apply(8'hE8, 16'h0001, 8'h05, 1'b0);
            apply(8'hE8, 16'h0001, 8'h05, 1'b0);
            cnt_after = u_dut.sparsity_cnt;
            sub_assert({32'b0, cnt_after}, {32'b0, 32'd3}, "sparsity_cnt=3 after 3 skips");
            // 2 non-skip cycles (act>=tau)
            apply(8'hE8, 16'h000A, 8'h05, 1'b0);
            apply(8'hE8, 16'h000A, 8'h05, 1'b0);
            sub_assert({32'b0, u_dut.sparsity_cnt}, {32'b0, 32'd3}, "sparsity_cnt unchanged on no-skip");
        end
        test_result("TEST8 sparsity_cnt");

        // -----------------------------------------------------------
        // TEST 9: Reset clears sparsity_cnt
        $display("TEST 9: Reset clears sparsity_cnt");
        // Accumulate some skips
        apply(8'hE8, 16'h0001, 8'h05, 1'b0);
        apply(8'hE8, 16'h0001, 8'h05, 1'b0);
        // Now reset — hold rst_n low and set non-skip inputs so on release no
        // stale skip_comb propagates into the registered outputs
        rst_n      = 1'b0;
        opcode     = 8'h00;   // non-skip opcode during reset
        activation = 16'h0000;
        tau        = 8'h00;
        topk_keep  = 1'b0;
        clk_tick(2);
        // Verify async reset took effect immediately
        sub_assert({32'b0, u_dut.sparsity_cnt}, {64'b0}, "sparsity_cnt=0 after async reset");
        rst_n = 1'b1;
        clk_tick(2);   // two cycles: one for FF to come out of reset, one to settle outputs
        sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "skip_o=0 after reset");
        sub_assert({63'b0, mac_clk_en}, {63'b0, 1'b1}, "mac_clk_en=1 after reset");
        test_result("TEST9 reset_clears_counter");

        // -----------------------------------------------------------
        // TEST 10: Single-cycle latency — output reflects input after exactly 1 posedge
        // Apply stimulus, then check output at next rising edge
        $display("TEST 10: Single-cycle latency (no pipeline)");
        begin
            // Cycle A: apply skip-triggering input, read output after 1 clk
            opcode     = 8'hE8;
            activation = 16'h0002;   // mag=2
            tau        = 8'h05;      // tau_decoded=5, 2<5 → skip
            topk_keep  = 1'b0;
            @(posedge clk); #1;
            sub_assert({63'b0, skip_o}, {63'b0, 1'b1}, "latency=1: skip=1 one cycle after input");
            // Cycle B: immediately switch to non-skip input, check after 1 clk
            opcode     = 8'hE8;
            activation = 16'h000A;   // mag=10 >= 5 → no skip
            tau        = 8'h05;
            topk_keep  = 1'b0;
            @(posedge clk); #1;
            sub_assert({63'b0, skip_o}, {63'b0, 1'b0}, "latency=1: skip=0 one cycle after no-skip input");
        end
        test_result("TEST10 single_cycle_latency");

        // -----------------------------------------------------------
        $display("ALL %0d/%0d PASS", pass_count, 10);
        if (fail_count > 0)
            $display("FAILURES: %0d", fail_count);
        $finish;
    end

endmodule
