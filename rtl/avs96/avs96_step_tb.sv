// Wave 45 lane QQ testbench for avs96_step_top
// 7 test cases: TB1-TB7

`timescale 1ns/1ps

module avs96_step_tb;

  logic       clk;
  logic       rst_n;
  logic [6:0] step_sel;
  logic [6:0] target_step;
  logic       step_request;
  logic [6:0] dac_out;
  logic       step_valid;
  logic [6:0] current_step;
  logic       transition_done;

  avs96_step_top dut (
    .clk             (clk),
    .rst_n           (rst_n),
    .step_sel        (step_sel),
    .target_step     (target_step),
    .step_request    (step_request),
    .dac_out         (dac_out),
    .step_valid      (step_valid),
    .current_step    (current_step),
    .transition_done (transition_done)
  );

  initial clk = 0;
  always #5 clk = ~clk;

  task tick(input int n);
    repeat (n) @(posedge clk);
    #1;
  endtask

  int pass_count;
  int fail_count;

  task check(input string name, input logic got, input logic exp);
    if (got === exp) begin
      $display("PASS %s", name);
      pass_count++;
    end else begin
      $display("FAIL %s: got=%0b exp=%0b", name, got, exp);
      fail_count++;
    end
  endtask

  task check7(input string name, input logic [6:0] got, input logic [6:0] exp);
    if (got === exp) begin
      $display("PASS %s", name);
      pass_count++;
    end else begin
      $display("FAIL %s: got=%0d exp=%0d", name, got, exp);
      fail_count++;
    end
  endtask

  initial begin
    pass_count   = 0;
    fail_count   = 0;
    rst_n        = 1'b0;
    step_sel     = 7'd0;
    target_step  = 7'd0;
    step_request = 1'b0;

    // TB1: reset asserted -> dac_out=0, step_valid=0
    tick(2);
    check7("TB1_dac_out",    dac_out,    7'd0);
    check("TB1_step_valid",  step_valid, 1'b0);

    // Release reset
    rst_n = 1'b1;
    tick(1);

    // TB2: step_sel=0 -> dac_out=0, step_valid=1
    step_sel = 7'd0;
    tick(1);
    check7("TB2_dac_out",    dac_out,    7'd0);
    check("TB2_step_valid",  step_valid, 1'b1);

    // TB3: step_sel=95 -> dac_out=95, step_valid=1
    step_sel = 7'd95;
    tick(1);
    check7("TB3_dac_out",    dac_out,    7'd95);
    check("TB3_step_valid",  step_valid, 1'b1);

    // TB4: step_sel=96 -> dac_out=0, step_valid=0 (out of range)
    step_sel = 7'd96;
    tick(1);
    check7("TB4_dac_out",    dac_out,    7'd0);
    check("TB4_step_valid",  step_valid, 1'b0);

    // TB5: vdd_step_controller ramp 0->3 over 3 clocks
    rst_n        = 1'b0;
    target_step  = 7'd0;
    step_request = 1'b0;
    tick(2);
    rst_n        = 1'b1;
    tick(1);
    target_step  = 7'd3;
    step_request = 1'b1;
    tick(1); check7("TB5_step1", current_step, 7'd1);
    tick(1); check7("TB5_step2", current_step, 7'd2);
    tick(1); check7("TB5_step3", current_step, 7'd3);

    // TB6: vdd_step_controller ramp 3->0 over 3 clocks
    target_step = 7'd0;
    tick(1); check7("TB6_step1", current_step, 7'd2);
    tick(1); check7("TB6_step2", current_step, 7'd1);
    tick(1); check7("TB6_step3", current_step, 7'd0);

    // TB7: transition_done asserted when current_step == target_step
    target_step = 7'd0;
    tick(1);
    check("TB7_transition_done", transition_done, 1'b1);

    $display("Results: %0d passed, %0d failed", pass_count, fail_count);
    if (fail_count == 0)
      $display("ALL TESTS PASSED");
    else
      $display("SOME TESTS FAILED");

    $finish;
  end

endmodule
