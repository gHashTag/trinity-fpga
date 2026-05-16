// Testbench for stoch_skip_gate.sv
// Wave 44, lane OO, S-188 + S-189
// 7 test cases

`timescale 1ns/1ps

module stoch_skip_gate_tb;

  logic clk;
  logic rst_n;
  logic cos_sim_pass;
  logic skip_compute;

  // Instantiate DUT
  theta_skip_gate_top dut (
    .clk          (clk),
    .rst_n        (rst_n),
    .cos_sim_pass (cos_sim_pass),
    .skip_compute (skip_compute)
  );

  // Clock generation: 1 ns period
  initial clk = 1'b0;
  always #0.5 clk = ~clk;

  // Task: apply one clock edge
  task tick;
    @(posedge clk);
    #0.1;
  endtask

  integer fail_count;

  initial begin
    fail_count = 0;

    // TB1: rst_n=0 => skip_compute must be 0
    rst_n       = 1'b0;
    cos_sim_pass = 1'b1;
    @(posedge clk); #0.1;
    if (skip_compute !== 1'b0) begin
      $display("FAIL TB1: expected skip=0 during reset, got %b", skip_compute);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB1: reset holds skip=0");
    end

    // Deassert reset
    rst_n = 1'b1;
    tick;

    // TB2: cos_pass=0, theta_off=0 => skip=0
    cos_sim_pass = 1'b0;
    // theta_off_phase starts at 0 after reset
    tick;
    if (skip_compute !== 1'b0) begin
      $display("FAIL TB2: expected skip=0 (cos=0, theta_off=0), got %b", skip_compute);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB2: cos=0 theta_off=0 => skip=0");
    end

    // TB3: cos_pass=1, theta_off=0 => skip=0
    cos_sim_pass = 1'b1;
    tick;
    if (skip_compute !== 1'b0) begin
      $display("FAIL TB3: expected skip=0 (cos=1, theta_off=0), got %b", skip_compute);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB3: cos=1 theta_off=0 => skip=0");
    end

    // TB4 and TB5: need to force theta_off_phase=1 via direct force
    // Force internal phase signal to 1 to test OFF-phase behavior
    force dut.u_phase_ctr.phase = 1'b1;
    tick;

    // TB4: cos_pass=0, theta_off=1 => skip=0
    cos_sim_pass = 1'b0;
    tick;
    if (skip_compute !== 1'b0) begin
      $display("FAIL TB4: expected skip=0 (cos=0, theta_off=1), got %b", skip_compute);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB4: cos=0 theta_off=1 => skip=0");
    end

    // TB5: cos_pass=1, theta_off=1 => skip=1
    cos_sim_pass = 1'b1;
    tick;
    if (skip_compute !== 1'b1) begin
      $display("FAIL TB5: expected skip=1 (cos=1, theta_off=1), got %b", skip_compute);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB5: cos=1 theta_off=1 => skip=1");
    end

    // Release force
    release dut.u_phase_ctr.phase;

    // TB6: clock several cycles to observe theta_off toggling
    // Reset and run until first toggle
    rst_n = 1'b0;
    repeat(2) tick;
    rst_n = 1'b1;
    cos_sim_pass = 1'b1;
    begin
      logic prev_theta;
      integer toggle_count;
      integer i;
      prev_theta   = 1'b0;
      toggle_count = 0;
      // Run enough cycles to see multiple toggles using a shortened HALF_PERIOD
      // Force cnt near rollover to observe toggle quickly
      force dut.u_phase_ctr.cnt = 32'd71428569;
      repeat(4) tick;
      release dut.u_phase_ctr.cnt;
      // Check that theta_off_phase toggled at least once
      for (i = 0; i < 5; i++) begin
        if (dut.u_phase_ctr.theta_off_phase !== prev_theta) begin
          toggle_count = toggle_count + 1;
          prev_theta = dut.u_phase_ctr.theta_off_phase;
        end
        tick;
      end
      if (toggle_count >= 1) begin
        $display("PASS TB6: theta_off_phase toggled %0d time(s)", toggle_count);
      end else begin
        $display("FAIL TB6: theta_off_phase did not toggle");
        fail_count = fail_count + 1;
      end
    end

    // TB7: assert HALF_PERIOD_CYCLES parameter value
    if (dut.u_phase_ctr.HALF_PERIOD_CYCLES !== 32'd71428571) begin
      $display("FAIL TB7: HALF_PERIOD_CYCLES mismatch, got %0d", dut.u_phase_ctr.HALF_PERIOD_CYCLES);
      fail_count = fail_count + 1;
    end else begin
      $display("PASS TB7: HALF_PERIOD_CYCLES == 71428571");
    end

    // Summary
    if (fail_count == 0) begin
      $display("ALL TESTS PASSED (7/7)");
    end else begin
      $display("FAILED: %0d test(s) failed", fail_count);
    end

    $finish;
  end

endmodule
