`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// tnf16_board_ax7203 -- TNF16 add and mul on the ALINX AX7203, over the UART.
//
// Spec: specs/trinet/tnf16_on_board_ax7203.t27. Every constant here is a
// `TNF16_* macro from fpga/tnet/tnf16_board_params.v, generated from it; list
// that file first, then fpga/tnet/tnf16_core.v, then this one.
//
// The UART receiver and transmitter are the TRI-NET node's
// (fpga/portable/trinet_node_core.v), same divider on the same CFGMCLK, so the
// link is the one that carried 403200/403200 node jobs at 1144744 baud.
//
// Request  SYNC0 SYNC1 OP SEQ a0 a1 a2 b0 b1 b2   operands little-endian;
//          bits above the 19-bit word are ignored.
// Response RESP_OK SEQ y0 y1 y2, or RESP_BADOP SEQ 0 0 0 for an unknown OP.
//
// One response buffer is enough: a request is 10 byte frames on the wire, a
// response waits at most one frame for the transmitter and then takes 5, and
// the core answers in `TNF16_CORE_STAGES clocks, far inside one bit. If a
// result still arrives while the buffer is busy, led[2] latches on.
//
// led[0] heartbeat, led[1] toggles per request, led[2] overrun, led[3] out of reset.
//=============================================================================
module tnf16_board_ax7203 (
    input  wire       rst_n,
    input  wire       uart_rx,
    output reg        uart_tx,
    output wire [3:0] led
);
    localparam integer W = `TNF16_WORD_BITS;
    localparam [9:0] BAUD_DIV = `TNF16_BAUD_DIV;
    localparam [7:0] SYNC0 = `TNF16_SYNC0, SYNC1 = `TNF16_SYNC1;
    localparam [7:0] RESP_OK = `TNF16_RESP_OK, RESP_BADOP = `TNF16_RESP_BADOP;

    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b0), .USRDONEO(1'b0), .USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;

    reg [26:0] beat;
    always @(posedge mclk or posedge rst) if (rst) beat <= 27'd0; else beat <= beat + 27'd1;

    //-------------------------------------------------------------------------
    // UART receive (trinet_node_core.v).
    //-------------------------------------------------------------------------
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst)
        if (rst) rsync <= 3'b111; else rsync <= {rsync[1:0], uart_rx};
    wire rxd = rsync[2];

    reg [1:0] rxs;
    reg [9:0] rxcnt;
    reg [3:0] rbi;
    reg [7:0] rxsr, rx_byte;
    reg       rx_new;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            rxs <= 2'd0; rxcnt <= 10'd0; rbi <= 4'd0;
            rxsr <= 8'd0; rx_byte <= 8'd0; rx_new <= 1'b0;
        end else begin
            rx_new <= 1'b0;
            case (rxs)
                2'd0: if (~rxd) begin
                          rxcnt <= (BAUD_DIV + (BAUD_DIV >> 1)) - 10'd1;
                          rxs <= 2'd1; rbi <= 4'd0;
                      end
                2'd1: if (rxcnt == 10'd0) begin
                          rxsr <= {rxd, rxsr[7:1]};
                          if (rbi == 4'd7) begin rxs <= 2'd2; rxcnt <= BAUD_DIV - 10'd1; end
                          else            begin rbi <= rbi + 4'd1; rxcnt <= BAUD_DIV - 10'd1; end
                      end else rxcnt <= rxcnt - 10'd1;
                2'd2: if (rxcnt == 10'd0) begin
                          rx_byte <= rxsr; rx_new <= 1'b1; rxs <= 2'd0;
                      end else rxcnt <= rxcnt - 10'd1;
                default: rxs <= 2'd0;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // Frame parser: SYNC0 SYNC1, then 8 body bytes. SYNC0 SYNC0 SYNC1 resyncs.
    //-------------------------------------------------------------------------
    localparam [1:0] F_MAGIC0 = 2'd0, F_MAGIC1 = 2'd1, F_BODY = 2'd2;

    reg [1:0] fstate;
    reg [2:0] bidx;
    reg [7:0] op_r, seq_r;
    reg [7:0] a_b [0:2];
    reg [7:0] b_b [0:2];
    reg       frame_valid, frame_toggle;

    integer ini;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            fstate <= F_MAGIC0; bidx <= 3'd0; op_r <= 8'd0; seq_r <= 8'd0;
            frame_valid <= 1'b0; frame_toggle <= 1'b0;
            for (ini = 0; ini < 3; ini = ini + 1) begin a_b[ini] <= 8'd0; b_b[ini] <= 8'd0; end
        end else begin
            frame_valid <= 1'b0;
            if (rx_new) begin
                case (fstate)
                    F_MAGIC0: fstate <= (rx_byte == SYNC0) ? F_MAGIC1 : F_MAGIC0;
                    F_MAGIC1: begin
                        if (rx_byte == SYNC1) begin fstate <= F_BODY; bidx <= 3'd0; end
                        else if (rx_byte == SYNC0) fstate <= F_MAGIC1;
                        else fstate <= F_MAGIC0;
                    end
                    F_BODY: begin
                        case (bidx)
                            3'd0: op_r   <= rx_byte;
                            3'd1: seq_r  <= rx_byte;
                            3'd2: a_b[0] <= rx_byte;
                            3'd3: a_b[1] <= rx_byte;
                            3'd4: a_b[2] <= rx_byte;
                            3'd5: b_b[0] <= rx_byte;
                            3'd6: b_b[1] <= rx_byte;
                            default: b_b[2] <= rx_byte;
                        endcase
                        if (bidx == 3'd7) begin
                            frame_valid <= 1'b1; frame_toggle <= ~frame_toggle;
                            fstate <= F_MAGIC0; bidx <= 3'd0;
                        end else bidx <= bidx + 3'd1;
                    end
                    default: fstate <= F_MAGIC0;
                endcase
            end
        end
    end

    //-------------------------------------------------------------------------
    // TNF16 core.
    //-------------------------------------------------------------------------
    wire [W-1:0] in_a = {a_b[2], a_b[1], a_b[0]};
    wire [W-1:0] in_b = {b_b[2], b_b[1], b_b[0]};
    wire         out_valid, out_badop;
    wire [W-1:0] out_y;
    reg  [7:0]   seq_q;
    always @(posedge mclk or posedge rst)
        if (rst) seq_q <= 8'd0; else if (frame_valid) seq_q <= seq_r;

    tnf16_core u_core (
        .clk(mclk), .rst(rst),
        .in_valid(frame_valid), .in_op(op_r), .in_a(in_a), .in_b(in_b),
        .out_valid(out_valid), .out_badop(out_badop), .out_y(out_y)
    );

    //-------------------------------------------------------------------------
    // UART transmit (trinet_node_core.v): 5-byte response.
    //-------------------------------------------------------------------------
    reg        responding, overrun;
    reg [2:0]  tx_idx;
    reg [7:0]  tx_buf [0:4];
    reg [9:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    integer ti;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            responding <= 1'b0; overrun <= 1'b0; tx_idx <= 3'd0; tcnt <= BAUD_DIV - 10'd1;
            tbi <= 4'd0; tsr <= 10'h3FF; uart_tx <= 1'b1;
            for (ti = 0; ti < 5; ti = ti + 1) tx_buf[ti] <= 8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (out_valid) begin
                if (responding) overrun <= 1'b1;
                tx_buf[0] <= out_badop ? RESP_BADOP : RESP_OK;
                tx_buf[1] <= seq_q;
                tx_buf[2] <= out_y[7:0];
                tx_buf[3] <= out_y[15:8];
                tx_buf[4] <= {{(24 - W){1'b0}}, out_y[W-1:16]};
                responding <= 1'b1;
                tx_idx     <= 3'd0;
            end

            if (tcnt == 10'd0) begin
                tcnt <= BAUD_DIV - 10'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (responding && !out_valid) begin
                        tsr <= {1'b1, tx_buf[tx_idx], 1'b0};
                        if (tx_idx == 3'd4) responding <= 1'b0;
                        else tx_idx <= tx_idx + 3'd1;
                    end else tsr <= 10'h3FF;
                end else begin
                    tbi <= tbi + 4'd1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else tcnt <= tcnt - 10'd1;
        end
    end

    assign led[0] = beat[25];
    assign led[1] = frame_toggle;
    assign led[2] = overrun;
    assign led[3] = ~rst;
endmodule
`default_nettype wire
