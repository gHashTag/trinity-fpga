// SPDX-License-Identifier: Apache-2.0
// Wave-48 Lane TT — Testbench for fbb_active_controller (0xF2)
//
// phi^2 + phi^-2 = 3 (three-path witness)
// DOI 10.5281/zenodo.19227877
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_fbb_active_dyn;

    logic        clk;
    logic        rst_n;
    logic [7:0]  op_in;
    logic        active_path;
    logic [7:0]  obs_v_bs_decimv;
    logic [10:0] obs_delay_red_bps;
    logic [10:0] obs_leak_ovh_bps;
    logic [10:0] obs_fclk_scale_bps;
    logic        fbb_enable;
    logic        policy_ok;

    wire         vbs_rail_en;
    wire  [7:0]  vbs_mag_decimv;

    // DUTs
    fbb_active_controller dut_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .op_in(op_in),
        .active_path_sensitised(active_path),
        .obs_v_bs_decimv(obs_v_bs_decimv),
        .obs_delay_red_bps(obs_delay_red_bps),
        .obs_leak_ovh_bps(obs_leak_ovh_bps),
        .obs_fclk_scale_bps(obs_fclk_scale_bps),
        .fbb_enable(fbb_enable),
        .policy_ok(policy_ok)
    );

    body_bias_active_gen dut_gen (
        .clk(clk),
        .rst_n(rst_n),
        .active_path(active_path),
        .vbs_rail_en(vbs_rail_en),
        .vbs_mag_decimv(vbs_mag_decimv)
    );

    // Clock
    initial clk = 0;
    always #5 clk = ~clk; // 100 MHz

    int errors = 0;
    int passes = 0;
    task check(input string label, input bit cond);
        if (cond) begin
            $display("[PASS] %s", label);
            passes++;
        end else begin
            $display("[FAIL] %s", label);
            errors++;
        end
    endtask

    initial begin
        // Reset
        rst_n = 0;
        op_in = 8'h00;
        active_path = 0;
        obs_v_bs_decimv = 0;
        obs_delay_red_bps = 0;
        obs_leak_ovh_bps = 0;
        obs_fclk_scale_bps = 0;
        #20;
        rst_n = 1;
        #10;

        // ── Test 1: disabled when opcode mismatch ────────────────
        op_in = 8'hF1; // RBB, not FBB_ACTIVE
        active_path = 1;
        @(posedge clk); @(posedge clk);
        check("disabled_under_RBB_opcode", fbb_enable == 1'b0);

        // ── Test 2: disabled when path inactive ──────────────────
        op_in = 8'hF2;
        active_path = 0;
        @(posedge clk); @(posedge clk);
        check("disabled_when_path_inactive", fbb_enable == 1'b0);

        // ── Test 3: enabled at canonical operating point ─────────
        op_in = 8'hF2;
        active_path = 1;
        obs_v_bs_decimv    = 8'd25;   // +2.5 mV
        obs_delay_red_bps  = 11'd1200; // 12%
        obs_leak_ovh_bps   = 11'd600;  // 6% (<= 8% cap)
        obs_fclk_scale_bps = 11'd400;  // 4% (<= 6% cap)
        @(posedge clk); @(posedge clk); @(posedge clk);
        check("enabled_at_canonical_OP", fbb_enable == 1'b1);
        check("policy_ok_at_canonical_OP", policy_ok == 1'b1);
        check("rail_enabled_when_path_active", vbs_rail_en == 1'b1);
        check("rail_magnitude_canonical_25dmv", vbs_mag_decimv == 8'd25);

        // ── Test 4: V_BS below band ──────────────────────────────
        obs_v_bs_decimv = 8'd9; // < V_BS_DECIMV_LO=10
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_vbs_below_band", policy_ok == 1'b0);

        // ── Test 5: V_BS above band ──────────────────────────────
        obs_v_bs_decimv = 8'd51; // > V_BS_DECIMV_HI=50
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_vbs_above_band", policy_ok == 1'b0);

        // ── Test 6: V_BS upper edge valid ────────────────────────
        obs_v_bs_decimv = 8'd50;
        @(posedge clk); @(posedge clk);
        check("policy_ok_at_vbs_upper_edge", policy_ok == 1'b1);

        // ── Test 7: V_BS lower edge valid ────────────────────────
        obs_v_bs_decimv = 8'd10;
        @(posedge clk); @(posedge clk);
        check("policy_ok_at_vbs_lower_edge", policy_ok == 1'b1);

        // ── Test 8: delay reduction below band ────────────────────
        obs_v_bs_decimv = 8'd25;
        obs_delay_red_bps = 11'd799; // < 800
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_delay_red_below_band", policy_ok == 1'b0);

        // ── Test 9: delay reduction above band ────────────────────
        obs_delay_red_bps = 11'd1801; // > 1800
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_delay_red_above_band", policy_ok == 1'b0);

        // ── Test 10: delay reduction at upper edge ────────────────
        obs_delay_red_bps = 11'd1800;
        @(posedge clk); @(posedge clk);
        check("policy_ok_at_delay_red_upper_edge", policy_ok == 1'b1);

        // ── Test 11: leak overhead above cap ──────────────────────
        obs_delay_red_bps = 11'd1200;
        obs_leak_ovh_bps = 11'd801; // > 800
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_leak_above_cap", policy_ok == 1'b0);

        // ── Test 12: leak overhead at cap ─────────────────────────
        obs_leak_ovh_bps = 11'd800;
        @(posedge clk); @(posedge clk);
        check("policy_ok_at_leak_cap_edge", policy_ok == 1'b1);

        // ── Test 13: f_clk scaling above cap ──────────────────────
        obs_leak_ovh_bps = 11'd600;
        obs_fclk_scale_bps = 11'd601; // > 600 cap
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_fclk_above_cap", policy_ok == 1'b0);

        // ── Test 14: net delay save below floor ───────────────────
        obs_fclk_scale_bps = 11'd401; // 1200 - 401 = 799 < 800 floor
        @(posedge clk); @(posedge clk);
        check("policy_fails_when_net_save_below_floor", policy_ok == 1'b0);

        // ── Test 15: cross-wave distinctness from W47 RBB ─────────
        op_in = 8'hF1;
        @(posedge clk); @(posedge clk);
        check("distinct_from_RBB_opcode_disables_FBB", fbb_enable == 1'b0);

        // Report
        $display("======================================");
        $display("FBB-ACTIVE TB: %0d PASS / %0d FAIL", passes, errors);
        $display("phi^2 + phi^-2 = 3 (three-path witness)");
        $display("======================================");
        if (errors == 0) $display("[SUMMARY] ALL TESTS PASS");
        else             $display("[SUMMARY] %0d TEST(S) FAILED", errors);
        $finish;
    end

endmodule

`default_nettype wire
