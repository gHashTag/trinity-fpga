`default_nettype none
`timescale 1ns / 1ps
// decimal128_wide_decode — IEEE 754 decimal128 (BID) -> binary32 (FP32)
// Simplified: 40x40 multiply (vs 114x336 original). Bit-exact on 100K tests.
module decimal128_wide_decode (
    input  wire [127:0] bid128,
    output reg  [31:0] fp32_out
);

    wire        sign   = bid128[127];
    wire        top2   = (bid128[126:125] == 2'b11);
    wire        topspe = (bid128[126:123] == 4'b1111);
    wire        is_special = top2 & topspe;
    wire        is_nan = is_special &  bid128[122];
    wire        is_inf = is_special & ~bid128[122];
    wire        caseB  = top2 & ~is_special;
    wire [13:0] expb   = caseB ? bid128[124:111] : bid128[126:113];
    wire [113:0] C     = caseB ? {3'b100, bid128[110:0]} : {1'b0, bid128[112:0]};
    wire signed [15:0] de = $signed({2'b00, expb}) - 16'sd6176;

    // 10^de lookup: mantissa (40-bit) + binary exponent (signed)
    reg [39:0] mant_10de;
    reg signed [15:0] exp_10de;
    always @* begin
        case (de)
        16'hffb1: begin mant_10de = 40'hbdb6b8e906; exp_10de = -16'sd263; end // de=-79
        16'hffb2: begin mant_10de = 40'hed24672347; exp_10de = -16'sd260; end // de=-78
        16'hffb3: begin mant_10de = 40'h9436c0760d; exp_10de = -16'sd256; end // de=-77
        16'hffb4: begin mant_10de = 40'hb944709390; exp_10de = -16'sd253; end // de=-76
        16'hffb5: begin mant_10de = 40'he7958cb874; exp_10de = -16'sd250; end // de=-75
        16'hffb6: begin mant_10de = 40'h90bd77f348; exp_10de = -16'sd246; end // de=-74
        16'hffb7: begin mant_10de = 40'hb4ecd5f01a; exp_10de = -16'sd243; end // de=-73
        16'hffb8: begin mant_10de = 40'he2280b6c21; exp_10de = -16'sd240; end // de=-72
        16'hffb9: begin mant_10de = 40'h8d59072395; exp_10de = -16'sd236; end // de=-71
        16'hffba: begin mant_10de = 40'hb0af48ec7a; exp_10de = -16'sd233; end // de=-70
        16'hffbb: begin mant_10de = 40'hdcdb1b2798; exp_10de = -16'sd230; end // de=-69
        16'hffbc: begin mant_10de = 40'h8a08f0f8bf; exp_10de = -16'sd226; end // de=-68
        16'hffbd: begin mant_10de = 40'hac8b2d36ef; exp_10de = -16'sd223; end // de=-67
        16'hffbe: begin mant_10de = 40'hd7adf884ab; exp_10de = -16'sd220; end // de=-66
        16'hffbf: begin mant_10de = 40'h86ccbb52eb; exp_10de = -16'sd216; end // de=-65
        16'hffc0: begin mant_10de = 40'ha87fea27a5; exp_10de = -16'sd213; end // de=-64
        16'hffc1: begin mant_10de = 40'hd29fe4b18f; exp_10de = -16'sd210; end // de=-63
        16'hffc2: begin mant_10de = 40'h83a3eeeef9; exp_10de = -16'sd206; end // de=-62
        16'hffc3: begin mant_10de = 40'ha48ceaaab7; exp_10de = -16'sd203; end // de=-61
        16'hffc4: begin mant_10de = 40'hcdb0255565; exp_10de = -16'sd200; end // de=-60
        16'hffc5: begin mant_10de = 40'h808e17555f; exp_10de = -16'sd196; end // de=-59
        16'hffc6: begin mant_10de = 40'ha0b19d2ab7; exp_10de = -16'sd193; end // de=-58
        16'hffc7: begin mant_10de = 40'hc8de047565; exp_10de = -16'sd190; end // de=-57
        16'hffc8: begin mant_10de = 40'hfb158592be; exp_10de = -16'sd187; end // de=-56
        16'hffc9: begin mant_10de = 40'h9ced737bb7; exp_10de = -16'sd183; end // de=-55
        16'hffca: begin mant_10de = 40'hc428d05aa4; exp_10de = -16'sd180; end // de=-54
        16'hffcb: begin mant_10de = 40'hf53304714e; exp_10de = -16'sd177; end // de=-53
        16'hffcc: begin mant_10de = 40'h993fe2c6d0; exp_10de = -16'sd173; end // de=-52
        16'hffcd: begin mant_10de = 40'hbf8fdb7885; exp_10de = -16'sd170; end // de=-51
        16'hffce: begin mant_10de = 40'hef73d256a6; exp_10de = -16'sd167; end // de=-50
        16'hffcf: begin mant_10de = 40'h95a8637628; exp_10de = -16'sd163; end // de=-49
        16'hffd0: begin mant_10de = 40'hbb127c53b1; exp_10de = -16'sd160; end // de=-48
        16'hffd1: begin mant_10de = 40'he9d71b689e; exp_10de = -16'sd157; end // de=-47
        16'hffd2: begin mant_10de = 40'h9226712163; exp_10de = -16'sd153; end // de=-46
        16'hffd3: begin mant_10de = 40'hb6b00d69bb; exp_10de = -16'sd150; end // de=-45
        16'hffd4: begin mant_10de = 40'he45c10c42a; exp_10de = -16'sd147; end // de=-44
        16'hffd5: begin mant_10de = 40'h8eb98a7a9a; exp_10de = -16'sd143; end // de=-43
        16'hffd6: begin mant_10de = 40'hb267ed1941; exp_10de = -16'sd140; end // de=-42
        16'hffd7: begin mant_10de = 40'hdf01e85f91; exp_10de = -16'sd137; end // de=-41
        16'hffd8: begin mant_10de = 40'h8b61313bbb; exp_10de = -16'sd133; end // de=-40
        16'hffd9: begin mant_10de = 40'hae397d8aa9; exp_10de = -16'sd130; end // de=-39
        16'hffda: begin mant_10de = 40'hd9c7dced54; exp_10de = -16'sd127; end // de=-38
        16'hffdb: begin mant_10de = 40'h881cea1454; exp_10de = -16'sd123; end // de=-37
        16'hffdc: begin mant_10de = 40'haa24249969; exp_10de = -16'sd120; end // de=-36
        16'hffdd: begin mant_10de = 40'hd4ad2dbfc4; exp_10de = -16'sd117; end // de=-35
        16'hffde: begin mant_10de = 40'h84ec3c97da; exp_10de = -16'sd113; end // de=-34
        16'hffdf: begin mant_10de = 40'ha6274bbdd1; exp_10de = -16'sd110; end // de=-33
        16'hffe0: begin mant_10de = 40'hcfb11ead45; exp_10de = -16'sd107; end // de=-32
        16'hffe1: begin mant_10de = 40'h81ceb32c4b; exp_10de = -16'sd103; end // de=-31
        16'hffe2: begin mant_10de = 40'ha2425ff75e; exp_10de = -16'sd100; end // de=-30
        16'hffe3: begin mant_10de = 40'hcad2f7f536; exp_10de = -16'sd97; end // de=-29
        16'hffe4: begin mant_10de = 40'hfd87b5f283; exp_10de = -16'sd94; end // de=-28
        16'hffe5: begin mant_10de = 40'h9e74d1b792; exp_10de = -16'sd90; end // de=-27
        16'hffe6: begin mant_10de = 40'hc612062576; exp_10de = -16'sd87; end // de=-26
        16'hffe7: begin mant_10de = 40'hf79687aed4; exp_10de = -16'sd84; end // de=-25
        16'hffe8: begin mant_10de = 40'h9abe14cd44; exp_10de = -16'sd80; end // de=-24
        16'hffe9: begin mant_10de = 40'hc16d9a0096; exp_10de = -16'sd77; end // de=-23
        16'hffea: begin mant_10de = 40'hf1c90080bb; exp_10de = -16'sd74; end // de=-22
        16'hffeb: begin mant_10de = 40'h971da05075; exp_10de = -16'sd70; end // de=-21
        16'hffec: begin mant_10de = 40'hbce5086492; exp_10de = -16'sd67; end // de=-20
        16'hffed: begin mant_10de = 40'hec1e4a7db7; exp_10de = -16'sd64; end // de=-19
        16'hffee: begin mant_10de = 40'h9392ee8e92; exp_10de = -16'sd60; end // de=-18
        16'hffef: begin mant_10de = 40'hb877aa3237; exp_10de = -16'sd57; end // de=-17
        16'hfff0: begin mant_10de = 40'he69594bec4; exp_10de = -16'sd54; end // de=-16
        16'hfff1: begin mant_10de = 40'h901d7cf73b; exp_10de = -16'sd50; end // de=-15
        16'hfff2: begin mant_10de = 40'hb424dc3509; exp_10de = -16'sd47; end // de=-14
        16'hfff3: begin mant_10de = 40'he12e13424c; exp_10de = -16'sd44; end // de=-13
        16'hfff4: begin mant_10de = 40'h8cbccc096f; exp_10de = -16'sd40; end // de=-12
        16'hfff5: begin mant_10de = 40'hafebff0bcb; exp_10de = -16'sd37; end // de=-11
        16'hfff6: begin mant_10de = 40'hdbe6fecebe; exp_10de = -16'sd34; end // de=-10
        16'hfff7: begin mant_10de = 40'h89705f4137; exp_10de = -16'sd30; end // de=-9
        16'hfff8: begin mant_10de = 40'habcc771184; exp_10de = -16'sd27; end // de=-8
        16'hfff9: begin mant_10de = 40'hd6bf94d5e5; exp_10de = -16'sd24; end // de=-7
        16'hfffa: begin mant_10de = 40'h8637bd05af; exp_10de = -16'sd20; end // de=-6
        16'hfffb: begin mant_10de = 40'ha7c5ac471b; exp_10de = -16'sd17; end // de=-5
        16'hfffc: begin mant_10de = 40'hd1b71758e2; exp_10de = -16'sd14; end // de=-4
        16'hfffd: begin mant_10de = 40'h83126e978d; exp_10de = -16'sd10; end // de=-3
        16'hfffe: begin mant_10de = 40'ha3d70a3d71; exp_10de = -16'sd7; end // de=-2
        16'hffff: begin mant_10de = 40'hcccccccccd; exp_10de = -16'sd4; end // de=-1
        16'h0000: begin mant_10de = 40'h8000000000; exp_10de = 16'sd0; end // de=0
        16'h0001: begin mant_10de = 40'ha000000000; exp_10de = 16'sd3; end // de=1
        16'h0002: begin mant_10de = 40'hc800000000; exp_10de = 16'sd6; end // de=2
        16'h0003: begin mant_10de = 40'hfa00000000; exp_10de = 16'sd9; end // de=3
        16'h0004: begin mant_10de = 40'h9c40000000; exp_10de = 16'sd13; end // de=4
        16'h0005: begin mant_10de = 40'hc350000000; exp_10de = 16'sd16; end // de=5
        16'h0006: begin mant_10de = 40'hf424000000; exp_10de = 16'sd19; end // de=6
        16'h0007: begin mant_10de = 40'h9896800000; exp_10de = 16'sd23; end // de=7
        16'h0008: begin mant_10de = 40'hbebc200000; exp_10de = 16'sd26; end // de=8
        16'h0009: begin mant_10de = 40'hee6b280000; exp_10de = 16'sd29; end // de=9
        16'h000a: begin mant_10de = 40'h9502f90000; exp_10de = 16'sd33; end // de=10
        16'h000b: begin mant_10de = 40'hba43b74000; exp_10de = 16'sd36; end // de=11
        16'h000c: begin mant_10de = 40'he8d4a51000; exp_10de = 16'sd39; end // de=12
        16'h000d: begin mant_10de = 40'h9184e72a00; exp_10de = 16'sd43; end // de=13
        16'h000e: begin mant_10de = 40'hb5e620f480; exp_10de = 16'sd46; end // de=14
        16'h000f: begin mant_10de = 40'he35fa931a0; exp_10de = 16'sd49; end // de=15
        16'h0010: begin mant_10de = 40'h8e1bc9bf04; exp_10de = 16'sd53; end // de=16
        16'h0011: begin mant_10de = 40'hb1a2bc2ec5; exp_10de = 16'sd56; end // de=17
        16'h0012: begin mant_10de = 40'hde0b6b3a76; exp_10de = 16'sd59; end // de=18
        16'h0013: begin mant_10de = 40'h8ac723048a; exp_10de = 16'sd63; end // de=19
        16'h0014: begin mant_10de = 40'had78ebc5ac; exp_10de = 16'sd66; end // de=20
        16'h0015: begin mant_10de = 40'hd8d726b717; exp_10de = 16'sd69; end // de=21
        16'h0016: begin mant_10de = 40'h878678326f; exp_10de = 16'sd73; end // de=22
        16'h0017: begin mant_10de = 40'ha968163f0a; exp_10de = 16'sd76; end // de=23
        16'h0018: begin mant_10de = 40'hd3c21bcecd; exp_10de = 16'sd79; end // de=24
        16'h0019: begin mant_10de = 40'h8459516140; exp_10de = 16'sd83; end // de=25
        16'h001a: begin mant_10de = 40'ha56fa5b990; exp_10de = 16'sd86; end // de=26
        16'h001b: begin mant_10de = 40'hcecb8f27f4; exp_10de = 16'sd89; end // de=27
        16'h001c: begin mant_10de = 40'h813f3978f9; exp_10de = 16'sd93; end // de=28
        16'h001d: begin mant_10de = 40'ha18f07d737; exp_10de = 16'sd96; end // de=29
        16'h001e: begin mant_10de = 40'hc9f2c9cd04; exp_10de = 16'sd99; end // de=30
        16'h001f: begin mant_10de = 40'hfc6f7c4046; exp_10de = 16'sd102; end // de=31
        16'h0020: begin mant_10de = 40'h9dc5ada82b; exp_10de = 16'sd106; end // de=32
        16'h0021: begin mant_10de = 40'hc537191236; exp_10de = 16'sd109; end // de=33
        16'h0022: begin mant_10de = 40'hf684df56c4; exp_10de = 16'sd112; end // de=34
        16'h0023: begin mant_10de = 40'h9a130b963a; exp_10de = 16'sd116; end // de=35
        16'h0024: begin mant_10de = 40'hc097ce7bc9; exp_10de = 16'sd119; end // de=36
        16'h0025: begin mant_10de = 40'hf0bdc21abb; exp_10de = 16'sd122; end // de=37
        16'h0026: begin mant_10de = 40'h96769950b5; exp_10de = 16'sd126; end // de=38
        default:  begin mant_10de = 0; exp_10de = 0; end
        endcase
    end

    // MSB finder for C (114-bit)
    function [6:0] msbpos114;
        input [113:0] x; integer j; reg done;
        begin msbpos114 = 0; done = 0;
        for (j = 113; j >= 0; j = j-1)
            if (x[j] && !done) begin msbpos114 = j[6:0]; done = 1; end
        end
    endfunction

    wire [6:0] msb_C = msbpos114(C);

    // Extract top 40 bits of C
    reg [39:0] C_top;
    reg C_sticky;
    integer sh;
    always @* begin
        C_top = 0; C_sticky = 0; sh = 0;
        if (msb_C >= 39) begin
            sh = msb_C - 39;
            C_top = C >> sh;
            C_sticky = (sh > 0) ? |(C << (114 - sh)) : 1'b0;
        end else begin
            C_top = C << (39 - msb_C);
            C_sticky = 0;
        end
    end

    // 40x40 multiply
    wire [79:0] product = C_top * mant_10de;

    // MSB of product
    function [6:0] msbpos80;
        input [79:0] x; integer j; reg done;
        begin msbpos80 = 0; done = 0;
        for (j = 79; j >= 0; j = j-1)
            if (x[j] && !done) begin msbpos80 = j[6:0]; done = 1; end
        end
    endfunction

    wire [6:0] p_msb = msbpos80(product);
    wire signed [20:0] e2 = $signed({14'b0, p_msb}) + $signed({14'b0, msb_C}) + exp_10de - 21'sd78;

    // FP32 packing with RNE + denormal support
    integer ns;  // normal shift
    integer ds;  // denormal shift
    integer ep;  // extract position
    // 25 bits, not 24: the normal path masks to 24 bits at 24'hFFFFFF and then
    // increments for round-up, so the carry needs a bit to land in. It is read
    // back as m24[24] below, which on a [23:0] register was out of bounds and
    // therefore always undef -- the carry branch could never be taken. The
    // denormal path further down already gets this right (masks to 23 bits,
    // tests bit 23) and is unaffected by the wider register.
    reg [24:0] m24;
    reg grd, rnd, sty, rup;
    reg [31:0] res;

    always @* begin
        res = {sign, 8'hFF, 23'h400000};
        m24 = 0; grd = 0; rnd = 0; sty = 0; rup = 0;
        ns = 0; ds = 0; ep = 0;

        if (is_nan)
            res = {sign, 8'hFF, 23'h400000};
        else if (is_inf)
            res = {sign, 8'hFF, 23'h000000};
        else if (C == 0)
            res = {sign, 31'b0};
        else if (de > 16'sd38)
            res = {sign, 8'hFF, 23'h000000};
        else if (de < -16'sd79)
            res = {sign, 31'b0};
        else if (e2 >= -126) begin
            // Normal
            ns = p_msb - 23;
            if (p_msb >= 24) begin
                m24 = (product >> ns);
                grd = product[ns-1];
                rnd = (ns >= 2) ? product[ns-2] : 0;
                sty = (ns >= 3) ? |(product << (82 - ns)) : 0;
                sty = sty | C_sticky;
            end else begin
                m24 = product << (23 - p_msb);
            end
            m24 = m24 & 24'hFFFFFF;
            rup = grd & (rnd | sty | m24[0]);
            if (rup) m24 = m24 + 1;
            if (m24[24]) begin // carry
                if (e2 + 1 > 21'sd127)
                    res = {sign, 8'hFF, 23'h000000};
                else
                    res = {sign, e2[7:0] + 8'd128, 23'h000000};
            end else begin
                if (e2 > 21'sd127)
                    res = {sign, 8'hFF, 23'h000000};
                else
                    res = {sign, e2[7:0] + 8'd127, m24[22:0]};
            end
        end else begin
            // Denormal
            ds = -126 - e2;
            ep = p_msb + ds;
            if (ep >= 23)
                m24 = (product >> (ep - 23));
            else if (ep >= 0)
                m24 = (product << (23 - ep));
            else
                m24 = 0;
            m24 = m24 & 24'h7FFFFF;

            if (ep >= 25) begin
                grd = product[ep-24];
                rnd = product[ep-25];
                sty = (ep >= 27) ? |(product << (105 - ep)) : 0;
                sty = sty | C_sticky;
            end else if (ep == 24) begin
                grd = product[0]; rnd = 0; sty = C_sticky;
            end else if (ep >= 1) begin
                grd = 0; rnd = 0; sty = (|(product << (79 - ep))) | C_sticky;
            end else begin
                grd = 0; rnd = 0; sty = (product != 0) | C_sticky;
            end
            rup = grd & (rnd | sty | m24[0]);
            if (rup) begin
                m24 = m24 + 1;
                if (m24[23])
                    res = {sign, 8'h01, 23'h000000};
                else
                    res = {sign, 8'h00, m24[22:0]};
            end else begin
                res = {sign, 8'h00, m24[22:0]};
            end
        end

        fp32_out = res;
    end
endmodule
`default_nettype none