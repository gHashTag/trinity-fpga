// SPDX-License-Identifier: Apache-2.0
// Wave-38 Lane CC — Reversible Dendritic NULLOR PE
// OP_NULL_PE = 0xE6 (sacred opcode chain post W37 OP_SUBTH_CLK=0xE4)
// Adiabatic charge-recycling ternary multiplier, target eta_reuse >= 0.88
// R-SI-1: zero `*` operators — multiplication via case-table lookup on 2-bit ternary
// Anchor: phi^2 + phi^-2 = 3
//
// Ternary encoding (2 bits per trit):
//   2'b00 = Zero (Z3 0)
//   2'b01 = Pos1 (Z3 +1)
//   2'b10 = Neg1 (Z3 -1)
//   2'b11 = invalid (asserted false in simulation)

module nullor_pe (
  input  wire        rst_n,
  input  wire        phi_1,         // 400 MHz precharge
  input  wire        phi_2,         // 300 MHz evaluate
  input  wire        phi_3,         // 200 MHz recover
  input  wire        phi_4,         // 100 MHz reset reservoir
  input  wire [7:0]  opcode,        // ISA opcode bus
  input  wire [1:0]  a_trit,        // ternary input a
  input  wire [1:0]  b_trit,        // ternary input b
  output reg  [1:0]  y_trit,        // ternary output y = a x b (no `*`)
  output reg         bypass_active, // asserted when |a|<eps OR |b|<eps
  output reg  [7:0]  reservoir_q    // recovered charge reservoir
);

  localparam [7:0] OP_NULL_PE = 8'hE6;

  // 2-bit ternary lookup (avoids `*` operator entirely)
  // Truth table for ternary multiplication a x b:
  //   0 x any = 0;  (+1) x (+1) = +1;  (+1) x (-1) = -1
  //  (-1) x (+1) = -1; (-1) x (-1) = +1
  function automatic [1:0] tmul_lut;
    input [1:0] x;
    input [1:0] y;
    begin
      case ({x, y})
        4'b00_00: tmul_lut = 2'b00;  //  0 x  0 =  0
        4'b00_01: tmul_lut = 2'b00;  //  0 x +1 =  0
        4'b00_10: tmul_lut = 2'b00;  //  0 x -1 =  0
        4'b01_00: tmul_lut = 2'b00;  // +1 x  0 =  0
        4'b01_01: tmul_lut = 2'b01;  // +1 x +1 = +1
        4'b01_10: tmul_lut = 2'b10;  // +1 x -1 = -1
        4'b10_00: tmul_lut = 2'b00;  // -1 x  0 =  0
        4'b10_01: tmul_lut = 2'b10;  // -1 x +1 = -1
        4'b10_10: tmul_lut = 2'b01;  // -1 x -1 = +1
        default:  tmul_lut = 2'b00;  // invalid encodings collapse to 0
      endcase
    end
  endfunction

  wire opcode_match = (opcode == OP_NULL_PE);
  wire a_is_zero   = (a_trit == 2'b00);
  wire b_is_zero   = (b_trit == 2'b00);
  wire bypass_w    = a_is_zero | b_is_zero;

  // Reservoir recovery counter — incremented on phi_3 recovery phase
  // Models adiabatic charge return: Q_recovered ~ 0.88 * Q_input
  reg [7:0] charge_in_acc;

  always @(posedge phi_1 or negedge rst_n) begin
    if (!rst_n) begin
      y_trit        <= 2'b00;
      bypass_active <= 1'b0;
      charge_in_acc <= 8'd0;
    end else if (opcode_match) begin
      bypass_active <= bypass_w;
      if (bypass_w) begin
        y_trit <= 2'b00;  // bypass: identity to zero
      end else begin
        y_trit <= tmul_lut(a_trit, b_trit);
      end
      // accumulate input charge proxy (bit-population) on precharge phase
      charge_in_acc <= charge_in_acc + {6'd0, ^a_trit, ^b_trit};
    end
  end

  // Phase phi_3: recover ~88% of input charge to reservoir
  // (0.88 ≈ 225/256). Implemented as (x << 8 - x << 5 - x << 2) >> 8 → shift-only, no `*`.
  always @(posedge phi_3 or negedge rst_n) begin
    if (!rst_n) begin
      reservoir_q <= 8'd0;
    end else if (opcode_match) begin
      // Approximate Q_recovered = (charge_in_acc << 8 - charge_in_acc << 5 - charge_in_acc << 2) >> 8
      reservoir_q <= (
        ({8'd0, charge_in_acc} << 8)
        - ({8'd0, charge_in_acc} << 5)
        - ({8'd0, charge_in_acc} << 2)
      ) >> 8;
    end
  end

  // Phase phi_4: drain residual reservoir (slow leak)
  always @(posedge phi_4 or negedge rst_n) begin
    if (!rst_n) begin
      // handled above
    end else if (opcode_match) begin
      charge_in_acc <= charge_in_acc >> 1;  // bleed
    end
  end

  // phi_2 evaluate phase: assert no invalid trit encodings (simulation-only)
  // synthesis translate_off
  always @(posedge phi_2) begin
    if (rst_n && opcode_match) begin
      if (a_trit == 2'b11 || b_trit == 2'b11) begin
        $display("[NULLOR_PE] FATAL: invalid trit encoding 2'b11");
        $finish;
      end
    end
  end
  // synthesis translate_on

endmodule
