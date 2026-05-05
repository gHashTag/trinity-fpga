`default_nettype wire

module tb_vsa_ops;

    localparam DIM  = 64;
    localparam BW   = DIM * 2;
    localparam TCLK = 10;

    reg                  clk, rst;
    reg                  valid_in;
    reg  [1:0]           op;
    reg  [BW-1:0]        a, b;
    wire                 valid_out;
    wire [BW-1:0]        result;
    wire                 led;

    vsa_top #(.DIM(DIM)) dut (
        .clk(clk), .rst(rst), .op(op),
        .valid_in(valid_in), .a(a), .b(b),
        .valid_out(valid_out), .result(result),
        .led(led)
    );

    initial begin
        clk = 0;
        forever #(TCLK/2) clk = ~clk;
    end

    integer pass_count;
    integer fail_count;

    task apply_and_check;
        input [BW-1:0] expected;
        input [640:0]   label;
    begin
        valid_in = 1;
        @(posedge clk);
        valid_in = 0;
        @(posedge clk);
        @(posedge clk);
        #(TCLK/2);
        if (result === expected) begin
            pass_count = pass_count + 1;
            $display("PASS %0s", label);
        end else begin
            fail_count = fail_count + 1;
            $display("FAIL %0s", label);
            $display("  expected: %h", expected);
            $display("  got:      %h", result);
        end
        #(TCLK);
    end
    endtask

    function [1:0] trit_mult;
        input [1:0] a_t, b_t;
    begin
        case ({a_t, b_t})
            4'b00_00: trit_mult = 2'b00;
            4'b00_01: trit_mult = 2'b01;
            4'b00_10: trit_mult = 2'b10;
            4'b01_00: trit_mult = 2'b01;
            4'b01_01: trit_mult = 2'b01;
            4'b01_10: trit_mult = 2'b10;
            4'b10_00: trit_mult = 2'b10;
            4'b10_01: trit_mult = 2'b10;
            4'b10_10: trit_mult = 2'b01;
            default:  trit_mult = 2'b00;
        endcase
    end
    endfunction

    function [1:0] trit_bundle;
        input [1:0] a_t, b_t;
    begin
        case ({a_t, b_t})
            4'b00_00: trit_bundle = 2'b00;
            4'b00_01: trit_bundle = 2'b01;
            4'b00_10: trit_bundle = 2'b10;
            4'b01_00: trit_bundle = 2'b01;
            4'b01_01: trit_bundle = 2'b01;
            4'b01_10: trit_bundle = 2'b00;
            4'b10_00: trit_bundle = 2'b10;
            4'b10_01: trit_bundle = 2'b00;
            4'b10_10: trit_bundle = 2'b10;
            default:  trit_bundle = 2'b00;
        endcase
    end
    endfunction

    reg [BW-1:0] expected;
    reg [BW-1:0] bound_vec;
    reg [BW-1:0] ab_result;
    integer k;

    initial begin
        $dumpfile("tb_vsa_ops.vcd");
        $dumpvars(0, dut);

        pass_count = 0;
        fail_count = 0;

        rst = 1;
        valid_in = 0;
        op = 0;
        a = {BW{1'b0}};
        b = {BW{1'b0}};
        #(TCLK * 10);
        rst = 0;
        #(TCLK * 4);

        $display("=== VSA Ops Testbench (DIM=%0d) ===", DIM);

        $display("--- Test 1: BIND +1 * +1 = +1 ---");
        op = 2'd0;
        a = {BW{2'b01}};
        b = {BW{2'b01}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bind_pos_pos");

        $display("--- Test 2: BIND 0 passthrough ---");
        a = {BW{2'b00}};
        b = {BW{2'b01}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bind_zero_passthrough");

        $display("--- Test 3: BIND -1 * +1 = -1 ---");
        a = {BW{2'b10}};
        b = {BW{2'b01}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bind_neg_pos");

        $display("--- Test 4: BIND -1 * -1 = +1 ---");
        a = {BW{2'b10}};
        b = {BW{2'b10}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bind_neg_neg");

        $display("--- Test 5: UNBIND self-inverse ---");
        a = {BW{2'b01}};
        b = {BW{2'b10}};
        for (k = 0; k < DIM; k = k + 1)
            bound_vec[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        op = 2'd0;
        a = {BW{2'b01}};
        b = {BW{2'b10}};
        valid_in = 1;
        @(posedge clk);
        valid_in = 0;
        @(posedge clk);
        @(posedge clk);
        #(TCLK/2);
        bound_vec = result;
        #(TCLK);

        op = 2'd1;
        a = bound_vec;
        b = {BW{2'b10}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(bound_vec[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "unbind_self_inverse");

        $display("--- Test 6: BUNDLE +1 + +1 = +1 ---");
        op = 2'd2;
        a = {BW{2'b01}};
        b = {BW{2'b01}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_bundle(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bundle_pos_pos");

        $display("--- Test 7: BUNDLE -1 + +1 = 0 ---");
        a = {BW{2'b10}};
        b = {BW{2'b01}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_bundle(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bundle_neg_pos");

        $display("--- Test 8: BUNDLE 0 passthrough ---");
        a = {BW{2'b00}};
        b = {BW{2'b10}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_bundle(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bundle_zero_passthrough");

        $display("--- Test 9: BIND commutativity ---");
        op = 2'd0;
        a = {{(BW/4){2'b01}}, {(BW/4){2'b10}}, {(BW/4){2'b00}}, {(BW/4){2'b01}}};
        b = {{(BW/4){2'b10}}, {(BW/4){2'b00}}, {(BW/4){2'b01}}, {(BW/4){2'b01}}};
        for (k = 0; k < DIM; k = k + 1)
            expected[k*2 +: 2] = trit_mult(a[k*2 +: 2], b[k*2 +: 2]);
        apply_and_check(expected, "bind_commutativity_a_b");
        ab_result = result;
        #(TCLK);

        a = {{(BW/4){2'b10}}, {(BW/4){2'b00}}, {(BW/4){2'b01}}, {(BW/4){2'b01}}};
        b = {{(BW/4){2'b01}}, {(BW/4){2'b10}}, {(BW/4){2'b00}}, {(BW/4){2'b01}}};
        apply_and_check(ab_result, "bind_commutativity_b_a");

        #(TCLK * 4);

        $display("");
        $display("=== RESULTS ===");
        $display("PASS: %0d", pass_count);
        $display("FAIL: %0d", fail_count);
        if (fail_count == 0)
            $display("ALL TESTS PASSED");
        else
            $display("SOME TESTS FAILED");

        $finish;
    end

endmodule
