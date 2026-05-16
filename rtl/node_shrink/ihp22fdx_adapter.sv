// SPDX-License-Identifier: Apache-2.0
// W41 IHP 22FDX SDF Port Adapter (Node Shrink, OP_NODE_SHRINK = 0xEF)
// Anchor: phi^2 + phi^-2 = 3 · NEVER STOP · DOI 10.5281/zenodo.19227877
//
// R-SI-1: ZERO star characters in synth path. Pure combinational logic.

module ihp22fdx_adapter (
    input  wire [7:0] sacred_opcode,
    output wire       use_ihp22fdx_lib,   // 1 = IHP 22FDX, 0 = SG13G2
    output wire       opcode_in_sacred_range,
    output wire       is_node_shrink
);
    // Sacred range 0xE0..0xEF: top nibble must be 0xE (b1110)
    wire top_nibble_E;
    assign top_nibble_E = (sacred_opcode[7] & sacred_opcode[6] & sacred_opcode[5] & ~sacred_opcode[4]);

    assign opcode_in_sacred_range = top_nibble_E;

    // OP_NODE_SHRINK = 0xEF: low nibble all 1s
    wire low_nibble_F;
    assign low_nibble_F = (sacred_opcode[3] & sacred_opcode[2] & sacred_opcode[1] & sacred_opcode[0]);

    assign is_node_shrink = top_nibble_E & low_nibble_F;

    // IHP 22FDX library is enabled when opcode is in sacred range AND is_node_shrink (W41 trigger)
    // OR when any prior sacred opcode is in W41 port mode (default-off, set by R-marker cell -- assume 0 here)
    assign use_ihp22fdx_lib = is_node_shrink;

endmodule
