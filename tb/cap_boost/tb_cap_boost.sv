// SPDX-License-Identifier: Apache-2.0
// Wave-49 Lane UU — CAP-BOOST controller testbench (iverilog 12 compatible)
//
// 15 TB checks for OP_CAP_BOOST = 0xF3 (γ³ capacitive decoupling burst).
//
// anchor: phi^2 + phi^-2 = 3 · gamma^3 = phi^-9
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`timescale 1ns/1ps
`default_nettype none

module tb_cap_boost;

  reg        clk;
  reg        rst_n;
  reg [7:0]  opcode;
  reg [7:0]  activity_factor;

  wire        cap_boost_active;
  wire        burst_enable_out;
  wire [6:0]  delta_c_bps;
  wire        delta_c_in_band;
  wire [9:0]  didt_margin_bps;
  wire [9:0]  droop_supp_bps;
  wire        didt_margin_ok;
  wire        droop_supp_ok;
  wire        cap_area_ok;
  wire        fclk_impact_ok;
  wire        tops_w_lift_ok;
  wire        bank_extension_ok;
  wire        burst_locked;

  cap_boost_controller u_cb (
    .clk              (clk),
    .rst_n            (rst_n),
    .opcode           (opcode),
    .activity_factor  (activity_factor),
    .cap_boost_active (cap_boost_active),
    .burst_enable_out (burst_enable_out),
    .delta_c_bps      (delta_c_bps),
    .delta_c_in_band  (delta_c_in_band),
    .didt_margin_bps  (didt_margin_bps),
    .droop_supp_bps   (droop_supp_bps),
    .didt_margin_ok   (didt_margin_ok),
    .droop_supp_ok    (droop_supp_ok),
    .cap_area_ok      (cap_area_ok),
    .fclk_impact_ok   (fclk_impact_ok),
    .tops_w_lift_ok   (tops_w_lift_ok),
    .bank_extension_ok(bank_extension_ok),
    .burst_locked     (burst_locked)
  );

  // 100 MHz clock
  always #5 clk = ~clk;

  integer pass_cnt;
  integer fail_cnt;

  task check(input [255:0] label, input cond);
    begin
      if (cond) begin
        pass_cnt = pass_cnt + 1;
        $display("PASS %0s", label);
      end else begin
        fail_cnt = fail_cnt + 1;
        $display("FAIL %0s", label);
      end
    end
  endtask

  initial begin
    clk = 0;
    rst_n = 0;
    opcode = 8'h00;
    activity_factor = 8'd0;
    pass_cnt = 0;
    fail_cnt = 0;

    #20 rst_n = 1;
    #10;

    // T01: opcode != 0xF3 → not active
    opcode = 8'h00;
    activity_factor = 8'd200;
    #20;
    check("T01_idle_when_opcode_zero",
          (cap_boost_active == 1'b0) && (burst_enable_out == 1'b0)
          && (delta_c_bps == 7'd0));

    // T02: opcode = 0xF3, activity high → active + burst_enable
    opcode = 8'hF3;
    activity_factor = 8'd200;
    #20;
    check("T02_active_when_opcode_0xF3_and_high_activity",
          (cap_boost_active == 1'b1) && (burst_enable_out == 1'b1));

    // T03: delta_c_bps = 81 when armed
    check("T03_delta_c_bps_is_81", (delta_c_bps == 7'd81));

    // T04: delta_c_in_band asserted
    check("T04_delta_c_in_band_asserted", delta_c_in_band == 1'b1);

    // T05: didt_margin_bps = 600 when armed
    check("T05_didt_margin_is_600", didt_margin_bps == 10'd600);

    // T06: didt_margin_ok asserted
    check("T06_didt_margin_ok_asserted", didt_margin_ok == 1'b1);

    // T07: droop_supp_bps = 400 when armed
    check("T07_droop_supp_is_400", droop_supp_bps == 10'd400);

    // T08: droop_supp_ok asserted
    check("T08_droop_supp_ok_asserted", droop_supp_ok == 1'b1);

    // T09: cap_area_ok asserted (R18 iso-area)
    check("T09_cap_area_ok_asserted", cap_area_ok == 1'b1);

    // T10: fclk_impact_ok asserted (≤2%)
    check("T10_fclk_impact_ok_asserted", fclk_impact_ok == 1'b1);

    // T11: tops_w_lift_ok asserted (8000 ≥ 7581)
    check("T11_tops_w_lift_ok_asserted", tops_w_lift_ok == 1'b1);

    // T12: bank_extension_ok asserted
    check("T12_bank_extension_ok_asserted", bank_extension_ok == 1'b1);

    // T13: burst_locked after settle window
    #100;
    check("T13_burst_locked_after_settle", burst_locked == 1'b1);

    // T14: opcode = 0xF3 but activity low → no burst
    activity_factor = 8'd50;
    #20;
    check("T14_no_burst_when_activity_low",
          (cap_boost_active == 1'b1) && (burst_enable_out == 1'b0)
          && (delta_c_bps == 7'd0));

    // T15: distinctness from W47/W48 opcodes (controller refuses 0xF1, 0xF2)
    opcode = 8'hF1;
    activity_factor = 8'd200;
    #20;
    check("T15a_not_active_on_OP_RBB", cap_boost_active == 1'b0);

    opcode = 8'hF2;
    #20;
    check("T15b_not_active_on_OP_FBB_ACTIVE", cap_boost_active == 1'b0);

    opcode = 8'hF3;
    #20;
    check("T15c_active_on_OP_CAP_BOOST", cap_boost_active == 1'b1);

    // Summary
    #10;
    $display("==== CAP-BOOST TB SUMMARY ====");
    $display("PASS: %0d", pass_cnt);
    $display("FAIL: %0d", fail_cnt);
    if (fail_cnt == 0) begin
      $display("RESULT: ALL_PASS");
    end else begin
      $display("RESULT: FAIL");
    end
    $finish;
  end

  // Watchdog
  initial begin
    #5000;
    $display("WATCHDOG_TIMEOUT");
    $finish;
  end

endmodule

`default_nettype wire
