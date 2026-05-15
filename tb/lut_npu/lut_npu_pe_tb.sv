// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// Testbench: lut_npu_pe_tb — 9 directed tests covering the W35-G5 gate
//   (≥9/9 PASS required).
// R-SI-1: zero `*` in DUT. Testbench may contain `*` for spec/oracle only;
//         Yosys synth runs on rtl/lut_npu/lut_npu_pe.sv only.
//
// LUT semantic invariant verified:
//   For inputs producing (n_plus products, n_minus products) with
//   n_plus + n_minus ≤ 9, addr = 9*n_plus + n_minus and lut_rom[addr]
//   = floor(addr/9) - (addr mod 9).
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-35
// DOI:    10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────
`timescale 1ns/1ps
`default_nettype none

module lut_npu_pe_tb;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg  [7:0]  opcode;
    reg  [17:0] w_packed;
    reg  [17:0] x_packed;
    wire [6:0]  lut_addr;
    wire signed [5:0] lut_out;
    wire        valid_out;
    wire [3:0]  wave35_marker;

    integer pass_count;
    integer fail_count;

    initial begin
        pass_count = 0;
        fail_count = 0;
    end

    // 100 MHz clock
    always #5 clk = ~clk;

    lut_npu_pe dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .opcode       (opcode),
        .w_packed     (w_packed),
        .x_packed     (x_packed),
        .lut_addr     (lut_addr),
        .lut_out      (lut_out),
        .valid_out    (valid_out),
        .wave35_marker(wave35_marker)
    );

    task automatic check_case;
        input [255:0]      label;
        input [17:0]       w;
        input [17:0]       x;
        input [6:0]        expect_addr;
        input signed [5:0] expect_out;
        begin
            opcode   = 8'hE3;
            w_packed = w;
            x_packed = x;
            @(posedge clk);
            #1;
            if (lut_addr === expect_addr && lut_out === expect_out && valid_out === 1'b1) begin
                $display("PASS %0s — addr=%0d out=%0d", label, lut_addr, $signed(lut_out));
                pass_count = pass_count + 1;
            end else begin
                $display("FAIL %0s — got addr=%0d out=%0d valid=%b ; expected addr=%0d out=%0d valid=1",
                         label, lut_addr, $signed(lut_out), valid_out,
                         expect_addr, $signed(expect_out));
                fail_count = fail_count + 1;
            end
        end
    endtask

    reg signed [5:0] neg3;
    reg signed [5:0] neg9;

    initial begin
        neg3 = -6'sd3;
        neg9 = -6'sd9;

        $dumpfile("lut_npu_pe_tb.vcd");
        $dumpvars(0, lut_npu_pe_tb);

        // 2'b00 = 0, 2'b01 = +1, 2'b10 = -1, 2'b11 invalid (unused)
        // Reset
        #2 rst_n = 1'b0; opcode = 8'h00; w_packed = 18'd0; x_packed = 18'd0;
        @(posedge clk); @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // ── 9 test cases for W35-G5 (≥9/9 PASS required) ──────────────────────

        // T1: all zeros → n_plus=0,n_minus=0 → addr=0, lut[0]=0-0=0
        check_case("T1 all-zero",
            18'b000000000000000000, 18'b000000000000000000, 7'd0, 6'sd0);

        // T2: lanes 1..8 = (+1·+1)=+1, lane 0 = (0·0)=0
        //   n_plus=8, n_minus=0 → addr=72, lut[72]=72/9=8, 72%9=0 → 8-0=8
        //   w: lane0=00, lanes1..8 = 01 → 18'b 01 01 01 01 01 01 01 01 00
        check_case("T2 eight-plus-one-zero",
            18'b010101010101010101 & ~18'b000000000000000011,
            18'b010101010101010101 & ~18'b000000000000000011,
            7'd72, 6'sd8);

        // T3: 3 lanes (+1·-1)=-1, 6 lanes zero
        //   n_plus=0, n_minus=3 → addr=3, lut[3]=0-3=-3
        //   w: lanes 0,1,2=01, rest 0; x: lanes 0,1,2=10, rest 0
        check_case("T3 three-minus-six-zero",
            18'b000000000000010101,
            18'b000000000000101010,
            7'd3, neg3);

        // T4: 5 lanes (+1·+1)=+1, 4 lanes zero → n_plus=5, addr=45, lut[45]=5-0=5
        check_case("T4 five-plus-four-zero",
            18'b000000000101010101,
            18'b000000000101010101,
            7'd45, 6'sd5);

        // T5: 2 plus and 2 minus from sign-cross
        //   w: lanes 0,1=01 (+1), lanes 2,3=10 (-1), rest 00 → lane0=01,lane1=01,lane2=10,lane3=10
        //   x: lanes 0,1=01 (+1), lanes 2,3=01 (+1) → products: +1,+1,-1,-1
        //   n_plus=2, n_minus=2 → addr=20, lut[20]=20/9=2, 20%9=2 → 2-2=0
        check_case("T5 two-plus-two-minus",
            18'b000000000010100101,
            18'b000000000001010101,
            7'd20, 6'sd0);

        // T6: 1 plus, 0 minus, 8 zero → addr=9, lut[9]=1-0=1
        check_case("T6 one-plus",
            18'b000000000000000001,
            18'b000000000000000001,
            7'd9, 6'sd1);

        // T7: 0 plus, 1 minus, 8 zero → addr=1, lut[1]=0-1=-1
        //   w lane0=+1 (01), rest 0; x lane0=-1 (10), rest 0 → product=-1
        check_case("T7 one-minus",
            18'b000000000000000001,
            18'b000000000000000010,
            7'd1, -6'sd1);

        // T8: opcode mismatch → valid_out=0
        opcode = 8'h00; w_packed = 18'd0; x_packed = 18'd0;
        @(posedge clk); #1;
        if (valid_out === 1'b0) begin
            $display("PASS T8 opcode-mismatch — valid_out=0");
            pass_count = pass_count + 1;
        end else begin
            $display("FAIL T8 opcode-mismatch — valid_out=%b expected 0", valid_out);
            fail_count = fail_count + 1;
        end

        // T9: marker constant
        if (wave35_marker === 4'b1110) begin
            $display("PASS T9 marker=4'b1110");
            pass_count = pass_count + 1;
        end else begin
            $display("FAIL T9 marker=%b expected 1110", wave35_marker);
            fail_count = fail_count + 1;
        end

        // ── Summary ─────────────────────────────────────────────────────────
        $display("=====================================");
        $display("LUT-NPU PE TB: %0d PASS / %0d FAIL", pass_count, fail_count);
        $display("=====================================");
        if (fail_count == 0) begin
            $display("W35-G5 GATE: PASS (>=9/9)");
            $finish(0);
        end else begin
            $display("W35-G5 GATE: FAIL");
            $finish(1);
        end
    end

endmodule

`default_nettype wire
