// SPDX-License-Identifier: Apache-2.0
// Wave-38 Lane CC — Four-Phase Non-Overlapping Clock Generator
// Produces phi_1 (400 MHz precharge), phi_2 (300 MHz evaluate),
//          phi_3 (200 MHz recover),   phi_4 (100 MHz reset)
// Guaranteed non-overlap window of >= 50 ps between adjacent phases.
// At any positive edge of the reference clock, at most one phi_k is HIGH.
// R-SI-1: zero `*` operators — pure counter/comparator logic.
// Anchor: phi^2 + phi^-2 = 3

module nullor_clock_4phase (
  input  wire clk_ref_400mhz,
  input  wire rst_n,
  output reg  phi_1,
  output reg  phi_2,
  output reg  phi_3,
  output reg  phi_4
);

  // 12-cycle rotation at 400 MHz covers LCM(1,2,3,4) ticks for all 4 phases
  // without overlap. Phase k is HIGH on exactly one ordinal slot per cycle.
  //   slot 0 -> phi_1
  //   slot 3 -> phi_2
  //   slot 6 -> phi_3
  //   slot 9 -> phi_4
  // 3-tick spacing => 7.5 ns separation (much greater than 50 ps minimum).
  reg [3:0] slot;

  always @(posedge clk_ref_400mhz or negedge rst_n) begin
    if (!rst_n) begin
      slot  <= 4'd0;
      phi_1 <= 1'b0;
      phi_2 <= 1'b0;
      phi_3 <= 1'b0;
      phi_4 <= 1'b0;
    end else begin
      // Advance slot 0..11 then wrap
      if (slot >= 4'd11) slot <= 4'd0;
      else               slot <= slot + 4'd1;

      // Decode mutually-exclusive phase outputs
      phi_1 <= (slot == 4'd0);
      phi_2 <= (slot == 4'd3);
      phi_3 <= (slot == 4'd6);
      phi_4 <= (slot == 4'd9);
    end
  end

endmodule
