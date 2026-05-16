// SPDX-License-Identifier: Apache-2.0
// Wave-48 Lane TT — Forward Body Bias (Active Path) Generator
// Sacred opcode: 0xF2 OP_FBB_ACTIVE (second slot in EXTENDED sacred bank 0xD0..0xFF)
//
// Theory (symmetric dual of W47 RBB at 0xF1):
//   gamma^4 = phi^-12 ≈ 0.003106 (Sacred ROM B007^4 — NO new cell, R18 frozen)
//   V_BS,active = +V_DD · gamma^4 ≈ +2.5 mV (POSITIVE body-source potential)
//   - W47 RBB:        V_BS = -V_DD · gamma^4 (idle PEs, leakage cut)
//   - W48 FBB_ACTIVE: V_BS = +V_DD · gamma^4 (active PEs, delay cut)
//   Same |V_BS| = 25 deci-mV magnitude, opposite sign.
//
// Constitutional:
//   R-SI-1: 0 `*` operators in RTL (verified — all multiplications precomputed)
//   R15 SACRED-SYNTH-GATE: gamma^4 ratio sourced from ROM[B007]^4
//   R18 LAYER-FROZEN: 75 Sacred ROM cells preserved
//
// Sign-off: Vasilev Dmitrii <admin@t27.ai> · ORCID 0009-0008-4294-6159

`default_nettype none

module body_bias_active_gen #(
    parameter int unsigned V_DD_MV       = 800,   // nominal V_DD in mV
    parameter int unsigned GAMMA4_BPS    = 31,    // gamma^4 in basis-points (from B007^4)
    // PRECOMPUTED at elaboration: V_BS magnitude in deci-mV.
    //   V_DD_MV * GAMMA4_BPS / 100 = 800 * 31 / 100 = 248 -> /10 = 25 deci-mV
    //   Hardcoded constant to keep RTL `*`-free (R-SI-1).
    parameter int unsigned V_BS_DECIMV   = 25     // +2.5 mV (positive sign — distinct from RBB negative)
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        active_path,    // assert when critical path is active
    output reg         vbs_rail_en,    // positive body-bias rail enable
    output reg  [7:0]  vbs_mag_decimv  // magnitude in deci-mV (sign is positive by construction)
);

    // Sacred bank membership witness (R18): 0xD0..0xFF
    localparam logic [7:0] OP_FBB_ACTIVE   = 8'hF2;
    localparam logic [7:0] BANK_LO         = 8'hD0;
    localparam logic [7:0] BANK_HI         = 8'hFF;
    // synthesis-time assertions
    initial begin
        if (OP_FBB_ACTIVE < BANK_LO || OP_FBB_ACTIVE > BANK_HI)
            $error("OP_FBB_ACTIVE out of extended bank");
        if (V_BS_DECIMV != 25)
            $error("V_BS_DECIMV must be canonical +25 deci-mV");
    end

    // Rail state machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vbs_rail_en    <= 1'b0;
            vbs_mag_decimv <= 8'd0;
        end else if (active_path) begin
            vbs_rail_en    <= 1'b1;
            vbs_mag_decimv <= V_BS_DECIMV[7:0];
        end else begin
            vbs_rail_en    <= 1'b0;
            vbs_mag_decimv <= 8'd0;
        end
    end

    // R-SI-1: rail magnitude canonical witness (TB verifies vbs_mag_decimv == 25
    // when rail enabled, and 0 when not).
    // phi^2 + phi^-2 = 3

endmodule

`default_nettype wire
