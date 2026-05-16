// =============================================================================
// Wave 43 -- Lane MM -- S-180 + S-181
// File   : rtl/int2_quant/int2_packer.sv
// Anchor : phi^2+phi^-2=3 (three-path witness)
// DOI    : 10.5281/zenodo.19227877
//
// INT2 Codebook
//   State         Code    INT4 approx
//   -1            2'b00   4'sb1111  (-1)
//    0            2'b01   4'sb0000  ( 0)
//   +phi^-1       2'b10   4'b0011   (~+0.618 quantized to +3 in 4-bit scale)
//   +1            2'b11   4'sb0001  (+1)
//
// phi^-1 = (sqrt(5)-1)/2 ~ 0.618
// +phi^-1 quantized to nearest INT4 value: 3 in range [-8..+7] -> 4'b0011
//
// R-SI-1 compliance: zero star, zero slash, zero unsigned-right-shift sign-loss.
// Only assign, case, comparison, addition, bitwise operators used.
// =============================================================================

// -----------------------------------------------------------------------------
// Module: int2_unpacker
// Combinational lookup: INT2 code -> sign-extended INT4 activation
// -----------------------------------------------------------------------------
module int2_unpacker (
    input  logic [1:0] code,
    output logic [3:0] int4_act
);
    // Decode INT2 code to INT4 representation.
    // Code 2'b00 => -1  => 4'sb1111
    // Code 2'b01 =>  0  => 4'sb0000
    // Code 2'b10 => +phi^-1 (~0.618) quantized => 4'b0011 (+3 in INT4)
    // Code 2'b11 => +1  => 4'sb0001
    always_comb begin
        case (code)
            2'b00:   int4_act = 4'sb1111; // -1
            2'b01:   int4_act = 4'sb0000; //  0
            2'b10:   int4_act = 4'b0011;  // +phi^-1, quantized to +3
            2'b11:   int4_act = 4'sb0001; // +1
            default: int4_act = 4'sb0000;
        endcase
    end
endmodule

// -----------------------------------------------------------------------------
// Module: int2_pack_sram_iface
// Packs four INT2 codes into one 8-bit SRAM word (little-endian bit order).
// act0 occupies bits [1:0], act1 bits [3:2], act2 bits [5:4], act3 bits [7:6].
// -----------------------------------------------------------------------------
module int2_pack_sram_iface (
    input  logic [1:0] act0,
    input  logic [1:0] act1,
    input  logic [1:0] act2,
    input  logic [1:0] act3,
    output logic [7:0] sram_word
);
    assign sram_word = {act3, act2, act1, act0};
endmodule

// -----------------------------------------------------------------------------
// Module: int2_col13_gate
// Quantizes a signed INT4 activation back to INT2 code.
// Thresholds (approximate, integer arithmetic only -- R-SI-1 compliant):
//   act < -1  => code 2'b00 (-1 bucket)
//   act == 0  => code 2'b01 ( 0 bucket)
//   0 < act < 2 => code 2'b10 (phi^-1 bucket, mid-positive)
//   act >= 2  => code 2'b11 (+1 bucket)
//   act < 0 and act != -1 ... rounded to -1 bucket
//
// Decision boundaries chosen to partition [-8..+7] into four regions:
//   Region 2'b00: act_int4 <= -1  (any negative)
//   Region 2'b01: act_int4 == 0
//   Region 2'b10: act_int4 == 1 or act_int4 == 2 (small positive)
//   Region 2'b11: act_int4 >= 3   (large positive)
//
// No star, no slash operators used.
// -----------------------------------------------------------------------------
module int2_col13_gate (
    input  logic signed [3:0] act_int4,
    output logic [1:0] code
);
    always_comb begin
        if (act_int4 <= 4'sb1111)       // act_int4 <= -1 (negative)
            code = 2'b00;
        else if (act_int4 == 4'sb0000)  // act_int4 == 0
            code = 2'b01;
        else if (act_int4 <= 4'sb0010)  // 1 <= act_int4 <= 2  (phi^-1 region)
            code = 2'b10;
        else                            // act_int4 >= 3 (+1 region)
            code = 2'b11;
    end
endmodule
