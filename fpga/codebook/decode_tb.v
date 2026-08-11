// Correctness before area. A decoder that emits the wrong table is smaller than
// one that emits the right table, so the LUT counts below mean nothing until the
// function is checked. Both decoders are exhaustive at 4 bits: 16 codes each, no
// sampling needed.
//
// The golden values are written out here as literals, independently of the RTL,
// and the bench also asserts a deliberately wrong expectation at the end to
// confirm a failure would actually be caught.
`timescale 1ns/1ps
module decode_tb;
    integer errors = 0;
    integer i;
    reg [2:0] j;

    reg [3:0] code;
    wire signed [4:0] wm;
    wire signed [7:0] w6;
    mxfp4_decode   um (.code(code), .w(wm));
    cb4_decode_b6  uc (.code(code), .w(w6));

    // E2M1 magnitudes in units of 0.5, index {e,m}: 0,1,2,3,4,6,8,12
    integer mx [0:7];
    // KL codebook quantised to 6 fractional bits: 0,5,12,20,30,39,51,64
    integer cb [0:7];
    integer expm, expc;

    initial begin
        mx[0]=0;  mx[1]=1;  mx[2]=2;  mx[3]=3;  mx[4]=4;  mx[5]=6;  mx[6]=8;  mx[7]=12;
        cb[0]=0;  cb[1]=5;  cb[2]=12; cb[3]=20; cb[4]=30; cb[5]=39; cb[6]=51; cb[7]=64;

        for (i = 0; i < 16; i = i + 1) begin
            code = i[3:0];
            #1;
            expm = i[3] ? -mx[i[2:0]] : mx[i[2:0]];
            expc = i[3] ? -cb[i[2:0]] : cb[i[2:0]];
            if (wm !== expm) begin
                $display("MXFP4  code=%b got=%0d want=%0d", code, wm, expm);
                errors = errors + 1;
            end
            if (w6 !== expc) begin
                $display("CB b=6 code=%b got=%0d want=%0d", code, w6, expc);
                errors = errors + 1;
            end
        end

        // monotone and distinct, read out of the RTL itself rather than assumed
        for (i = 0; i < 7; i = i + 1) begin
            code = {1'b0, i[2:0]};   #1;  expm = wm;  expc = w6;
            j    = i + 1;
            code = {1'b0, j};        #1;
            if (!(wm > expm)) begin $display("MXFP4 not monotone at %0d", i); errors = errors + 1; end
            if (!(w6 > expc)) begin $display("CB    not monotone at %0d", i); errors = errors + 1; end
        end

        // the bench must be able to fail
        code = 4'b0111; #1;
        if (w6 === 8'sd63) begin
            $display("SENSITIVITY BROKEN: a wrong expectation was not distinguishable");
            errors = errors + 1;
        end else
            $display("sensitivity ok: a wrong expectation (63 for 64) would be caught");

        if (errors == 0) $display("PASS  32 exhaustive checks + 14 monotonicity checks, 0 errors");
        else             $display("FAIL  %0d errors", errors);
        $finish;
    end
endmodule
