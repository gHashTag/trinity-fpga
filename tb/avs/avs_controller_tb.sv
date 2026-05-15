// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 gHashTag / TRI-1 Silicon Program
//
// Testbench : avs_controller_tb
// Purpose   : Verify avs_controller.sv -- W36 Lane W AVS-48 island reconfig FSM.
//             Targets W-105-B (latency ≤ 4 cycles), W-105-C (Vdd field 2 bits),
//             W-105-D (48 islands), plus 9 directed scenarios.
//
// R7 falsifier outputs: 12 directed PASSes printed; any FAIL -> $fatal(1).
//
// Sibling: rtl/avs/avs_controller.sv (this module's DUT).
// Pattern: tb/lut_npu/lut_npu_controller_tb.sv (W35 Lane V template).
//
// Author : Vasilev Dmitrii <admin@t27.ai>
// Wave   : Wave-36
// DOI    : 10.5281/zenodo.19227877
// ----------------------------------------------------------------------------

`default_nettype none
`timescale 1ns/1ps

module avs_controller_tb;

    // Parameters
    localparam integer N_ISLANDS = 48;
    localparam integer V_DD_BITS = 2;
    localparam [7:0]   OP_AVS_RECONF = 8'hE4;
    localparam [7:0]   OP_LUT_NPU    = 8'hE3;     // for opcode-mismatch test

    // DUT signals
    reg                       clk;
    reg                       rst_n;
    reg                       valid_in;
    reg  [7:0]                opcode;
    reg  [V_DD_BITS-1:0]      v_dd_target;
    reg  [N_ISLANDS-1:0]      island_mask_in;
    wire [V_DD_BITS-1:0]      v_dd_active;
    wire [N_ISLANDS-1:0]      island_enable;
    wire                      ack_out;
    wire                      valid_out;

    // Test bookkeeping
    integer test_count;
    integer pass_count;
    integer fail_count;
    integer latency_cycles;

    // Clock generation: 10 ns period
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // DUT instantiation
    avs_controller #(
        .N_ISLANDS             (N_ISLANDS),
        .V_DD_FIELD_WIDTH_BITS (V_DD_BITS)
    ) dut (
        .clk            (clk),
        .rst_n          (rst_n),
        .valid_in       (valid_in),
        .opcode         (opcode),
        .v_dd_target    (v_dd_target),
        .island_mask_in (island_mask_in),
        .v_dd_active    (v_dd_active),
        .island_enable  (island_enable),
        .ack_out        (ack_out),
        .valid_out      (valid_out)
    );

    // Helper: pulse valid_in for one cycle
    task pulse_request(
        input [7:0]                opc,
        input [V_DD_BITS-1:0]      vdd,
        input [N_ISLANDS-1:0]      mask
    );
        begin
            @(posedge clk);
            valid_in       <= 1'b1;
            opcode         <= opc;
            v_dd_target    <= vdd;
            island_mask_in <= mask;
            @(posedge clk);
            valid_in       <= 1'b0;
        end
    endtask

    // Helper: wait for ack_out, count cycles from request
    task wait_ack(output integer cycles);
        integer c;
        begin
            c = 0;
            while (!ack_out && c < 16) begin
                @(posedge clk);
                c = c + 1;
            end
            cycles = c;
        end
    endtask

    // Helper: check + count
    task check(input [255:0] name, input cond);
        begin
            test_count = test_count + 1;
            if (cond) begin
                pass_count = pass_count + 1;
                $display("  [PASS] T%0d %0s", test_count, name);
            end else begin
                fail_count = fail_count + 1;
                $display("  [FAIL] T%0d %0s", test_count, name);
            end
        end
    endtask

    initial begin
        // Init
        test_count     = 0;
        pass_count     = 0;
        fail_count     = 0;
        latency_cycles = 0;
        rst_n          = 1'b0;
        valid_in       = 1'b0;
        opcode         = 8'h00;
        v_dd_target    = 2'b01;
        island_mask_in = {N_ISLANDS{1'b1}};

        $display("================================================================");
        $display(" avs_controller_tb -- W36 Lane W AVS-48 directed verification");
        $display(" W-105-B latency ≤ 4 / W-105-C V_dd 2-bit / W-105-D 48 islands");
        $display("================================================================");

        // Reset for 4 cycles
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // -------------------------------------------------------------------
        // T1: After reset, defaults are nominal (v_dd = 2'b01, all enabled)
        // -------------------------------------------------------------------
        check("reset defaults v_dd=01",  v_dd_active   == 2'b01);
        check("reset defaults mask=all", island_enable == {N_ISLANDS{1'b1}});

        // -------------------------------------------------------------------
        // T3: Valid OP_AVS_RECONF -> ack within ≤ 4 cycles (W-105-B)
        // -------------------------------------------------------------------
        pulse_request(OP_AVS_RECONF, 2'b10, {N_ISLANDS{1'b1}});
        wait_ack(latency_cycles);
        check("W-105-B latency <= 4 cycles", latency_cycles <= 4);

        // -------------------------------------------------------------------
        // T4: v_dd_active updated to boost (2'b10)
        // -------------------------------------------------------------------
        check("v_dd switched to boost", v_dd_active == 2'b10);

        @(posedge clk);
        // Settle
        repeat (2) @(posedge clk);

        // -------------------------------------------------------------------
        // T5: Switch to turbo (2'b11), keep all islands
        // -------------------------------------------------------------------
        pulse_request(OP_AVS_RECONF, 2'b11, {N_ISLANDS{1'b1}});
        wait_ack(latency_cycles);
        check("turbo switch latency <= 4", latency_cycles <= 4);
        check("v_dd switched to turbo", v_dd_active == 2'b11);

        repeat (2) @(posedge clk);

        // -------------------------------------------------------------------
        // T7: Switch to low-power (2'b00), disable 8 islands (strand-0 head)
        // -------------------------------------------------------------------
        pulse_request(OP_AVS_RECONF, 2'b00, ~(48'h0000_0000_00FF));
        wait_ack(latency_cycles);
        check("low-power switch latency <= 4", latency_cycles <= 4);
        check("v_dd switched to low-power", v_dd_active == 2'b00);
        check("8 islands disabled", island_enable == ~(48'h0000_0000_00FF));

        repeat (2) @(posedge clk);

        // -------------------------------------------------------------------
        // T10: Wrong opcode (OP_LUT_NPU) must be ignored
        // -------------------------------------------------------------------
        pulse_request(OP_LUT_NPU, 2'b11, {N_ISLANDS{1'b1}});
        // Should remain in S_IDLE, no ack, v_dd stays at 2'b00
        repeat (4) @(posedge clk);
        check("wrong opcode no ack", ack_out == 1'b0);
        check("wrong opcode v_dd unchanged", v_dd_active == 2'b00);

        // -------------------------------------------------------------------
        // T12: Restore nominal full-mask
        // -------------------------------------------------------------------
        pulse_request(OP_AVS_RECONF, 2'b01, {N_ISLANDS{1'b1}});
        wait_ack(latency_cycles);
        check("restore nominal latency <= 4", latency_cycles <= 4);
        check("restore nominal v_dd=01", v_dd_active == 2'b01);

        repeat (4) @(posedge clk);

        // Verdict
        $display("----------------------------------------------------------------");
        $display(" TESTS: %0d  PASS: %0d  FAIL: %0d", test_count, pass_count, fail_count);
        $display("----------------------------------------------------------------");
        if (fail_count == 0 && pass_count >= 12) begin
            $display(" VERDICT: PASS  (W-105-B/C/D structural + 9 directed all green)");
            $display(" phi^2 + phi^-2 = 3  /  DOI 10.5281/zenodo.19227877  /  NEVER STOP");
            $finish;
        end else begin
            $display(" VERDICT: FAIL");
            $fatal(1);
        end
    end

    // Hard timeout
    initial begin
        #10000;
        $display("VERDICT: FAIL -- testbench timeout");
        $fatal(1);
    end

endmodule

`default_nettype wire
