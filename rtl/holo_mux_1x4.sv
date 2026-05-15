// =============================================================================
// holo_mux_1x4.sv — Wave-39 Lane EE RTL
// =============================================================================
// Module: holo_mux_1x4
//
// Holographic 1-of-4 multiplexer controlled by a 2-bit φ⁻¹ phase rotator.
//
// φ⁻¹ Phase Rotation Background:
//   In the TRI-1 Quantum Brain architecture, the holographic MUX implements
//   the φ⁻¹ phase rotation principle: each of the 4 input channels corresponds
//   to one quadrant of the 256-cell shared SRAM address space, addressed by
//   the 2-bit `phase` selector. The conceptual 256-cell shared SRAM partitions
//   memory into four 64-cell banks (bank 0..3), each bank addressed by one
//   phase value. For TB verification we only verify the 4-way mux selector;
//   the full SRAM bank-switching fabric is implemented at the SoC level.
//
//   Identity anchor: φ² + φ⁻² = 3  (Trinity Identity, R-SI-1)
//   Opcode slot     : OP_HOLO_MUX_X4 = 8'hE6  (sacred slot 0xE6)
//   DOI             : 10.5281/zenodo.19227877
//
// Inputs:
//   in_ch0..in_ch3  — 4 data input channels, each 8 bits wide
//   phase           — 2-bit selector (φ⁻¹ phase index)
//
// Outputs:
//   out_mux         — 8-bit selected output
//
// Pure combinational; no clock, no registers.
// =============================================================================

module holo_mux_1x4 (
    input  logic [7:0] in_ch0,
    input  logic [7:0] in_ch1,
    input  logic [7:0] in_ch2,
    input  logic [7:0] in_ch3,
    input  logic [1:0] phase,
    output logic [7:0] out_mux
);

    // Sacred opcode: OP_HOLO_MUX_X4 occupies exclusive slot 0xE6 in the
    // TRI-1 L1 opcode table (Wave-39 Lane EE, R-SI-1 compliant).
    localparam logic [7:0] OP_HOLO_MUX_X4 = 8'hE6;

    // φ⁻¹ 4-way combinational mux
    // phase 2'b00 → channel 0 (SRAM bank 0, cells 0x00..0x3F)
    // phase 2'b01 → channel 1 (SRAM bank 1, cells 0x40..0x7F)
    // phase 2'b10 → channel 2 (SRAM bank 2, cells 0x80..0xBF)
    // phase 2'b11 → channel 3 (SRAM bank 3, cells 0xC0..0xFF)
    assign out_mux = (phase == 2'b00) ? in_ch0 :
                     (phase == 2'b01) ? in_ch1 :
                     (phase == 2'b10) ? in_ch2 :
                                        in_ch3;

endmodule
