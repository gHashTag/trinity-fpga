// =============================================================================
// holo_deinterleave.sv — Wave-39 Lane EE RTL
// =============================================================================
// Module: holo_deinterleave
//
// Holographic de-interleaver: routes an input byte stream to one of four
// output channels based on the 2-bit φ⁻¹ phase selector.
//
// Only the channel whose index matches `phase` receives the input data and
// has its valid flag asserted; all other channels output zero with valid=0.
//
// This implements the inverse of the holographic interleaver: given a
// time-multiplexed stream tagged by phase, each downstream consumer sees
// only its own lane's data, eliminating cross-lane interference.
//
//   φ² + φ⁻² = 3  (Trinity Identity, R-SI-1)
//   DOI: 10.5281/zenodo.19227877
//
// Inputs:
//   in_stream — 8-bit input data byte
//   phase     — 2-bit channel selector
//
// Outputs:
//   out_ch0..out_ch3   — 8-bit per-channel output (non-selected = 8'h00)
//   valid_ch0..valid_ch3 — per-channel valid strobe (non-selected = 1'b0)
//
// Pure combinational; no clock, no registers.
// =============================================================================

module holo_deinterleave (
    input  logic [7:0] in_stream,
    input  logic [1:0] phase,
    output logic [7:0] out_ch0,
    output logic [7:0] out_ch1,
    output logic [7:0] out_ch2,
    output logic [7:0] out_ch3,
    output logic       valid_ch0,
    output logic       valid_ch1,
    output logic       valid_ch2,
    output logic       valid_ch3
);

    // Route input to the selected channel; zero all others
    always_comb begin
        // Default: all channels zero, all valid deasserted
        out_ch0   = 8'h00;
        out_ch1   = 8'h00;
        out_ch2   = 8'h00;
        out_ch3   = 8'h00;
        valid_ch0 = 1'b0;
        valid_ch1 = 1'b0;
        valid_ch2 = 1'b0;
        valid_ch3 = 1'b0;

        // Assert only the selected channel
        case (phase)
            2'b00: begin out_ch0 = in_stream; valid_ch0 = 1'b1; end
            2'b01: begin out_ch1 = in_stream; valid_ch1 = 1'b1; end
            2'b10: begin out_ch2 = in_stream; valid_ch2 = 1'b1; end
            2'b11: begin out_ch3 = in_stream; valid_ch3 = 1'b1; end
            default: begin /* all zero — covered by defaults above */ end
        endcase
    end

endmodule
