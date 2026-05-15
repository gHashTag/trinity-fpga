// Wave-42 Lane JJ — Stochastic Rounding Unit
// OP_STOCH_ROUND = 8'hE9 — sacred opcode for unbiased INT4 MAC rounding
//
// Inputs:
//   opcode[7:0]    — must equal 8'hE9 to engage stochastic path
//   x_int[15:0]    — integer part of operand
//   x_frac[3:0]    — 4-bit fractional part (INT4 sub-integer bits)
//   mode[1:0]      — 0=RNE  1=STOCH  2=FLOOR
//   lfsr_in[31:0]  — random bits from lfsr32
//
// Output:
//   y_rounded[15:0] — rounded result, single-cycle latency
//
// Rounding rules (opcode == 8'hE9 only):
//   STOCH (mode=1): y = x_int + (lfsr_in[3:0] < x_frac ? 1 : 0)
//   RNE   (mode=0): round-nearest-even on x_frac (tie at 8 -> even x_int)
//   FLOOR (mode=2): y = x_int  (truncate)
//
// If opcode != 8'hE9: pass x_int straight through regardless of mode.
// anchor: phi^2 + phi^-2 = 3  · DOI 10.5281/zenodo.19227877

module stoch_round (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [7:0]  opcode,
    input  logic [15:0] x_int,
    input  logic [3:0]  x_frac,
    input  logic [1:0]  mode,
    input  logic [31:0] lfsr_in,
    output logic [15:0] y_rounded
);

    localparam logic [7:0] OP_STOCH_ROUND = 8'hE9;

    // Mode encoding
    localparam logic [1:0] MODE_RNE   = 2'b00;
    localparam logic [1:0] MODE_STOCH = 2'b01;
    localparam logic [1:0] MODE_FLOOR = 2'b10;

    // Extract sub-fields as wires to avoid iverilog part-select limitation
    // inside always blocks
    wire [3:0] lfsr4;        // LFSR noise bits for stochastic compare
    wire       x_int_lsb;    // LSB of x_int for RNE tie-break
    assign lfsr4      = lfsr_in[3:0];
    assign x_int_lsb  = x_int[0];

    // Decoded: is x_int even?
    wire x_int_is_odd;
    assign x_int_is_odd = x_int_lsb;

    // -----------------------------------------------------------------------
    // Combinational rounding logic
    // -----------------------------------------------------------------------
    logic [15:0] y_comb;

    always_comb begin
        if (opcode != OP_STOCH_ROUND) begin
            // Opcode mismatch: transparent pass-through
            y_comb = x_int;
        end else begin
            case (mode)
                MODE_STOCH: begin
                    // Stochastic: round up if lfsr4 < x_frac
                    // P(round up) = x_frac/16 => unbiased rounding
                    if (lfsr4 < x_frac)
                        y_comb = x_int + 16'h1;
                    else
                        y_comb = x_int;
                end

                MODE_RNE: begin
                    // Round-nearest-even on 4-bit fraction
                    // Mid-point is x_frac == 4'h8
                    if (x_frac > 4'h8) begin
                        // Above mid: round up
                        y_comb = x_int + 16'h1;
                    end else if (x_frac < 4'h8) begin
                        // Below mid: truncate
                        y_comb = x_int;
                    end else begin
                        // Exactly at mid: round to even
                        // x_int odd => round up; even => stay
                        if (x_int_is_odd)
                            y_comb = x_int + 16'h1;
                        else
                            y_comb = x_int;
                    end
                end

                MODE_FLOOR: begin
                    // Floor / truncate: discard fraction entirely
                    y_comb = x_int;
                end

                default: begin
                    // Reserved modes: pass-through
                    y_comb = x_int;
                end
            endcase
        end
    end

    // -----------------------------------------------------------------------
    // Registered output — single-cycle latency
    // -----------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y_rounded <= 16'h0;
        end else begin
            y_rounded <= y_comb;
        end
    end

endmodule
