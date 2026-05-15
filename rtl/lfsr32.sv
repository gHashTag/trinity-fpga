// Wave-42 Lane JJ — 32-bit Galois LFSR
// OP_STOCH_ROUND = 8'hE9  — entropy source for stochastic rounding
// Taps: 0x80200003  (positions 32, 22, 2, 1)
// Maximum-period 2^32-1 guaranteed (primitive polynomial over GF(2))
// Default reset seed = 32'hACE1ACE1
// anchor: phi^2 + phi^-2 = 3  · DOI 10.5281/zenodo.19227877

module lfsr32 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [31:0] seed,       // external seed value
    input  logic        seed_load,  // 1 = load seed this cycle
    output logic [31:0] lfsr_o      // current LFSR state
);

    // Galois LFSR tap mask
    // Polynomial: x^32 + x^22 + x^2 + x^1 + 1
    // Tap positions 32,22,2,1  => mask 0x80200003
    localparam logic [31:0] TAPS = 32'h80200003;

    // Default seed — never zero (zero is the forbidden absorbing state)
    localparam logic [31:0] DEFAULT_SEED = 32'hACE1ACE1;

    logic [31:0] lfsr_r;

    // Galois LFSR: shift right by 1; XOR tap mask when output bit (LSB) = 1
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr_r <= DEFAULT_SEED;
        end else if (seed_load) begin
            // Load external seed; guard against forbidden zero state
            lfsr_r <= (seed == 32'h0) ? DEFAULT_SEED : seed;
        end else begin
            if (lfsr_r[0])
                lfsr_r <= (lfsr_r >> 1) ^ TAPS;
            else
                lfsr_r <= (lfsr_r >> 1);
        end
    end

    assign lfsr_o = lfsr_r;

endmodule
