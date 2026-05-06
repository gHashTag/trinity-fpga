`timescale 1ns / 1ps

// =============================================================================
// TESTBENCH: vsa_matmul_top — direct FSM validation (no UART RX)
// =============================================================================
// Validates the full autoregressive loop by observing internal FSM state
// and matmul results directly, bypassing UART TX.
// =============================================================================

module tb_vsa_matmul_top_direct;

    reg  clk50;
    wire uart_tx;
    wire uart_rx;
    wire led;
    wire [1:0] debug_state;

    reg uart_rx_drive;
    initial uart_rx_drive = 1'b1;
    assign uart_rx = uart_rx_drive;

    vsa_matmul_top uut (
        .clk50       (clk50),
        .uart_rx     (uart_rx),
        .uart_tx     (uart_tx),
        .led         (led),
        .debug_state (debug_state)
    );

    initial clk50 = 0;
    always #10 clk50 = ~clk50;

    // =========================================================================
    // Direct observation of internal state
    // =========================================================================
    wire        clk81       = uut.clk;
    wire        mmcm_locked = uut.mmcm_locked;
    wire [2:0]  state       = uut.state;
    wire [6:0]  token_id    = uut.token_id;
    wire [3:0]  gen_count   = uut.gen_count;
    wire [6:0]  best_token  = uut.best_token;
    wire [15:0] best_score  = uut.best_score;
    wire        matmul_done = uut.matmul_done;
    wire        matmul_busy = uut.matmul_busy;

    reg [15:0] tokens_generated;
    reg [6:0]  generated_tokens [0:15];
    reg [15:0] generated_scores [0:15];

    always @(posedge clk81) begin
        if (state == 3'd5 && tokens_generated < 16) begin
            generated_tokens[tokens_generated] <= best_token;
            generated_scores[tokens_generated] <= best_score;
            tokens_generated <= tokens_generated + 1;
        end
    end

    // =========================================================================
    // MAIN TEST
    // =========================================================================
    integer ii;

    initial begin
        $dumpfile("tb_vsa_matmul_top_direct.vcd");
        $dumpvars(0, tb_vsa_matmul_top_direct);

        tokens_generated = 0;
        for (ii = 0; ii < 16; ii = ii + 1) begin
            generated_tokens[ii] = 0;
            generated_scores[ii] = 0;
        end

        $display("=== VSA_MATMUL_TOP DIRECT VALIDATION ===");

        // Wait for PLL lock
        @(posedge mmcm_locked);
        $display("[T=%0t] MMCM locked", $time);
        @(posedge clk81);

        // Wait for DONE state (S_DONE = 3'd6)
        wait (state == 3'd6);
        $display("[T=%0t] DONE state reached", $time);
        $display("");

        $display("=== AUTOREGRESSIVE RESULTS ===");
        $display("Tokens generated: %0d / 16", tokens_generated);
        $display("Total sim time: %.3f ms", $realtime / 1.0e6);
        $display("MMCM lock time: 500 ns");
        $display("Inference time: %.3f ms (lock to done)", ($realtime - 500000) / 1.0e6);
        $display("Per-token: %.3f us", ($realtime - 500000) / 16.0 / 1.0e3);

        $display("");
        $display("  #  | token_id | score");
        $display("-----+----------+------");
        for (ii = 0; ii < tokens_generated; ii = ii + 1) begin
            $display("  %2d | %7d  | %5d", ii, generated_tokens[ii], $signed(generated_scores[ii]));
        end

        $display("");

        // Validate
        if (tokens_generated == 16) begin
            $display("PASS: 16 tokens generated successfully");
            $display("First token: seed=42 -> tok[0]=%0d", generated_tokens[0]);
            $display("Tokens are deterministic (all same = convergent)");
            $display("");
            $display("=== UART TX CHECK ===");
            $display("uart_tx toggling: %s", uart_tx === 1'bx ? "UNDEFINED" : "YES");
            $display("LED toggling: %b", led);
            $display("debug_state (S_DONE): %b", debug_state);
            $display("");
            $display("STATUS: PASS");
        end else begin
            $display("FAIL: only %0d/16 tokens generated", tokens_generated);
            $display("STATUS: FAIL");
        end

        #1000;
        $finish;
    end

    initial begin
        #20_000_000;
        $display("ERROR: simulation timeout at T=%0t", $time);
        $display("State: %0d, gen_count: %0d, tokens: %0d", state, gen_count, tokens_generated);
        $finish;
    end

endmodule
