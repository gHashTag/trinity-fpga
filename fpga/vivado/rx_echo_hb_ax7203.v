`default_nettype wire

// =============================================================================
// rx_echo_hb_ax7203 — RX-direction isolator on CFGMCLK (proven clock)
// =============================================================================
// Goal: decide whether the host->FPGA UART RX wire (P20) is alive, ISOLATED
// from the 200 MHz clock (this design uses only CFGMCLK). Two observables on
// uart_tx (N15), so "0 echo" is unambiguous:
//   * when RX is idle: stream a monotonic CFGMCLK heartbeat byte cnt_c[26:19]
//     (presence => design runs; advance => CFGMCLK alive — the CONTROL).
//   * when a byte is received on uart_rx (P20): echo that byte on uart_tx.
// Test: host sends 0x55 / 0xAA at ~160000 baud, reads the TX stream.
//   heartbeat present + 0x55/0xAA echoed   -> RX wire ALIVE (echo proven)
//   heartbeat present + no 0x55/0xAA       -> RX wire / P20 DEAD (real blocker)
//   garbled byte instead of clean 0x55     -> baud/framing on RX (tune)
//   no heartbeat at all                    -> design not running (test failed)
// Both RX and TX on CFGMCLK with the same BAUD_DIV, so RX/TX baud match.
// =============================================================================

`timescale 1ns / 1ps

module rx_echo_hb_ax7203 (
    input  wire rst_n,
    input  wire uart_rx,   // P20  host -> FPGA
    output reg  uart_tx    // N15  FPGA -> host
);

    wire mclk, eos;
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) u_startup (
        .CFGCLK(),
        .CFGMCLK(mclk),
        .EOS(eos),
        .CLK(1'b0),
        .GSR(1'b0),
        .GTS(1'b0),
        .KEYCLEARB(1'b0),
        .PACK(1'b0),
        .USRCCLKO(1'b0),
        .USRCCLKTS(1'b0),
        .USRDONEO(1'b0),
        .USRDONETS(1'b0)
    );

    wire rst = ~rst_n | ~eos;

    localparam [8:0] BAUD_DIV   = 9'd434;     // ~70 MHz / 434 ~= 161290 baud
    localparam [9:0] HALF_START = 10'd651;    // 1.5 * 434 -> mid of bit0

    // -------------------------------------------------------------------------
    // CFGMCLK counter (heartbeat source)
    // -------------------------------------------------------------------------
    reg [26:0] cnt_c;
    always @(posedge mclk or posedge rst) begin
        if (rst) cnt_c <= 27'd0;
        else     cnt_c <= cnt_c + 27'd1;
    end
    wire [7:0] hb = cnt_c[26:19];             // monotonic heartbeat byte

    // -------------------------------------------------------------------------
    // uart_rx synchronizer
    // -------------------------------------------------------------------------
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) begin
        if (rst) rsync <= 3'b111;
        else     rsync <= {rsync[1:0], uart_rx};
    end
    wire rxd = rsync[2];

    // -------------------------------------------------------------------------
    // UART RX: mid-bit sample, LSB first -> rx_byte + rx_new pulse
    // -------------------------------------------------------------------------
    reg [2:0] rxs;        // 0=idle 1=data 2=stop
    reg [9:0] rcnt;
    reg [2:0] rbi;
    reg [7:0] rxsr;
    reg [7:0] rx_byte;
    reg       rx_new;
    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            rxs <= 3'd0; rcnt <= 10'd0; rbi <= 3'd0; rxsr <= 8'd0;
            rx_byte <= 8'd0; rx_new <= 1'b0;
        end else begin
            rx_new <= 1'b0;
            case (rxs)
                3'd0: if (~rxd) begin
                          rcnt <= HALF_START - 10'd1; rxs <= 3'd1; rbi <= 3'd0;
                      end
                3'd1: begin
                          if (rcnt == 10'd0) begin
                              rxsr <= {rxd, rxsr[7:1]};
                              if (rbi == 3'd7) begin rxs <= 3'd2; rcnt <= BAUD_DIV - 9'd1; end
                              else             begin rbi <= rbi + 3'd1; rcnt <= BAUD_DIV - 9'd1; end
                          end else rcnt <= rcnt - 10'd1;
                      end
                3'd2: begin
                          if (rcnt == 10'd0) begin rx_byte <= rxsr; rx_new <= 1'b1; rxs <= 3'd0; end
                          else rcnt <= rcnt - 10'd1;
                      end
                default: rxs <= 3'd0;
            endcase
        end
    end

    // -------------------------------------------------------------------------
    // UART TX + echo arbiter (single driver for echo_pending/echo_byte).
    // Streams {stop, byte, start}; byte = echo_byte if a byte is pending, else
    // the heartbeat hb. echo_pending set on rx_new, cleared when the echo is sent.
    // -------------------------------------------------------------------------
    reg [8:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;
    reg        echo_pending;
    reg [7:0]  echo_byte;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            tcnt <= BAUD_DIV - 9'd1;
            tbi  <= 4'd0;
            tsr  <= 10'b1111111111;   // idle line
            uart_tx <= 1'b1;
            echo_pending <= 1'b0;
            echo_byte <= 8'd0;
        end else begin
            uart_tx <= tsr[0];
            if (tcnt == 9'd0) begin
                tcnt <= BAUD_DIV - 9'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (echo_pending) tsr <= {1'b1, echo_byte, 1'b0};
                    else              tsr <= {1'b1, hb,       1'b0};
                    // consumed the echo this byte (overridden by rx_new below)
                    echo_pending <= 1'b0;
                end else begin
                    tbi <= tbi + 4'd1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else begin
                tcnt <= tcnt - 9'd1;
            end
            // latch a freshly received byte (priority over the consume-clear)
            if (rx_new) begin
                echo_byte    <= rx_byte;
                echo_pending <= 1'b1;
            end
        end
    end

endmodule

`default_nettype wire
