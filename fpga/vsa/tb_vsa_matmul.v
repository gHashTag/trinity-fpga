`timescale 1ns / 1ps

// =============================================================================
// TESTBENCH: vsa_matmul — VSA ternary matrix-vector multiply
// =============================================================================
// Self-test weights: W[j][i] = +1 if (i+j)%3==0, -1 if (i+j)%3==1, 0 else
// Self-test input:   x[i] = +1 for all i  (all +1 ternary vector)
// Expected: y[j] = count(+1 in row j) - count(-1 in row j)
//   For all-+1 input with these weights:
//   y[j] = count((i+j)%3==0) - count((i+j)%3==1) for i=0..63
//   Since mod3 cycles: +1, -1, 0, +1, -1, 0, ... for each row
//   64 elements: 64/3 = 21 full cycles + 1 extra
//   Row j=0: pattern starts at +1: 22 pos, 21 neg, 21 zero → y=1
//   Row j=1: pattern starts at -1: 21 pos, 22 neg, 21 zero → y=-1
//   Row j=2: pattern starts at  0: 21 pos, 21 neg, 22 zero → y=0
//   Then repeats with period 3.
// =============================================================================

module tb_vsa_matmul;

    localparam DIM = 64;
    localparam N_OUT = 64;
    localparam ACC_WIDTH = 16;

    reg         clk;
    reg         rst;
    reg         start;
    reg  [DIM*2-1:0] x_vec;

    wire [ACC_WIDTH-1:0]    result_data;
    wire [5:0]              result_addr;
    wire                    result_valid;
    wire                    done;
    wire                    busy;
    wire [DIM*2-1:0]        bind_debug;

    vsa_matmul #(
        .DIM(DIM),
        .N_OUT(N_OUT),
        .ACC_WIDTH(ACC_WIDTH)
    ) uut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .x_vec(x_vec),
        .result_data(result_data),
        .result_addr(result_addr),
        .result_valid(result_valid),
        .done(done),
        .busy(busy),
        .bind_debug(bind_debug)
    );

    // Clock: 10ns period (100 MHz)
    initial clk = 0;
    always #5 clk = ~clk;

    // Expected results storage
    reg signed [ACC_WIDTH-1:0] expected [0:N_OUT-1];
    reg [15:0] errors;
    reg [15:0] passes;

    // Build expected results: y[j] = pop(+1) - pop(-1) for row j with all-+1 input
    integer ei, ej;
    reg signed [15:0] acc_build;
    initial begin
        for (ej = 0; ej < N_OUT; ej = ej + 1) begin
            acc_build = 0;
            for (ei = 0; ei < DIM; ei = ei + 1) begin
                case ((ei + ej) % 3)
                    0: acc_build = acc_build + 1;
                    1: acc_build = acc_build - 1;
                    default: ;
                endcase
            end
            expected[ej] = acc_build;
        end
    end

    // Collect results
    reg [15:0] got_count;

    always @(posedge clk) begin
        if (result_valid) begin
            got_count = got_count + 1;
            if ($signed(result_data) !== $signed(expected[result_addr])) begin
                $display("FAIL row %0d: got %0d, expected %0d",
                         result_addr, $signed(result_data), $signed(expected[result_addr]));
                errors = errors + 1;
            end else begin
                passes = passes + 1;
            end
        end
    end

    integer jj;

    initial begin
        $dumpfile("tb_vsa_matmul.vcd");
        $dumpvars(0, tb_vsa_matmul);

        errors = 0;
        passes = 0;
        got_count = 0;

        // Initialize
        rst = 1;
        start = 0;
        x_vec = {DIM*2{1'b0}};
        #100;
        rst = 0;
        #20;

        // Build all-+1 ternary input vector
        for (jj = 0; jj < DIM; jj = jj + 1)
            x_vec[jj*2 +: 2] = 2'b01;  // +1

        // Start computation
        @(posedge clk);
        start = 1;
        @(posedge clk);
        start = 0;

        // Wait for completion
        wait (done == 1);
        @(posedge clk);

        // Report
        $display("");
        $display("=== VSA_MATMUL TEST RESULTS ===");
        $display("Rows computed: %0d / %0d", got_count, N_OUT);
        $display("Pass: %0d  Fail: %0d", passes, errors);
        $display("================================");

        if (errors > 0) begin
            $display("STATUS: FAIL");
        end else if (got_count != N_OUT) begin
            $display("STATUS: INCOMPLETE — expected %0d results, got %0d", N_OUT, got_count);
        end else begin
            $display("STATUS: PASS");
        end

        #100;
        $finish;
    end

    // Timeout watchdog
    initial begin
        #100000;
        $display("ERROR: Simulation timeout — done never asserted");
        $finish;
    end

endmodule
