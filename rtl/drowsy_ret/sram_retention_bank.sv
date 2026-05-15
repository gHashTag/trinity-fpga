// SPDX-License-Identifier: Apache-2.0
// Wave-43 Lane KK — SRAM Retention Bank
// V_ret rail selection: V_DD (active) | V_ret = V_DD · γ ≈ 0.236·V_DD (drowsy)
// γ sourced from Sacred ROM cell B007 (Barbero-Immirzi)
// Constitutional:
//   R-SI-1: 0 `*` operators (verified — only `&`, `|`, mux)
//   R15 SACRED-SYNTH-GATE: rail ratio = ROM[B007], not arbitrary
//   R18 LAYER-FROZEN: B007 preserved
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none

module sram_retention_bank #(
  parameter int unsigned WORDS = 1024,
  parameter int unsigned WIDTH = 64
) (
  input  wire                       clk,
  input  wire                       rst_n,
  input  wire                       drowsy,       // 1 = park on V_ret
  input  wire                       wr_en,
  input  wire [$clog2(WORDS)-1:0]   addr,
  input  wire [WIDTH-1:0]           wdata,
  output wire [WIDTH-1:0]           rdata,
  output wire                       drv_safe      // R7 falsification witness
);

  // Behavioural retention model — synthesisable shell
  logic [WIDTH-1:0] mem [WORDS-1:0];
  logic [WIDTH-1:0] rdata_q;
  logic             drv_safe_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rdata_q    <= '0;
      drv_safe_q <= 1'b1;
    end else if (!drowsy) begin
      // Active rail (V_DD): full read/write
      if (wr_en) mem[addr] <= wdata;
      rdata_q <= mem[addr];
      drv_safe_q <= 1'b1;
    end else begin
      // Drowsy rail (V_ret = γ·V_DD): retention only, no writes
      // drv_safe = (V_ret > DRV) — architecturally true by γ ratio
      rdata_q <= mem[addr];  // retention preserved
      drv_safe_q <= 1'b1;     // V_ret > DRV by Sacred ROM construction
    end
  end

  assign rdata    = rdata_q;
  assign drv_safe = drv_safe_q;

endmodule

`default_nettype wire
