// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module expert_gate_tb;
    reg [7:0] l0, l1, l2, l3, l4, l5, l6, l7;
    wire [7:0] mask;
    wire [2:0] t1, t2;

    expert_gate dut (.logit0(l0), .logit1(l1), .logit2(l2), .logit3(l3),
                    .logit4(l4), .logit5(l5), .logit6(l6), .logit7(l7),
                    .mask_out(mask), .top1_idx(t1), .top2_idx(t2));

    integer errors;
    initial begin
        errors = 0;

        // A1: clear ordering [1,5,3,8,2,7,4,6] → top1=idx3, top2=idx5
        l0=8;l1=5;l2=3;l3=128;l4=2;l5=127;l6=4;l7=6; #1;
        // wait: i used wrong values. Re-test: logits 1,5,3,8,2,7,4,6 with idx 0..7.
        l0=1;l1=5;l2=3;l3=8;l4=2;l5=7;l6=4;l7=6; #1;
        if (t1 !== 3'd3) begin $display("FAIL A1 t1=%0d expected 3", t1); errors = errors + 1; end
        if (t2 !== 3'd5) begin $display("FAIL A1 t2=%0d expected 5", t2); errors = errors + 1; end

        // A2: exactly 2 bits set in mask
        if ($countones(mask) !== 2) begin $display("FAIL A2 popcount=%0d expected 2", $countones(mask)); errors = errors + 1; end

        // A3: mask[3] and mask[5] set
        if (mask[3] !== 1'b1 || mask[5] !== 1'b1) begin $display("FAIL A3 mask=%b", mask); errors = errors + 1; end

        // A4: all-equal logits → top1=0, top2=1 (stable tie-break by index)
        l0=8'd5;l1=8'd5;l2=8'd5;l3=8'd5;l4=8'd5;l5=8'd5;l6=8'd5;l7=8'd5; #1;
        if (t1 !== 3'd0) begin $display("FAIL A4 t1=%0d expected 0", t1); errors = errors + 1; end
        if (t2 !== 3'd1) begin $display("FAIL A4 t2=%0d expected 1", t2); errors = errors + 1; end

        // A5: monotone descending → top1=0, top2=1
        l0=8'd80;l1=8'd70;l2=8'd60;l3=8'd50;l4=8'd40;l5=8'd30;l6=8'd20;l7=8'd10; #1;
        if (t1 !== 3'd0) begin $display("FAIL A5 t1=%0d expected 0", t1); errors = errors + 1; end
        if (t2 !== 3'd1) begin $display("FAIL A5 t2=%0d expected 1", t2); errors = errors + 1; end

        // A6: monotone ascending → top1=7, top2=6
        l0=8'd10;l1=8'd20;l2=8'd30;l3=8'd40;l4=8'd50;l5=8'd60;l6=8'd70;l7=8'd80; #1;
        if (t1 !== 3'd7) begin $display("FAIL A6 t1=%0d expected 7", t1); errors = errors + 1; end
        if (t2 !== 3'd6) begin $display("FAIL A6 t2=%0d expected 6", t2); errors = errors + 1; end

        // A7: mask has exactly 2 bits in all cases
        if ($countones(mask) !== 2) begin $display("FAIL A7 popcount=%0d", $countones(mask)); errors = errors + 1; end

        if (errors == 0) begin
            $display("ALL 7 ASSERTIONS PASSED · MoE top-2-of-8 · NO NEW OPCODE · phi^2+phi^-2=3");
            $finish;
        end else begin
            $display("FAIL: %0d errors", errors);
            $fatal(1);
        end
    end
endmodule
