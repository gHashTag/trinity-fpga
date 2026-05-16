// phi^2 + phi^-2 = 3 -- TRI-1 Wave 46 Lane SS -- Purkinje gate testbench
// W-109-G  freeze 2027-04-15
// Closes gHashTag trinity-fpga issue 178
module purkinje_gate_tb;

  // DUT signals
  logic        clk;
  logic        rst_n;
  logic [7:0]  temp_tile [26:0];
  logic [26:0] mask;

  // Instantiate DUT
  purkinje_gate dut (
    .clk       (clk),
    .rst_n     (rst_n),
    .temp_tile (temp_tile),
    .mask      (mask)
  );

  // Free-running clock, 10 ns period
  initial clk = 1'b0;
  always #5 clk = ~clk;

  // Helper: set all tiles to a single value
  task set_all;
    input logic [7:0] val;
    integer k;
    begin
      for (k = 0; k < 27; k = k + 1)
        temp_tile[k] = val;
    end
  endtask

  integer i;

  initial begin
    // Reset
    rst_n = 1'b0;
    set_all(8'd0);
    repeat(4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);

    // Test 1: all tiles cold (50 < 85) -- expect all mask bits 1
    set_all(8'd50);
    @(posedge clk); @(posedge clk);
    if (mask !== 27'h7FFFFFF)
      $display("FAIL test1: mask=%b expected all-ones", mask);
    else
      $display("PASS test1: cold tiles, mask=all-ones");

    // Test 2: all tiles hot (100 >= 85) -- expect all mask bits 0
    set_all(8'd100);
    @(posedge clk); @(posedge clk);
    if (mask !== 27'd0)
      $display("FAIL test2: mask=%b expected all-zeros", mask);
    else
      $display("PASS test2: hot tiles, mask=all-zeros");

    // Test 3: tile 0 cold, rest hot
    set_all(8'd200);
    temp_tile[0] = 8'd10;
    @(posedge clk); @(posedge clk);
    if (mask[0] !== 1'b1)
      $display("FAIL test3a: mask[0]=%b expected 1", mask[0]);
    else
      $display("PASS test3a: tile0 cold mask[0]=1");
    if (mask[26:1] !== 26'd0)
      $display("FAIL test3b: mask[26:1]=%b expected all-zeros", mask[26:1]);
    else
      $display("PASS test3b: tiles1..26 hot mask=0");

    // Test 4: tile 26 cold, rest hot
    set_all(8'd90);
    temp_tile[26] = 8'd84;
    @(posedge clk); @(posedge clk);
    if (mask[26] !== 1'b1)
      $display("FAIL test4: mask[26]=%b expected 1", mask[26]);
    else
      $display("PASS test4: tile26 cold mask[26]=1");

    // Test 5: boundary -- exactly T_HOT=85 is NOT cold (mask=0)
    set_all(8'd85);
    @(posedge clk); @(posedge clk);
    if (mask !== 27'd0)
      $display("FAIL test5: mask=%b at T_HOT boundary", mask);
    else
      $display("PASS test5: boundary T_HOT mask=all-zeros");

    // Test 6: T_HOT - 1 = 84 is cold (mask=1)
    set_all(8'd84);
    @(posedge clk); @(posedge clk);
    if (mask !== 27'h7FFFFFF)
      $display("FAIL test6: mask=%b at T_HOT-1 boundary", mask);
    else
      $display("PASS test6: boundary T_HOT-1 mask=all-ones");

    $display("Testbench complete. phi^2 + phi^-2 = 3");
    $finish;
  end

endmodule
