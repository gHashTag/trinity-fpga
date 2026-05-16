// =============================================================================
// Testbench: int2_packer_tb
// Wave 43, Lane MM -- S-180 + S-181
// Tests: int2_unpacker, int2_pack_sram_iface, int2_col13_gate
// =============================================================================
module int2_packer_tb;

    // -------------------------------------------------------------------------
    // DUT signals
    // -------------------------------------------------------------------------
    logic [1:0]       code_in;
    logic [3:0]       int4_out;

    logic [1:0]       act0, act1, act2, act3;
    logic [7:0]       sram_word;

    logic signed [3:0] act_int4_in;
    logic [1:0]        code_out;

    integer errors;

    // -------------------------------------------------------------------------
    // Instantiations
    // -------------------------------------------------------------------------
    int2_unpacker u_unpacker (
        .code    (code_in),
        .int4_act(int4_out)
    );

    int2_pack_sram_iface u_packer (
        .act0     (act0),
        .act1     (act1),
        .act2     (act2),
        .act3     (act3),
        .sram_word(sram_word)
    );

    int2_col13_gate u_gate (
        .act_int4(act_int4_in),
        .code    (code_out)
    );

    // -------------------------------------------------------------------------
    // Test tasks
    // -------------------------------------------------------------------------
    task check_unpack;
        input [1:0] c;
        input signed [3:0] expected;
        input [63:0] test_id;
        begin
            code_in = c;
            #1;
            if (int4_out !== expected) begin
                $display("FAIL Test %0d: int2_unpacker(2'b%02b) = 4'b%04b, expected 4'b%04b",
                         test_id, c, int4_out, expected);
                errors = errors + 1;
            end else begin
                $display("PASS Test %0d: int2_unpacker(2'b%02b) = 4'b%04b", test_id, c, int4_out);
            end
        end
    endtask

    task check_gate;
        input signed [3:0] act;
        input [1:0] expected_code;
        input [63:0] test_id;
        begin
            act_int4_in = act;
            #1;
            if (code_out !== expected_code) begin
                $display("FAIL Test %0d: int2_col13_gate(4'sb%04b) = 2'b%02b, expected 2'b%02b",
                         test_id, act, code_out, expected_code);
                errors = errors + 1;
            end else begin
                $display("PASS Test %0d: int2_col13_gate(4'sb%04b) = 2'b%02b", test_id, act, code_out);
            end
        end
    endtask

    // -------------------------------------------------------------------------
    // Main test sequence
    // -------------------------------------------------------------------------
    initial begin
        errors = 0;

        // Test 1: int2_unpacker code=2'b00 -> -1 => 4'sb1111
        check_unpack(2'b00, 4'sb1111, 1);

        // Test 2: int2_unpacker code=2'b01 -> 0 => 4'sb0000
        check_unpack(2'b01, 4'sb0000, 2);

        // Test 3: int2_unpacker code=2'b10 -> phi^-1 approx => 4'b0011 (+3)
        check_unpack(2'b10, 4'b0011, 3);

        // Test 4: int2_unpacker code=2'b11 -> +1 => 4'sb0001
        check_unpack(2'b11, 4'sb0001, 4);

        // Test 5: int2_pack_sram_iface -- verify bit packing
        // act0=2'b01, act1=2'b10, act2=2'b11, act3=2'b00 -> sram_word = 8'b00_11_10_01
        act0 = 2'b01;
        act1 = 2'b10;
        act2 = 2'b11;
        act3 = 2'b00;
        #1;
        if (sram_word !== 8'b00111001) begin
            $display("FAIL Test 5: pack({00,11,10,01}) = 8'b%08b, expected 8'b00111001", sram_word);
            errors = errors + 1;
        end else begin
            $display("PASS Test 5: pack({00,11,10,01}) = 8'b%08b", sram_word);
        end

        // Test 6: int2_col13_gate(4'sb0000 = 0) -> code 2'b01
        check_gate(4'sb0000, 2'b01, 6);

        // Test 7: int2_col13_gate(4'sb0111 = +7, max positive) -> code 2'b11 (+1 region)
        check_gate(4'sb0111, 2'b11, 7);

        // Test 8: int2_col13_gate(4'sb1001 = -7, negative) -> code 2'b00 (-1 region)
        check_gate(4'sb1001, 2'b00, 8);

        // Summary
        if (errors == 0)
            $display("ALL TESTS PASSED (8/8)");
        else
            $display("FAILURES: %0d / 8 tests failed", errors);

        $finish;
    end

endmodule
