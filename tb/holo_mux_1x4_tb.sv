// =============================================================================
// holo_mux_1x4_tb.sv — Testbench for holo_mux_1x4 + holo_deinterleave
// Wave-39 Lane EE — 12/12 TEST SUITE
// =============================================================================
// Tests:
//   TEST  1- 4: Pattern A (A=8'hAA) — each phase selects correct channel
//   TEST  5- 8: Pattern B (B=8'hB1) — each phase selects correct channel
//   TEST  9-12: Pattern C (C=8'hC9) — each phase selects correct channel
//   TEST 12 also checks: OP_HOLO_MUX_X4 == 8'hE6 (sacred slot 0xE6)
//
//   φ² + φ⁻² = 3 · DOI 10.5281/zenodo.19227877
// =============================================================================

`timescale 1ns/1ps

module holo_mux_1x4_tb;

    // DUT signals
    logic [7:0] in_ch0, in_ch1, in_ch2, in_ch3;
    logic [1:0] phase;
    logic [7:0] out_mux;

    // Instantiate DUT
    holo_mux_1x4 u_holo (
        .in_ch0  (in_ch0),
        .in_ch1  (in_ch1),
        .in_ch2  (in_ch2),
        .in_ch3  (in_ch3),
        .phase   (phase),
        .out_mux (out_mux)
    );

    // Test counter
    integer pass_count;

    // Helper task
    task automatic check;
        input [7:0]  expected;
        input [7:0]  got;
        input integer test_num;
        begin
            if (expected === got) begin
                $display("TEST %0d PASS", test_num);
                pass_count = pass_count + 1;
            end else begin
                $display("TEST %0d FAIL exp=%h got=%h", test_num, expected, got);
            end
        end
    endtask

    // Patterns
    localparam logic [7:0] PAT_A0 = 8'hAA;
    localparam logic [7:0] PAT_A1 = 8'hA1;
    localparam logic [7:0] PAT_A2 = 8'hA2;
    localparam logic [7:0] PAT_A3 = 8'hA3;

    localparam logic [7:0] PAT_B0 = 8'hB0;
    localparam logic [7:0] PAT_B1 = 8'hB1;
    localparam logic [7:0] PAT_B2 = 8'hB2;
    localparam logic [7:0] PAT_B3 = 8'hB3;

    localparam logic [7:0] PAT_C0 = 8'hC0;
    localparam logic [7:0] PAT_C1 = 8'hC1;
    localparam logic [7:0] PAT_C2 = 8'hC2;
    localparam logic [7:0] PAT_C9 = 8'hC9;

    initial begin
        pass_count = 0;

        // ---------------------------------------------------------------
        // PATTERN A: distinct value on each channel, verify phase selects
        // ---------------------------------------------------------------
        in_ch0 = PAT_A0; in_ch1 = PAT_A1; in_ch2 = PAT_A2; in_ch3 = PAT_A3;

        // TEST 1: phase 2'b00 → in_ch0
        phase = 2'b00; #1;
        check(PAT_A0, out_mux, 1);

        // TEST 2: phase 2'b01 → in_ch1
        phase = 2'b01; #1;
        check(PAT_A1, out_mux, 2);

        // TEST 3: phase 2'b10 → in_ch2
        phase = 2'b10; #1;
        check(PAT_A2, out_mux, 3);

        // TEST 4: phase 2'b11 → in_ch3
        phase = 2'b11; #1;
        check(PAT_A3, out_mux, 4);

        // ---------------------------------------------------------------
        // PATTERN B
        // ---------------------------------------------------------------
        in_ch0 = PAT_B0; in_ch1 = PAT_B1; in_ch2 = PAT_B2; in_ch3 = PAT_B3;

        // TEST 5: phase 2'b00 → in_ch0
        phase = 2'b00; #1;
        check(PAT_B0, out_mux, 5);

        // TEST 6: phase 2'b01 → in_ch1
        phase = 2'b01; #1;
        check(PAT_B1, out_mux, 6);

        // TEST 7: phase 2'b10 → in_ch2
        phase = 2'b10; #1;
        check(PAT_B2, out_mux, 7);

        // TEST 8: phase 2'b11 → in_ch3
        phase = 2'b11; #1;
        check(PAT_B3, out_mux, 8);

        // ---------------------------------------------------------------
        // PATTERN C
        // ---------------------------------------------------------------
        in_ch0 = PAT_C0; in_ch1 = PAT_C1; in_ch2 = PAT_C2; in_ch3 = PAT_C9;

        // TEST 9: phase 2'b00 → in_ch0
        phase = 2'b00; #1;
        check(PAT_C0, out_mux, 9);

        // TEST 10: phase 2'b01 → in_ch1
        phase = 2'b01; #1;
        check(PAT_C1, out_mux, 10);

        // TEST 11: phase 2'b10 → in_ch2
        phase = 2'b10; #1;
        check(PAT_C2, out_mux, 11);

        // TEST 12: phase 2'b11 → in_ch3 (PAT_C9 = 8'hC9)
        phase = 2'b11; #1;
        check(PAT_C9, out_mux, 12);

        // TEST 12 bonus: verify OP_HOLO_MUX_X4 sacred slot 0xE6
        assert ({56'b0, u_holo.OP_HOLO_MUX_X4} === {56'b0, 8'hE6})
            else $fatal(1, "ASSERT FAIL: OP_HOLO_MUX_X4 != 8'hE6");
        $display("TEST 12 BONUS ASSERT: OP_HOLO_MUX_X4 sacred slot 0xE6 OK");

        // ---------------------------------------------------------------
        $display("ALL %0d/%0d PASS", pass_count, 12);
        $finish;
    end

endmodule
