`default_nettype wire
`timescale 1ns / 1ps

// =============================================================================
// gf20_mul_ax7203 — GF20 ADD HW-conformance engine (1S+7E+12M, bias=63, no Inf).
// Same CFGMCLK/STARTUPE2/UART infrastructure as gf16_clean, but a WIDER frame:
// GF20 operands are 20-bit and do NOT fit the 16-bit frame, so this build uses a
// 9-byte request and 4-byte response:
//   Host -> FPGA: [0xAA][0x55][a_lo][a_mid][a_hi][b_lo][b_mid][b_hi][cmd]
//     op_a[19:0] = {a_hi[3:0], a_mid[7:0], a_lo[7:0]}  (same for op_b)
//   FPGA -> Host: [0xA5][r_lo][r_mid][r_hi]
//     result[19:0] = {r_hi[3:0], r_mid[7:0], r_lo[7:0]}
// Adder core = gf_mul_param #(EXP_BITS=7, MANT_BITS=12) (validated SW for all
// GF widths; HAS_INF=0 -> overflow saturates to max-finite). Matches
// conformance/gf20_add_conformance_ax7203.py.
// =============================================================================

// build trigger: push-initiated CI test
module gf20_mul_ax7203 (
    input  wire rst_n,
    input  wire uart_rx,
    output reg  uart_tx,
    output wire [3:0] led
);

    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b0),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b0),.USRDONEO(1'b0),.USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;
    localparam [8:0] BAUD_DIV = 9'd434;

    reg [26:0] cnt_c;
    always @(posedge mclk or posedge rst)
        if (rst) cnt_c <= 0; else cnt_c <= cnt_c + 1;
    assign led[0] = cnt_c[25];
    assign led[3] = ~rst;

    // ===== UART RX (PROVEN mid-bit sampling) =====
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst)
        if (rst) rsync <= 3'b111; else rsync <= {rsync[1:0], uart_rx};
    wire rxd = rsync[2];

    reg [1:0]  rxs;
    reg [9:0]  rxcnt;
    reg [3:0]  rbi;
    reg [7:0]  rxsr;
    reg [7:0]  rx_byte;
    reg        rx_new;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin rxs<=0; rxcnt<=0; rbi<=0; rxsr<=0; rx_byte<=0; rx_new<=0; end
        else begin
            rx_new <= 0;
            case (rxs)
                2'd0: if (~rxd) begin rxcnt <= (BAUD_DIV + (BAUD_DIV>>1)) - 1; rxs<=1; rbi<=0; end
                2'd1: begin
                    if (rxcnt==0) begin
                        rxsr <= {rxd, rxsr[7:1]};
                        if (rbi==7) begin rxs<=2; rxcnt<=BAUD_DIV-1; end
                        else begin rbi<=rbi+1; rxcnt<=BAUD_DIV-1; end
                    end else rxcnt<=rxcnt-1;
                end
                2'd2: begin
                    if (rxcnt==0) begin rx_byte<=rxsr; rx_new<=1; rxs<=0; end
                    else rxcnt<=rxcnt-1;
                end
                default: rxs<=0;
            endcase
        end
    end

    // ===== Frame assembly: 9-byte  AA 55 a_lo a_mid a_hi b_lo b_mid b_hi cmd =====
    reg [3:0] frm;
    reg [19:0] op_a, op_b;
    reg frame_valid;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin frm<=0; op_a<=0; op_b<=0; frame_valid<=0; end
        else begin
            frame_valid <= 0;
            if (rx_new) begin
                case (frm)
                    4'd0: frm <= (rx_byte==8'hAA) ? 4'd1 : 4'd0;
                    4'd1: frm <= (rx_byte==8'h55) ? 4'd2 : 4'd0;
                    4'd2: begin op_a[7:0]   <= rx_byte; frm <= 4'd3; end
                    4'd3: begin op_a[15:8]  <= rx_byte; frm <= 4'd4; end
                    4'd4: begin op_a[19:16] <= rx_byte; frm <= 4'd5; end
                    4'd5: begin op_b[7:0]   <= rx_byte; frm <= 4'd6; end
                    4'd6: begin op_b[15:8]  <= rx_byte; frm <= 4'd7; end
                    4'd7: begin op_b[19:16] <= rx_byte; frm <= 4'd8; end
                    4'd8: begin frame_valid <= 1; frm <= 4'd0; end
                endcase
            end
        end
    end

    // ===== GF20 adder (parametric core, HAS_INF=0) =====
    wire add_in_ready, add_out_valid;
    wire [19:0] add_out_y20;
    gf_mul_param #(.EXP_BITS(7), .MANT_BITS(12)) u_add (
        .clk(mclk), .rst(rst),
        .in_valid(frame_valid), .in_a(op_a[19:0]), .in_b(op_b[19:0]),
        .in_ready(add_in_ready), .out_valid(add_out_valid),
        .out_y(add_out_y20), .out_ready(1'b1));
    wire [19:0] result_y = add_out_y20;

    assign led[1] = frame_valid;
    assign led[2] = add_out_valid;

    // ===== UART TX: send [A5 r_lo r_mid r_hi] on add_out_valid (4 bytes) =====
    reg        responding;
    reg [1:0]  tx_idx;
    reg [7:0]  tx_buf0, tx_buf1, tx_buf2, tx_buf3;

    reg [8:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            responding<=0; tx_idx<=0;
            tcnt<=BAUD_DIV-1; tbi<=0; tsr<=10'h3FF; uart_tx<=1;
            tx_buf0<=8'hFF; tx_buf1<=8'hFF; tx_buf2<=8'hFF; tx_buf3<=8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (add_out_valid) begin
                tx_buf0 <= 8'hA5;
                tx_buf1 <= result_y[7:0];
                tx_buf2 <= result_y[15:8];
                tx_buf3 <= result_y[19:16];   // 4 bits in low nibble
                responding <= 1;
                tx_idx <= 0;
            end

            if (tcnt==0) begin
                tcnt <= BAUD_DIV-1;
                if (tbi==9) begin
                    tbi <= 0;
                    if (responding) begin
                        case (tx_idx)
                            2'd0: tsr <= {1'b1, tx_buf0, 1'b0};
                            2'd1: tsr <= {1'b1, tx_buf1, 1'b0};
                            2'd2: tsr <= {1'b1, tx_buf2, 1'b0};
                            2'd3: tsr <= {1'b1, tx_buf3, 1'b0};
                        endcase
                        if (tx_idx==3) responding <= 0;
                        else tx_idx <= tx_idx + 1;
                    end else begin
                        tsr <= 10'h3FF;  // idle (line high)
                    end
                end else begin
                    tbi <= tbi + 1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else begin
                tcnt <= tcnt - 1;
            end
        end
    end

endmodule

`default_nettype wire
