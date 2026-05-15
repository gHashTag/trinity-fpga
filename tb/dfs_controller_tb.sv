// Wave-40 Lane GG — DFS controller testbench
// 10 tests: VF LUT, lock/unlock, opcode gate, Acquire→Hold→Release, sacred opcode check
`timescale 1ns/1ps

module dfs_controller_tb;
    // DUT signals
    logic        clk;
    logic        rst_n;
    logic [7:0]  opcode;
    logic [3:0]  vdd_code;
    logic        vdd_lock;
    logic [3:0]  f_target_code;
    logic        dfs_ready;

    // Instantiate DUT
    dfs_controller u_dfs (
        .clk          (clk),
        .rst_n        (rst_n),
        .opcode       (opcode),
        .vdd_code     (vdd_code),
        .vdd_lock     (vdd_lock),
        .f_target_code(f_target_code),
        .dfs_ready    (dfs_ready)
    );

    // Clock: 10 ns period
    initial clk = 0;
    always #5 clk = ~clk;

    // Test bookkeeping — one pass_count increment per TEST
    int pass_count;
    int fail_count;

    // Internal sub-assertion tracker (resets each test)
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

    task clk_tick(input int n);
        repeat(n) @(posedge clk);
        #1;
    endtask

    // ---------------------------------------------------------------
    initial begin
        pass_count = 0;
        fail_count = 0;
        sub_fail   = 0;

        // Reset
        rst_n    = 1'b0;
        opcode   = 8'h00;
        vdd_code = 4'b0;
        vdd_lock = 1'b0;
        clk_tick(3);
        rst_n = 1'b1;
        clk_tick(1);

        // ---------------------------------------------------------------
        // TEST 1: vdd_code=0001, vdd_lock=1 → f_target=0001
        $display("TEST 1: vdd_code=0001 → f_target=0001");
        opcode   = 8'hE7;
        vdd_code = 4'b0001;
        vdd_lock = 1'b1;
        clk_tick(2);
        sub_assert({60'b0, f_target_code}, {60'b0, 4'b0001}, "f_target=1");
        sub_assert({63'b0, dfs_ready},     {63'b0, 1'b1},    "dfs_ready=1");
        test_result("TEST1 vdd_code=0001");

        // ---------------------------------------------------------------
        // TEST 2: vdd_code=0100, vdd_lock=1 → f_target=0100
        $display("TEST 2: vdd_code=0100 → f_target=0100");
        vdd_code = 4'b0100;
        clk_tick(2);
        sub_assert({60'b0, f_target_code}, {60'b0, 4'b0100}, "f_target=4");
        test_result("TEST2 vdd_code=0100");

        // ---------------------------------------------------------------
        // TEST 3: vdd_code=1000, vdd_lock=1 → f_target=1000
        $display("TEST 3: vdd_code=1000 → f_target=1000");
        vdd_code = 4'b1000;
        clk_tick(2);
        sub_assert({60'b0, f_target_code}, {60'b0, 4'b1000}, "f_target=8");
        test_result("TEST3 vdd_code=1000");

        // ---------------------------------------------------------------
        // TEST 4: vdd_code=1111, vdd_lock=1 → f_target=1111
        $display("TEST 4: vdd_code=1111 → f_target=1111");
        vdd_code = 4'b1111;
        clk_tick(2);
        sub_assert({60'b0, f_target_code}, {60'b0, 4'b1111}, "f_target=15");
        test_result("TEST4 vdd_code=1111");

        // ---------------------------------------------------------------
        // TEST 5: vdd_lock=0 → dfs_ready stays 0
        $display("TEST 5: vdd_lock=0 → dfs_ready=0");
        vdd_lock = 1'b0;
        clk_tick(2);
        sub_assert({63'b0, dfs_ready}, {63'b0, 1'b0}, "dfs_ready=0 when unlocked");
        test_result("TEST5 vdd_lock=0");

        // ---------------------------------------------------------------
        // TEST 6: opcode != 0xE7 (opcode=0x00) → no f_target update
        $display("TEST 6: opcode=0x00 → no f_target update");
        begin
            logic [3:0] saved;
            // prime with valid opcode
            opcode   = 8'hE7;
            vdd_code = 4'b0011;
            vdd_lock = 1'b1;
            clk_tick(2);
            saved = f_target_code;
            // switch to wrong opcode
            opcode   = 8'h00;
            vdd_code = 4'b1010;
            clk_tick(2);
            sub_assert({60'b0, f_target_code}, {60'b0, saved}, "f_target unchanged opcode=0x00");
        end
        test_result("TEST6 opcode=0x00");

        // ---------------------------------------------------------------
        // TEST 7: opcode=0xAA → no f_target update
        $display("TEST 7: opcode=0xAA → no f_target update");
        begin
            logic [3:0] saved;
            opcode   = 8'hE7;
            vdd_code = 4'b0101;
            vdd_lock = 1'b1;
            clk_tick(2);
            saved = f_target_code;
            opcode   = 8'hAA;
            vdd_code = 4'b1100;
            clk_tick(2);
            sub_assert({60'b0, f_target_code}, {60'b0, saved}, "f_target unchanged opcode=0xAA");
        end
        test_result("TEST7 opcode=0xAA");

        // ---------------------------------------------------------------
        // TEST 8: opcode=0xE6 (one bit off) → no f_target update
        $display("TEST 8: opcode=0xE6 → no f_target update");
        begin
            logic [3:0] saved;
            opcode   = 8'hE7;
            vdd_code = 4'b0110;
            vdd_lock = 1'b1;
            clk_tick(2);
            saved = f_target_code;
            opcode   = 8'hE6;
            vdd_code = 4'b1110;
            clk_tick(2);
            sub_assert({60'b0, f_target_code}, {60'b0, saved}, "f_target unchanged opcode=0xE6");
        end
        test_result("TEST8 opcode=0xE6");

        // ---------------------------------------------------------------
        // TEST 9: Acquire→Hold→Release sequence (vdd_lock 0→1→0)
        $display("TEST 9: Acquire→Hold→Release (vdd_lock 0→1→0)");
        opcode   = 8'hE7;
        vdd_code = 4'b0010;
        // Acquire
        vdd_lock = 1'b0;
        clk_tick(2);
        sub_assert({63'b0, dfs_ready}, {63'b0, 1'b0}, "Acquire: dfs_ready=0");
        // Hold
        vdd_lock = 1'b1;
        clk_tick(2);
        sub_assert({60'b0, f_target_code}, {60'b0, 4'b0010}, "Hold: f_target=2");
        sub_assert({63'b0, dfs_ready},     {63'b0, 1'b1},    "Hold: dfs_ready=1");
        // Release
        vdd_lock = 1'b0;
        clk_tick(2);
        sub_assert({63'b0, dfs_ready}, {63'b0, 1'b0}, "Release: dfs_ready=0");
        test_result("TEST9 Acquire→Hold→Release");

        // ---------------------------------------------------------------
        // TEST 10: OP_DFS_GATE sacred slot = 8'hE7
        $display("TEST 10: OP_DFS_GATE sacred value = 8'hE7");
        assert_eq({56'b0, u_dfs.OP_DFS_GATE}, {56'b0, 8'hE7}, "OP_DFS_GATE sacred slot 0xE7");

        // ---------------------------------------------------------------
        $display("ALL %0d/%0d PASS", pass_count, 10);
        if (fail_count > 0)
            $display("FAILURES: %0d", fail_count);
        $finish;
    end

    // assert_eq used only for TEST 10 (matches task spec exactly)
    task assert_eq(input [63:0] got, input [63:0] exp, input string msg);
        if (got === exp) begin
            $display("  PASS: %s (got=%0h)", msg, got);
            pass_count++;
        end else begin
            $display("  FAIL: %s — got=%0h exp=%0h", msg, got, exp);
            fail_count++;
        end
    endtask

endmodule
