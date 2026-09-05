// Decode cost: MXFP4's E2M1 element versus the derived codebook.
//
// The bit-fairness caveat carried through this whole programme was that E2M1 decodes
// combinationally from its bit pattern while the derived codebook needs a 16-entry lookup
// table. On an ASIC that is a real difference: E2M1's decode is a shift, an arbitrary
// codebook is a mux tree. On an FPGA the claim is less obvious and worth measuring rather
// than asserting, because a 4-input function of ANY kind fits one LUT per output bit.
//
// Both modules take the same 4-bit code and produce the same signed Q1.7 value, so the
// comparison is like-for-like. Values are the normalised levels scaled by 127.

module dec_e2m1 (input wire [3:0] code, output reg signed [7:0] val);
    // sign | exp[1:0] | mant  ->  {0, .5, 1, 1.5, 2, 3, 4, 6} / 6, times 127
    always @* begin
        case (code[2:0])
            3'd0: val = 8'sd0;    // 0.0
            3'd1: val = 8'sd11;   // 0.5/6
            3'd2: val = 8'sd21;   // 1.0/6
            3'd3: val = 8'sd32;   // 1.5/6
            3'd4: val = 8'sd42;   // 2.0/6
            3'd5: val = 8'sd64;   // 3.0/6
            3'd6: val = 8'sd85;   // 4.0/6
            3'd7: val = 8'sd127;  // 6.0/6
        endcase
        if (code[3]) val = -val;
    end
endmodule

module dec_derived (input wire [3:0] code, output reg signed [7:0] val);
    // exact DP optimum: 0 .1095 .2219 .3400 .4680 .6121 .7825 1, times 127
    always @* begin
        case (code[2:0])
            3'd0: val = 8'sd0;
            3'd1: val = 8'sd14;
            3'd2: val = 8'sd28;
            3'd3: val = 8'sd43;
            3'd4: val = 8'sd59;
            3'd5: val = 8'sd78;
            3'd6: val = 8'sd99;
            3'd7: val = 8'sd127;
        endcase
        if (code[3]) val = -val;
    end
endmodule

// In situ: a full 32-element block dequantiser, which is how the decoder is actually used.
module block_e2m1 (input wire [127:0] codes, output wire signed [255:0] vals);
    genvar i;
    generate for (i = 0; i < 32; i = i + 1) begin : g
        dec_e2m1 u (.code(codes[4*i+3:4*i]), .val(vals[8*i+7:8*i]));
    end endgenerate
endmodule

module block_derived (input wire [127:0] codes, output wire signed [255:0] vals);
    genvar i;
    generate for (i = 0; i < 32; i = i + 1) begin : g
        dec_derived u (.code(codes[4*i+3:4*i]), .val(vals[8*i+7:8*i]));
    end endgenerate
endmodule
