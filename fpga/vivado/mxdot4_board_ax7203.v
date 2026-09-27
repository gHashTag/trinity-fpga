`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// mxdot4_board_ax7203 -- 32-element block dot products, MXFP4 and TNF4, on the
// ALINX AX7203, over the UART.
//
// Spec: specs/trinet/mxdot4_on_board_ax7203.t27. Every constant here is a
// `MXDOT4_* macro from fpga/tnet/mxdot4_board_params.v, generated from it; list
// that file first, then fpga/tnet/mxdot4_core.v, then this one.
//
// The UART receiver and transmitter are the TRI-NET node's
// (fpga/portable/trinet_node_core.v), as in fpga/vivado/tnf16_board_ax7203.v:
// same divider on the same CFGMCLK, the link that carried 1035886/1035886
// TNF16 requests at 1144744 baud.
//
// Request  SYNC0 SYNC1 OP SEQ SA SB A0..A15 B0..B15   element 2j in the low
//          nibble of byte j, 2j+1 in the high nibble.
// Response RESP_OK SEQ y0 y1 y2 (word little-endian), or RESP_BADOP SEQ 0 0 0.
//
// One response buffer is enough: a request is 38 byte frames on the wire, a
// response waits at most one frame for the transmitter and then takes 5, and
// the core answers in `MXDOT4_CORE_STAGES clocks. If a result still arrives
// while the buffer is busy, led[2] latches on.
//
// FORMATS goes to the core: 3 on the board; 1 and 2 build the one-format tops
// whose timing is compared.
//
// led[0] heartbeat, led[1] toggles per request, led[2] overrun, led[3] out of reset.
//=============================================================================
module mxdot4_board_ax7203 #(
    parameter integer FORMATS = 3
) (
    input  wire       rst_n,
    input  wire       uart_rx,
    output reg        uart_tx,
    output wire [3:0] led
);
    localparam integer W = `MXDOT4_WORD_BITS;
    localparam integer NB = `MXDOT4_REQ_BYTES - 2;       // body bytes after the two SYNCs
    localparam integer BW = `MXDOT4_BLOCK * `MXDOT4_ELEM_BITS;
    localparam [9:0] BAUD_DIV = `MXDOT4_BAUD_DIV;
    localparam [7:0] SYNC0 = `MXDOT4_SYNC0, SYNC1 = `MXDOT4_SYNC1;
    localparam [7:0] RESP_OK = `MXDOT4_RESP_OK, RESP_BADOP = `MXDOT4_RESP_BADOP;

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
    // Frame parser: SYNC0 SYNC1, then NB body bytes shifted in from the top, so
    // body byte k ends at body[8k+7:8k]. SYNC0 SYNC0 SYNC1 resyncs.
    //-------------------------------------------------------------------------
    localparam [1:0] F_MAGIC0 = 2'd0, F_MAGIC1 = 2'd1, F_BODY = 2'd2;

    reg [1:0]      fstate;
    reg [5:0]      bidx;
    reg [8*NB-1:0] body;
    reg            frame_valid, frame_toggle;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            fstate <= F_MAGIC0; bidx <= 6'd0; body <= {8*NB{1'b0}};
            frame_valid <= 1'b0; frame_toggle <= 1'b0;
        end else begin
            frame_valid <= 1'b0;
            if (rx_new) begin
                case (fstate)
                    F_MAGIC0: fstate <= (rx_byte == SYNC0) ? F_MAGIC1 : F_MAGIC0;
                    F_MAGIC1: begin
                        if (rx_byte == SYNC1) begin fstate <= F_BODY; bidx <= 6'd0; end
                        else if (rx_byte == SYNC0) fstate <= F_MAGIC1;
                        else fstate <= F_MAGIC0;
                    end
                    F_BODY: begin
                        body <= {rx_byte, body[8*NB-1:8]};
                        if (bidx == NB - 1) begin
                            frame_valid <= 1'b1; frame_toggle <= ~frame_toggle;
                            fstate <= F_MAGIC0; bidx <= 6'd0;
                        end else bidx <= bidx + 6'd1;
                    end
                    default: fstate <= F_MAGIC0;
                endcase
            end
        end
    end

    //-------------------------------------------------------------------------
    // Core. OP SEQ SA SB are body bytes 0..3, A bytes 4..19, B bytes 20..35.
    //-------------------------------------------------------------------------
    wire         out_valid, out_badop;
    wire [W-1:0] out_y;
    reg  [7:0]   seq_q;
    always @(posedge mclk or posedge rst)
        if (rst) seq_q <= 8'd0; else if (frame_valid) seq_q <= body[15:8];

    mxdot4_core #(.FORMATS(FORMATS)) u_core (
        .clk(mclk), .rst(rst), .in_valid(frame_valid),
        .in_op(body[7:0]), .in_sa(body[23:16]), .in_sb(body[31:24]),
        .in_a(body[32 +: BW]), .in_b(body[32 + BW +: BW]),
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
                tx_buf[4] <= out_y[23:16];
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
