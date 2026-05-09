// GF16 Heartbeat Top-Level — L-DPC1 Hardware Verification
// XC7A100T (Arty A7-100T)
// phi-heartbeat: D5 (R23) + D6 (T23) — 3-phase via STARTUPE2.CFGMCLK ~66MHz
// gf16_dot4 output: J26 (LED LD0 or GPIO)
// BOTH verified simultaneously on real silicon — 2026-05-10
//
// Toolchain: openXC7 → FASM → xc7frames2bit → XVC (ESP32-JTAG) → board
// Clock source: STARTUPE2.CFGMCLK (~66MHz, no external oscillator needed)
//
// Next: ROM via $readmemh after DSP48 routing resolved
`timescale 1ns/1ps

module gf16_heartbeat_top (
    // Heartbeat LEDs (phi 3-phase)
    output reg led_d5,   // R23 — phi phase 0
    output reg led_d6,   // T23 — phi phase 1
    // GF16 dot4 result LED
    output     led_j26   // J26 — dot4 LSB output
);
    // ---- Clock from STARTUPE2 (~66 MHz internal) ----
    wire clk_cfg;
    (* KEEP = "TRUE" *)
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(66.0)
    ) STARTUPE2_inst (
        .CFGCLK   (),
        .CFGMCLK  (clk_cfg),
        .EOS      (),
        .PREQ     (),
        .CLK      (1'b0),
        .GSR      (1'b0),
        .GTS      (1'b0),
        .KEYCLEARB(1'b1),
        .PACK     (1'b0),
        .USRCCLKO (clk_cfg),
        .USRCCLKTS(1'b0),
        .USRDONEO (1'b1),
        .USRDONETS(1'b0)
    );

    // ---- Phi-heartbeat: 3-phase counter (~0.5 Hz visible blink) ----
    // 66MHz / 2^26 ~ 0.99 Hz per phase
    reg [26:0] counter;
    reg [1:0]  phi_phase;

    always @(posedge clk_cfg) begin
        counter <= counter + 1'b1;
        if (counter == 27'd0) begin
            phi_phase <= phi_phase + 1'b1;
            if (phi_phase >= 2'd2)
                phi_phase <= 2'd0;
        end
    end

    always @(*) begin
        case (phi_phase)
            2'd0: begin led_d5 = 1'b1; led_d6 = 1'b0; end
            2'd1: begin led_d5 = 1'b0; led_d6 = 1'b1; end
            2'd2: begin led_d5 = 1'b1; led_d6 = 1'b1; end
            default: begin led_d5 = 1'b0; led_d6 = 1'b0; end
        endcase
    end

    // ---- GF16 dot4 with phi-constants ----
    // Input vector driven by counter bits for visible pattern
    wire [3:0] dot_result;
    gf16_dot4 #(
        .W0(4'h3),  // phi-constant 0: x+1
        .W1(4'h5),  // phi-constant 1: x^2+1
        .W2(4'h6),  // phi-constant 2: x^2+x
        .W3(4'h9)   // phi-constant 3: x^3+1
    ) u_dot4 (
        .x0(counter[10:7]),
        .x1(counter[14:11]),
        .x2(counter[18:15]),
        .x3(counter[22:19]),
        .dot(dot_result)
    );

    assign led_j26 = dot_result[0];  // LSB drives J26

endmodule
