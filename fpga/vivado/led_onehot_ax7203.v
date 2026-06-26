`default_nettype wire

// =============================================================================
// led_onehot_ax7203 — silkscreen/pin ANCHOR + clock-isolation diagnostic
// =============================================================================
// 5-phase "walking LED" cycle (~2.7 s each at CFGMCLK ~50 MHz):
//   phase 0 -> led[0] only   (pin B13)
//   phase 1 -> led[1] only   (pin C13)
//   phase 2 -> led[2] only   (pin D14)
//   phase 3 -> led[3] only   (pin D15)
//   phase 4 -> ALL OFF       (clean dark frame between LEDs)
//
// The FIRST silkscreen LED (LED1..LED4) to light = led[0] = B13. Watching one
// full cycle fixes the entire silkscreen <-> Verilog-bit <-> pin table in a
// single pass, resolving the LiteX-order vs board-textolite ambiguity.
//
// CLOCK: STARTUPE2 CFGMCLK (internal configuration master clock, ~tens of MHz,
// free-running after configuration). This is INTENTIONALLY independent of the
// 200 MHz differential (IBUFDS->BUFG) path used by gf16/blinky — that path is
// NOT independently verified (its only "blinking" evidence may itself be
// camera-based and Nyquist-limited). If this diagnostic blinks, the fabric +
// LED pins + config flow are proven good regardless of the 200 MHz path.
//
// CAMERA-SAFE RATE: phase advances on the rising edge of cnt[26] =>
// 2^27 / ~50 MHz ~= 2.7 s => 0.37 Hz switching. Even at a 3 fps capture
// (Nyquist 1.5 Hz) the margin is ~4x, so the cycle resolves cleanly.
//
// NOTE: onehot success proves only THIS design's infrastructure. It does NOT
// prove the gf16 bitstream loads or that its 200 MHz heartbeat runs.
// =============================================================================

`timescale 1ns / 1ps

module led_onehot_ax7203 (
    input  wire rst_n,       // CPU_RESET_N (T6), active-low; restarts the cycle
    output reg  [3:0] led
);

    // -------------------------------------------------------------------------
    // Internal config master clock via STARTUPE2 (no external clock needed)
    // -------------------------------------------------------------------------
    wire mclk;               // CFGMCLK: free-running after configuration
    wire eos;                // End-Of-Startup
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) u_startup (
        .CFGCLK(),           // unused (user config clock output)
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

    // Hold reset until startup completes and while the reset button is held.
    wire rst = ~rst_n | ~eos;

    // -------------------------------------------------------------------------
    // Free-running counter + phase stepped on rising edge of cnt[26]
    // (no wide comparator -> minimal timing risk)
    // -------------------------------------------------------------------------
    reg [26:0] cnt;          // MSB = cnt[26], the only bit we read
    reg [2:0]  phase;        // 0..4 (wraps 4 -> 0)
    reg        cnt26_d;
    wire       step = cnt[26] & ~cnt26_d;   // rising edge of cnt[26]

    always @(posedge mclk or posedge rst) begin
        if (rst) begin
            cnt     <= 32'd0;
            phase   <= 3'd0;
            cnt26_d <= 1'b0;
        end else begin
            cnt     <= cnt + 27'd1;
            cnt26_d <= cnt[26];
            if (step)
                phase <= (phase == 3'd4) ? 3'd0 : (phase + 3'd1);
        end
    end

    // -------------------------------------------------------------------------
    // One-hot LED mapping with explicit OFF phase (3-bit compare only)
    // -------------------------------------------------------------------------
    always @(*) begin
        case (phase)
            3'd0: led = 4'b0001; // LED at pin B13 (Verilog led[0])
            3'd1: led = 4'b0010; // LED at pin C13 (Verilog led[1])
            3'd2: led = 4'b0100; // LED at pin D14 (Verilog led[2])
            3'd3: led = 4'b1000; // LED at pin D15 (Verilog led[3])
            default: led = 4'b0000; // phase 4 -> ALL OFF
        endcase
    end

endmodule

`default_nettype wire
