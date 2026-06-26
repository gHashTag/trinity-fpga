`default_nettype wire

// =============================================================================
// uart_tx_probe_ax7203 — UART TX probe (camera-independent, fabric-proving)
// =============================================================================
// Streams a MONOTONIC COUNTER BYTE (cnt[26:19]) back-to-back on uart_tx (N15).
// Unlike a static 0x55, a counting payload is irrefutable proof the fabric is
// alive: the host sees an incrementing sequence (0x00, 0x01, ...) rather than a
// fixed value a stuck FSM could also produce. cnt[26:19] advances every
// 2^19 mclk ~= 10.5 ms (at 50 MHz), so each value repeats ~120x at 115200 baud.
//
// Clock = STARTUPE2 CFGMCLK (same isolated path as led_onehot) so success
// isolates the UART path, not the clock. CFGMCLK is part-dependent (~32-98 MHz)
// -> actual baud scales (~74k-226k); the host sweeps baud and reads BOTH:
//   /dev/cu.usbserial-120           (on-board CP2102N UART)
//   /dev/cu.usbserial-210512180081  (AL321 FT2232H channel B)
// A monotonic byte stream on a port => that port is the working host-RX path
// AND the fabric/counter is provably running.
//
// PARALLEL VISUAL: LED1..LED4 walk (proven onehot logic) so a human observer
// confirms the bitstream loaded/ran independently of the UART path.
//
// NOTE on build: this design must build WITHOUT --force. nextpnr-xilinx on
// xc7a200t can leave a global constant net ($PACKER_VCC_NET) unrouted; --force
// would emit a functionally-broken bitstream. CI fails the build if any
// "Failed to find a route" appears. Success proves only this design's infra.
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
    // Free-running counter + LED walking (proven from led_onehot)
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
    // UART TX: stream cnt[26:19] (monotonic) at nominal 115200 (50 MHz CFGMCLK)
    // Frame out of shreg[0] (LSB first): start(0), d0..d7, stop(1).
    // Each byte = live cnt[26:19], re-sampled at the byte boundary => monotonic.
    // -------------------------------------------------------------------------
    localparam [8:0] BAUD_DIV = 9'd434;          // 50 MHz / 115200 ~= 434

    reg [8:0] baud_cnt;
    reg [3:0] bit_idx;                            // 0..9 (start + 8 data + stop)
    reg [9:0] shreg;

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            baud_cnt <= 9'd0;
            bit_idx  <= 4'd0;
            shreg    <= {1'b1, 8'h00, 1'b0};      // cnt=0 at reset -> data 0x00
            uart_tx  <= 1'b1;                     // idle line high
        end else begin
            uart_tx <= shreg[0];                  // emit current LSB
            if (baud_cnt == BAUD_DIV - 9'd1) begin
                baud_cnt <= 9'd0;
                if (bit_idx == 4'd9) begin
                    bit_idx <= 4'd0;
                    shreg   <= {1'b1, cnt[26:19], 1'b0}; // next byte = live counter slice
                end else begin
                    bit_idx <= bit_idx + 4'd1;
                    shreg   <= {1'b1, shreg[9:1]};       // shift right, feed stop/idle
                end
            end else begin
                baud_cnt <= baud_cnt + 9'd1;
            end
        end
    end

endmodule

`default_nettype wire
