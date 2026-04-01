// Ternary MAC Cell — Dot Product Unit (BENCH-006)
// Computes: y += w·x for 16-dimensional vectors
// w[i], x[i] in {-1, 0, +1} (ternary, 2-bit encoding)
// Result: y in {-16..+16} (5-bit signed)

`default_nettype none

module ternary_mac_16_top #(
    parameter LATENCY = 2
)(
    // ========================================================================
    // Clock and Reset
    // ========================================================================
    input  wire clk,
    input  wire rst_n,

    // ========================================================================
    // ACCUM Interface (Ready-Valid Handshake)
    // ========================================================================
    input  wire valid,      // Data ready from upstream
    output wire ready,      // Ready to accept new data

    // ========================================================================
    // Data Ports
    // ========================================================================
    input  wire [31:0] w,   // 16 × 2-bit ternary weights (10=-1, 00=0, 01=+1)
    input  wire [31:0] x,   // 16 × 2-bit ternary inputs
    output wire [15:0] y,   // Accumulator output (signed, {-16..+16} in lower bits)

    // ========================================================================
    // Status
    // ========================================================================
    output wire overflow,   // Accumulator saturation detected
    output wire led         // Status LED (T23, active-low)
);

    // ========================================================================
    // Ternary Encoding
    // ========================================================================
    // 2 bits encode 3 values:
    //   10 = -1 (negative)
    //   00 =  0 (zero)
    //   01 = +1 (positive)
    //   11 = unused (treated as 0)
    //
    // Product table (w × x):
    //   -1 × -1 = +1
    //   -1 ×  0 =  0
    //   -1 × +1 = -1
    //    0 ×  X =  0
    //   +1 × -1 = -1
    //   +1 ×  0 =  0
    //   +1 × +1 = +1

    // ========================================================================
    // INPUT REGISTERS (for fair Fmax measurement)
    // ========================================================================
    reg [31:0] w_reg;
    reg [31:0] x_reg;
    reg valid_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            w_reg <= 32'h0;
            x_reg <= 32'h0;
            valid_reg <= 1'b0;
        end else if (ready) begin
            w_reg <= w;
            x_reg <= x;
            valid_reg <= valid;
        end
    end

    // ========================================================================
    // TERNARY PRODUCT ARRAY (16 parallel ternary multipliers)
    // ========================================================================
    // Each trit is 2 bits, product is also a trit {-1,0,+1}
    // Using XOR for sign: (-1)*(-1)=+1, (-1)*(+1)=-1

    wire signed [1:0] prod [16];  // -1, 0, or +1 for each product

    genvar i;
    generate for (i = 0; i < 16; i = i + 1) begin : gen_prod
        wire [1:0] w_trit = w_reg[2*i +: 2];
        wire [1:0] x_trit = x_reg[2*i +: 2];

        // Decode trits to signed values
        wire w_is_neg = (w_trit == 2'b10);
        wire w_is_pos = (w_trit == 2'b01);
        wire w_is_zero = (w_trit == 2'b00) | (w_trit == 2'b11);

        wire x_is_neg = (x_trit == 2'b10);
        wire x_is_pos = (x_trit == 2'b01);
        wire x_is_zero = (x_trit == 2'b00) | (x_trit == 2'b11);

        // Product: if either is zero, product is zero
        // else: signs equal = +1, signs different = -1
        wire prod_is_zero = w_is_zero | x_is_zero;
        wire prod_is_pos = (w_is_pos & x_is_pos) | (w_is_neg & x_is_neg);
        wire prod_is_neg = (w_is_pos & x_is_neg) | (w_is_neg & x_is_pos);

        assign prod[i] = prod_is_zero ? 2'sb00 :
                         prod_is_pos ? 2'sb01 :
                         2'sb11;  // -1 in 2's complement
    end
    endgenerate

    // ========================================================================
    // ADDER TREE (accumulate 16 ternary products)
    // ========================================================================
    // Sum range: -16 to +16 (5-bit signed)
    // Using tree structure for better timing

    // Level 1: 8 adds (3 bits each: -2..+2)
    wire signed [2:0] sum_l1 [8];
    generate for (i = 0; i < 8; i = i + 1) begin : gen_l1
        assign sum_l1[i] = prod[2*i] + prod[2*i+1];
    end
    endgenerate

    // Level 2: 4 adds (4 bits each: -4..+4)
    wire signed [3:0] sum_l2 [4];
    generate for (i = 0; i < 4; i = i + 1) begin : gen_l2
        assign sum_l2[i] = sum_l1[2*i] + sum_l1[2*i+1];
    end
    endgenerate

    // Level 3: 2 adds (5 bits each: -8..+8)
    wire signed [4:0] sum_l3 [2];
    generate for (i = 0; i < 2; i = i + 1) begin : gen_l3
        assign sum_l3[i] = sum_l2[2*i] + sum_l2[2*i+1];
    end
    endgenerate

    // Level 4: final add (6 bits: -16..+16)
    wire signed [5:0] sum_raw = sum_l3[0] + sum_l3[1];

    // ========================================================================
    // ACCUMULATOR with saturation
    // ========================================================================
    // Accumulates results over multiple cycles
    // Range: -32..+31 after 2 accumulations (6-bit signed)
    // Saturates at -16..+16 for single output

    reg signed [5:0] acc;
    reg overflow_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc <= 6'sd0;
            overflow_reg <= 1'b0;
        end else if (ready && valid_reg) begin
            // Add new product sum to accumulator
            acc <= acc + sum_raw;
            // Detect overflow (outside -16..+16 range)
            overflow_reg <= (acc + sum_raw < 6'sd16) | (acc + sum_raw > 6'sd15);
        end
    end

    // ========================================================================
    // OUTPUT REGISTER (for fair Fmax measurement)
    // ========================================================================
    reg signed [5:0] y_reg;
    reg overflow_reg_out;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y_reg <= 6'sd0;
            overflow_reg_out <= 1'b0;
        end else begin
            y_reg <= acc;
            overflow_reg_out <= overflow_reg;
        end
    end

    // ========================================================================
    // OUTPUTS
    // ========================================================================
    assign y = {10'h0, y_reg};  // Zero-extend to 16 bits
    assign overflow = overflow_reg_out;
    assign ready = 1'b1;  // Always ready (no backpressure)

    // ========================================================================
    // STATUS LED — T23 (active-low, D6)
    // ========================================================================
    assign led = rst_n ? 1'b0 : 1'b1;  // ON when not reset

endmodule
