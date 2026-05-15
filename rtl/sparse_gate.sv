// Wave-41 Lane HH — Sparse-Activation Gating module
// OP_SPARSE_SKIP = 8'hE8 — R-SI-1 unique sacred opcode
// Skips MAC when |activation| < tau_decoded and topk_keep=0
// tau_decoded = {3'b000, tau[4:0]} << tau[7:5]  (5-bit mantissa, 3-bit exp)
// anchor: phi^2 + phi^-2 = 3  · DOI 10.5281/zenodo.19227877

module sparse_gate (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [7:0]  opcode,
    input  logic [15:0] activation,    // signed magnitude; bit[15]=sign, [14:0]=magnitude
    input  logic [7:0]  tau,           // 3-bit exp [7:5] + 5-bit mantissa [4:0]
    input  logic        topk_keep,     // force-keep override (1 = never skip)
    output logic        skip_o,        // 1 = skip MAC, 0 = execute
    output logic        mac_clk_en     // clock-gate enable for downstream multiplier
);

    localparam logic [7:0] OP_SPARSE_SKIP = 8'hE8;

    // --- tau decode: {3'b000, tau[4:0]} << tau[7:5] ---
    // Max shift = 7, mantissa = 5 bits → decoded value fits in 12 bits
    logic [11:0] tau_decoded;
    assign tau_decoded = 12'({7'b000_0000, tau[4:0]} << tau[7:5]);

    // --- |activation|: bit[15] is sign, bits[14:0] are magnitude ---
    logic [14:0] act_mag;
    assign act_mag = activation[14:0];

    // --- combinational skip decision ---
    logic skip_comb;
    always_comb begin
        if (opcode == OP_SPARSE_SKIP && topk_keep == 1'b0 && ({1'b0, act_mag} < {1'b0, tau_decoded}))
            skip_comb = 1'b1;
        else
            skip_comb = 1'b0;
    end

    // --- registered outputs (single-cycle, no pipeline) ---
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            skip_o     <= 1'b0;
            mac_clk_en <= 1'b1;
        end else begin
            skip_o     <= skip_comb;
            mac_clk_en <= ~skip_comb;
        end
    end

    // --- 32-bit sparsity telemetry counter ---
    // Increments every cycle that skip is asserted (using skip_comb so it counts
    // the same cycle the skip decision is made, before the registered output)
    logic [31:0] sparsity_cnt;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sparsity_cnt <= 32'b0;
        end else if (skip_comb) begin
            sparsity_cnt <= sparsity_cnt + 32'b1;
        end
    end

endmodule
