// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps

module ihp22fdx_adapter_tb;
    reg  [7:0] op;
    wire       use_ihp;
    wire       in_range;
    wire       is_ns;

    ihp22fdx_adapter dut (
        .sacred_opcode(op),
        .use_ihp22fdx_lib(use_ihp),
        .opcode_in_sacred_range(in_range),
        .is_node_shrink(is_ns)
    );

    integer errors;

    initial begin
        errors = 0;

        // A1: 0xEF triggers IHP 22FDX
        op = 8'hEF; #1;
        if (use_ihp !== 1'b1) begin $display("FAIL A1 use_ihp"); errors = errors + 1; end
        if (is_ns !== 1'b1) begin $display("FAIL A1 is_ns"); errors = errors + 1; end
        if (in_range !== 1'b1) begin $display("FAIL A1 in_range"); errors = errors + 1; end

        // A2: 0xE0 in sacred range but not node_shrink
        op = 8'hE0; #1;
        if (in_range !== 1'b1) begin $display("FAIL A2 in_range"); errors = errors + 1; end
        if (is_ns !== 1'b0) begin $display("FAIL A2 is_ns"); errors = errors + 1; end
        if (use_ihp !== 1'b0) begin $display("FAIL A2 use_ihp"); errors = errors + 1; end

        // A3: 0xED (SPARSE_MASK) sacred but not NODE_SHRINK
        op = 8'hED; #1;
        if (in_range !== 1'b1) begin $display("FAIL A3 in_range"); errors = errors + 1; end
        if (is_ns !== 1'b0) begin $display("FAIL A3 is_ns"); errors = errors + 1; end

        // A4: 0xDF not in sacred range
        op = 8'hDF; #1;
        if (in_range !== 1'b0) begin $display("FAIL A4 in_range"); errors = errors + 1; end
        if (use_ihp !== 1'b0) begin $display("FAIL A4 use_ihp"); errors = errors + 1; end

        // A5: 0xFF not in sacred range
        op = 8'hFF; #1;
        if (in_range !== 1'b0) begin $display("FAIL A5 in_range"); errors = errors + 1; end

        // A6: 0x00 not in sacred range, IHP off
        op = 8'h00; #1;
        if (use_ihp !== 1'b0) begin $display("FAIL A6 use_ihp"); errors = errors + 1; end
        if (in_range !== 1'b0) begin $display("FAIL A6 in_range"); errors = errors + 1; end

        if (errors == 0) begin
            $display("ALL 6 ASSERTIONS PASSED · phi^2+phi^-2=3 · OP_NODE_SHRINK=0xEF");
            $finish;
        end else begin
            $display("FAIL: %0d errors", errors);
            $fatal(1);
        end
    end
endmodule
