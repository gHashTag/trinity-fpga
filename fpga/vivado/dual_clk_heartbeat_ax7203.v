`default_nettype wire

// =============================================================================
// dual_clk_heartbeat_ax7203 — ELECTRICAL 200 MHz vs CFGMCLK discriminator
// =============================================================================
// One byte streamed per UART frame on uart_tx (N15):
//   bits [7:4] = cnt_c[26:23]   — counter on CFGMCLK (reference, KNOWN alive)
//   bits [3:0] = cnt_200[26:23] — counter on 200 MHz IBUFDS->BUFG (UNDER TEST),
//                                 2-FF synchronized into the CFGMCLK domain
// UART TX itself runs on CFGMCLK, so the stream works even if 200 MHz is dead.
//
// Reading the stream on /dev/cu.usbserial-120 (~160000 baud) gives an electrical
// verdict (NOT a camera reading):
//   upper nibble advances, lower nibble STUCK  -> 200 MHz path DEAD
//   both nibbles advance (lower faster)         -> 200 MHz ALIVE
//   lower nibble advances erratically           -> 200 MHz MARGINAL
//
// 200 MHz path is RAW IBUFDS->BUFG (NO PLL/MMCM) — identical to gf16/loopback/
// blinky, so this tests the exact path those designs use. CFGMCLK nibble is the
// control: if it does NOT advance, the test itself failed (CFGMCLK/UART), not
// the 200 MHz path.
// =============================================================================

`timescale 1ns / 1ps

module dual_clk_heartbeat_ax7203 (
    input  wire clk200_p,
    input  wire clk200_n,
    input  wire rst_n,
    output reg  uart_tx
);

    // -------------------------------------------------------------------------
    // CFGMCLK reference (STARTUPE2) — clocks the UART + the reference counter
    // -------------------------------------------------------------------------
    wire mclk_c;
    wire eos;
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) u_startup (
        .CFGCLK(),
        .CFGMCLK(mclk_c),
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

    // -------------------------------------------------------------------------
    // 200 MHz differential clock (RAW IBUFDS->BUFG, NO PLL — same as gf16)
    // -------------------------------------------------------------------------
    wire clk200_raw;
    IBUFDS clk_ibufds (
        .I  (clk200_p),
        .IB (clk200_n),
        .O  (clk200_raw)
    );
    wire mclk_200;
    BUFG clk_bufg200 (
        .I (clk200_raw),
        .O (mclk_200)
    );

    wire rst = ~rst_n | ~eos;

    // -------------------------------------------------------------------------
    // Reference counter on CFGMCLK
    // -------------------------------------------------------------------------
    reg [26:0] cnt_c;
    always @(posedge mclk_c or posedge rst) begin
        if (rst) cnt_c <= 27'd0;
        else     cnt_c <= cnt_c + 27'd1;
    end

    // -------------------------------------------------------------------------
    // Counter under test on 200 MHz (if the clock is dead, this never advances)
    // -------------------------------------------------------------------------
    reg [26:0] cnt_200;
    always @(posedge mclk_200 or posedge rst) begin
        if (rst) cnt_200 <= 27'd0;
        else     cnt_200 <= cnt_200 + 27'd1;
    end

    // -------------------------------------------------------------------------
    // CDC: 2-FF synchronizer per bit for the 200 MHz nibble -> CFGMCLK domain.
    // The raw 4-bit binary slice has multi-bit transitions (e.g. 0111->1000),
    // so per-bit 2-FF sync would skew and produce transient garbage -> would
    // masquerade as "marginal". FIX: Gray-code the slice first, so only ONE bit
    // changes per increment -> per-bit 2-FF is safe (no multibit skew). The host
    // decodes the lower nibble gray->binary to read the advancing count.
    // -------------------------------------------------------------------------
    wire [3:0] cnt_200_bin  = cnt_200[26:23];
    wire [3:0] cnt_200_gray = cnt_200_bin ^ (cnt_200_bin >> 1);  // 1-bit/trans
    reg [3:0] sync_a, sync_b;
    always @(posedge mclk_c or posedge rst) begin
        if (rst) begin
            sync_a <= 4'd0;
            sync_b <= 4'd0;
        end else begin
            sync_a <= cnt_200_gray;
            sync_b <= sync_a;
        end
    end

    // payload = {CFGMCLK nibble (binary, same domain — no CDC),
    //            200 MHz nibble (GRAY-coded, 2-FF synced)}. Host decodes lower.
    wire [7:0] payload = {cnt_c[26:23], sync_b};

    // -------------------------------------------------------------------------
    // UART TX on CFGMCLK: stream payload, BAUD_DIV for ~70 MHz CFGMCLK (~160k)
    // -------------------------------------------------------------------------
    localparam [8:0] BAUD_DIV = 9'd434;          // 70 MHz / 434 ~= 161290 baud
    reg [8:0] baud_cnt;
    reg [3:0] bit_idx;                            // 0..9 (start + 8 data + stop)
    reg [9:0] shreg;

    always @(posedge mclk_c or posedge rst) begin
        if (rst) begin
            baud_cnt <= 9'd0;
            bit_idx  <= 4'd0;
            shreg    <= {1'b1, 8'h00, 1'b0};
            uart_tx  <= 1'b1;                     // idle high
        end else begin
            uart_tx <= shreg[0];                  // emit LSB
            if (baud_cnt == BAUD_DIV - 9'd1) begin
                baud_cnt <= 9'd0;
                if (bit_idx == 4'd9) begin
                    bit_idx <= 4'd0;
                    shreg   <= {1'b1, payload, 1'b0};   // next byte = live payload
                end else begin
                    bit_idx <= bit_idx + 4'd1;
                    shreg   <= {1'b1, shreg[9:1]};      // shift right, feed stop
                end
            end else begin
                baud_cnt <= baud_cnt + 9'd1;
            end
        end
    end

endmodule

`default_nettype wire
