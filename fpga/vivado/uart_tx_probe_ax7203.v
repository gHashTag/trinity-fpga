`default_nettype wire

// =============================================================================
// uart_tx_probe_ax7203 — UART TX heartbeat probe (camera-independent)
// =============================================================================
// Streams 0x55 ('U') back-to-back on uart_tx (pin N15) to verify the FPGA->host
// UART TX electrical path WITHOUT relying on the camera (the user-LED bank is
// outside the camera FOV). Clock = STARTUPE2 CFGMCLK (same isolated, proven path
// as led_onehot) so a successful read isolates the UART path, not the clock.
//
// CFGMCLK is part-dependent (~32-98 MHz), so the actual baud scales with it
// (nominal 115200 at 50 MHz -> ~74k..226k across the range). The host therefore
// SWEEPS baud rates and reads BOTH candidate serial ports:
//   /dev/cu.usbserial-120           (on-board CP2102N UART)
//   /dev/cu.usbserial-210512180081  (AL321 FT2232H channel B)
// Repeating "UUUU..." on a port => that port is the working host-RX path AND the
// design is running (CFGMCLK + fabric + uart_tx pin all functional).
//
// PARALLEL VISUAL: LED1..LED4 walk (identical proven onehot logic), so a human
// observer confirms the bitstream loaded/ran independently of the UART path:
//   walk visible + UART bytes => both observers agree
//   walk visible + no bytes    => UART TX path (N15) isolated as the fault
//   no walk                     => configuration problem (not the UART path)
//
// Success here proves ONLY this design's infrastructure; it does NOT verify the
// 200 MHz differential path (gf16) — that remains a separate test.
// =============================================================================

`timescale 1ns / 1ps

module uart_tx_probe_ax7203 (
    input  wire rst_n,
    output reg  [3:0] led,
    output reg  uart_tx
);

    // -------------------------------------------------------------------------
    // Internal config master clock via STARTUPE2 (same as led_onehot)
    // -------------------------------------------------------------------------
    wire mclk;
    wire eos;
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

    // -------------------------------------------------------------------------
    // LED walking (proven from led_onehot) — parallel visual "design alive"
    // -------------------------------------------------------------------------
    reg [26:0] cnt;
    reg [2:0]  phase;
    reg        cnt26_d;
    wire       step = cnt[26] & ~cnt26_d;   // rising edge -> phase advance

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            cnt     <= 27'd0;
            phase   <= 3'd0;
            cnt26_d <= 1'b0;
        end else begin
            cnt     <= cnt + 27'd1;
            cnt26_d <= cnt[26];
            if (step)
                phase <= (phase == 3'd4) ? 3'd0 : (phase + 3'd1);
        end
    end

    always @(*) begin
        case (phase)
            3'd0: led = 4'b0001; // LED1 (B13)
            3'd1: led = 4'b0010; // LED2 (C13)
            3'd2: led = 4'b0100; // LED3 (D14)
            3'd3: led = 4'b1000; // LED4 (D15)
            default: led = 4'b0000; // OFF
        endcase
    end

    // -------------------------------------------------------------------------
    // UART TX: stream 0x55 back-to-back at nominal 115200 (50 MHz CFGMCLK)
    // Frame (LSB-first out of shreg[0]): start(0), d0..d7, stop(1)
    // 0x55 = d7..d0 = 0101_0101, so frame = stop,0,1,0,1,0,1,0,1,start
    //                                = 1_01010101_0 ... bit layout => 10'b1010101010
    // -------------------------------------------------------------------------
    localparam [8:0] BAUD_DIV    = 9'd434;          // 50 MHz / 115200 ~= 434
    localparam [9:0] FRAME_0x55  = 10'b1010101010;

    reg [8:0] baud_cnt;
    reg [3:0] bit_idx;                               // 0..9 (start + 8 data + stop)
    reg [9:0] shreg;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            baud_cnt <= 9'd0;
            bit_idx  <= 4'd0;
            shreg    <= FRAME_0x55;
            uart_tx  <= 1'b1;                        // idle line high
        end else begin
            uart_tx <= shreg[0];                     // emit current LSB
            if (baud_cnt == BAUD_DIV - 9'd1) begin
                baud_cnt <= 9'd0;
                if (bit_idx == 4'd9) begin
                    bit_idx <= 4'd0;
                    shreg   <= FRAME_0x55;           // next byte frame
                end else begin
                    bit_idx <= bit_idx + 4'd1;
                    shreg   <= {1'b1, shreg[9:1]};   // shift right, feed stop/idle
                end
            end else begin
                baud_cnt <= baud_cnt + 9'd1;
            end
        end
    end

endmodule

`default_nettype wire
