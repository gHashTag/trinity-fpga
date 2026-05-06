`default_nettype wire

// =============================================================================
// VSA_MATMUL_TOP — Synthesizable top for QMTECH XC7A100T
// =============================================================================
// Autoregressive ternary inference:
//   seed_token -> Embedding (ternary LUT) -> VSA MatMul -> Argmax -> next token
//   Loop MAX_GEN tokens, stream results over UART
//
// Architecture:
//   - vsa_matmul: 64x64 ternary matmul (XOR + popcount, 0 DSP48)
//   - UART TX: 115200 baud, binary frame
//   - LED heartbeat
//   - MMCM: 50 MHz -> 81.25 MHz
//
// phi^2 + 1/phi^2 = 3 = TRINITY
// =============================================================================

`timescale 1ns / 1ps

module vsa_matmul_top (
    input  wire clk50,
    input  wire uart_rx,
    output wire uart_tx,
    output wire led,
    output reg [1:0] debug_state
);

    localparam DIM       = 64;
    localparam N_OUT     = 64;
    localparam ACC_WIDTH = 16;
    localparam VOCAB     = 64;
    localparam MAX_GEN   = 16;

    // =========================================================================
    // MMCM — 50 MHz -> 81.25 MHz
    // =========================================================================
    wire clk81;
    wire mmcm_locked;

    PLLE2_BASE #(
        .CLKIN1_PERIOD    (20.0),
        .CLKFBOUT_MULT    (13),
        .CLKOUT0_DIVIDE   (8),
        .DIVCLK_DIVIDE    (1)
    ) mmcm_inst (
        .CLKIN1   (clk50),
        .CLKOUT0  (clk81),
        .LOCKED   (mmcm_locked),
        .CLKFBOUT (),
        .CLKFBIN  (),
        .PWRDWN   (1'b0),
        .RST      (1'b0)
    );

    wire clk = clk81;
    wire rst = ~mmcm_locked;

    // =========================================================================
    // LED HEARTBEAT — blink at ~2 Hz
    // =========================================================================
    reg [24:0] led_cnt;
    always @(posedge clk) begin
        if (rst) led_cnt <= 0;
        else     led_cnt <= led_cnt + 1;
    end
    assign led = led_cnt[24];

    // =========================================================================
    // TERNARY EMBEDDING — token_id -> 64-trit vector (register-based)
    // =========================================================================
    integer ei, ej;
    reg [DIM*2-1:0] embed_rom [0:VOCAB-1];
    initial begin
        for (ei = 0; ei < VOCAB; ei = ei + 1) begin
            for (ej = 0; ej < DIM; ej = ej + 1) begin
                case ((ei + ej) % 3)
                    0: embed_rom[ei][ej*2 +: 2] = 2'b01;
                    1: embed_rom[ei][ej*2 +: 2] = 2'b10;
                    default: embed_rom[ei][ej*2 +: 2] = 2'b00;
                endcase
            end
        end
    end

    // =========================================================================
    // AUTOREGRESSIVE STATE MACHINE
    // =========================================================================
    localparam S_RESET   = 3'd0;
    localparam S_EMBED   = 3'd1;
    localparam S_MATMUL  = 3'd2;
    localparam S_ARGMAX  = 3'd3;
    localparam S_REPORT  = 3'd4;
    localparam S_NEXT    = 3'd5;
    localparam S_DONE    = 3'd6;

    reg [2:0]   state;
    reg [6:0]   token_id;
    reg [3:0]   gen_count;
    reg [DIM*2-1:0] x_vec;
    reg         matmul_start;
    wire        matmul_done;
    wire        matmul_busy;
    wire [ACC_WIDTH-1:0]  matmul_data;
    wire [5:0]           matmul_addr;
    wire                 matmul_valid;

    reg [ACC_WIDTH-1:0]  logits [0:N_OUT-1];
    reg [6:0]   best_token;
    reg [ACC_WIDTH-1:0] best_score;
    reg [4:0]   uart_byte_cnt;

    // =========================================================================
    // VSA MATMUL INSTANCE
    // =========================================================================
    wire [DIM*2-1:0] bind_debug;

    vsa_matmul #(
        .DIM(DIM),
        .N_OUT(N_OUT),
        .ACC_WIDTH(ACC_WIDTH)
    ) matmul_inst (
        .clk(clk),
        .rst(rst),
        .start(matmul_start),
        .x_vec(x_vec),
        .result_data(matmul_data),
        .result_addr(matmul_addr),
        .result_valid(matmul_valid),
        .done(matmul_done),
        .busy(matmul_busy),
        .bind_debug(bind_debug)
    );

    // Latch matmul results into logits array
    always @(posedge clk) begin
        if (matmul_valid) begin
            logits[matmul_addr] <= matmul_data;
        end
    end

    // =========================================================================
    // ARGMAX — find highest logit
    // =========================================================================
    reg [6:0] am_idx;
    reg [ACC_WIDTH-1:0] am_best;
    reg [6:0] am_best_idx;

    // =========================================================================
    // UART TX — 115200 baud, simple state machine
    // =========================================================================
    localparam UART_DIV = 81_250_000 / 115200;

    reg [15:0] uart_cnt;
    reg [3:0]  uart_bit;
    reg [7:0]  uart_shift;
    reg        uart_active;
    reg        uart_tx_reg;
    reg        uart_start_tx;

    assign uart_tx = uart_tx_reg;

    wire uart_done_tx;
    assign uart_done_tx = (uart_active == 0);

    always @(posedge clk) begin
        if (rst) begin
            uart_tx_reg <= 1'b1;
            uart_active <= 1'b0;
            uart_cnt    <= 0;
            uart_bit    <= 0;
            uart_shift  <= 0;
            uart_start_tx <= 1'b0;
        end else begin
            uart_start_tx <= 1'b0;
            if (uart_active) begin
                if (uart_cnt == UART_DIV - 1) begin
                    uart_cnt <= 0;
                    if (uart_bit == 0) begin
                        uart_tx_reg <= 1'b0;
                        uart_bit <= uart_bit + 1;
                    end else if (uart_bit < 9) begin
                        uart_tx_reg <= uart_shift[0];
                        uart_shift <= {1'b0, uart_shift[7:1]};
                        uart_bit <= uart_bit + 1;
                    end else begin
                        uart_tx_reg <= 1'b1;
                        uart_active <= 1'b0;
                        uart_bit <= 0;
                    end
                end else begin
                    uart_cnt <= uart_cnt + 1;
                end
            end else if (uart_start_tx) begin
                uart_tx_reg <= 1'b0;
                uart_active <= 1'b1;
                uart_cnt    <= 0;
                uart_bit    <= 0;
            end else begin
                uart_tx_reg <= 1'b1;
            end
        end
    end

    // =========================================================================
    // MAIN FSM
    // =========================================================================
    reg [7:0] report_byte;

    always @(posedge clk) begin
        if (rst) begin
            state         <= S_RESET;
            matmul_start  <= 1'b0;
            token_id      <= 7'd42;
            gen_count     <= 4'd0;
            best_token    <= 7'd0;
            best_score    <= {ACC_WIDTH{1'b0}};
            debug_state   <= 2'b00;
            uart_byte_cnt <= 5'd0;
            am_idx        <= 7'd0;
            report_byte   <= 8'd0;
        end else begin
            matmul_start <= 1'b0;

            case (state)
                S_RESET: begin
                    debug_state <= 2'b00;
                    if (mmcm_locked) begin
                        state <= S_EMBED;
                    end
                end

                S_EMBED: begin
                    debug_state <= 2'b01;
                    x_vec <= embed_rom[token_id % VOCAB];
                    state <= S_MATMUL;
                end

                S_MATMUL: begin
                    debug_state <= 2'b01;
                    if (matmul_busy == 0 && matmul_done == 0) begin
                        matmul_start <= 1'b1;
                    end else if (matmul_done) begin
                        state    <= S_ARGMAX;
                        am_idx   <= 7'd0;
                        am_best  <= {ACC_WIDTH{1'b0}};
                        am_best_idx <= 7'd0;
                    end
                end

                S_ARGMAX: begin
                    debug_state <= 2'b10;
                    if ($signed(logits[am_idx]) > $signed(am_best)) begin
                        am_best     <= logits[am_idx];
                        am_best_idx <= am_idx;
                    end
                    if (am_idx == N_OUT - 1) begin
                        best_token <= am_best_idx;
                        best_score <= am_best;
                        state      <= S_REPORT;
                        uart_byte_cnt <= 5'd0;
                    end else begin
                        am_idx <= am_idx + 1;
                    end
                end

                S_REPORT: begin
                    debug_state <= 2'b10;
                    if (!uart_active) begin
                        case (uart_byte_cnt)
                            5'd0:  report_byte <= 8'hAA;
                            5'd1:  report_byte <= 8'hBB;
                            5'd2:  report_byte <= 8'hFE;
                            5'd3:  report_byte <= 8'h01;
                            5'd4:  report_byte <= token_id[7:0];
                            5'd5:  report_byte <= best_token[7:0];
                            5'd6:  report_byte <= best_score[15:8];
                            5'd7:  report_byte <= best_score[7:0];
                            5'd8:  report_byte <= gen_count;
                            5'd9:  report_byte <= 8'hFF;
                            default: report_byte <= 8'h00;
                        endcase

                        if (uart_byte_cnt < 5'd10) begin
                            uart_shift  <= report_byte;
                            uart_start_tx <= 1'b1;
                            uart_byte_cnt <= uart_byte_cnt + 1;
                        end else begin
                            state <= S_NEXT;
                        end
                    end
                end

                S_NEXT: begin
                    token_id <= best_token;
                    gen_count <= gen_count + 1;
                    if (gen_count >= MAX_GEN - 1) begin
                        state <= S_DONE;
                    end else begin
                        state <= S_EMBED;
                    end
                end

                S_DONE: begin
                    debug_state <= 2'b11;
                end

                default: state <= S_RESET;
            endcase
        end
    end

endmodule
