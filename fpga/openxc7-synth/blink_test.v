//! Blink Test Module — Simple LED flasher (No UART needed)
// ============================================================================
// Target: QMTech XC7A100T-FGG676 board via Xilinx DLC10 (JTAG mode)

// JTAG configuration (from 2026-04-01 Mac ARM discovery):
// - PID: 0x0008 (JTAG mode) confirmed ✅
// - FPGA IDCODE: 0x13631093 (XC7A100T) ✅
// - Tool: xc3sprog (not openFPGALoader) ✅

// Known pin mapping issues:
// - uart_bridge_fixed.v uses L20/K20 (Arty A7 pins) instead of J2/J2 (QMTech FT232RL pins)
// - This causes DSLogic to show no UART data on CH0/CH1

// Corrected pin mapping (QMTech FT232RL):
// - TXD (E21, white) on FT232RL → J2 pin 6 → FPGA uart_tx
// - RXD (F21, green) on FT232RL → J2 pin 5 → FPGA uart_rx

module blink_test (
    // 50MHz clock from M22 oscillator (V1/V2 on QMTech board)
    input  wire clk_50MHz,

    // Simple 27-bit counter for LED blinking
    // Bit period: 2^25 / 50MHz ≈ 1.34 seconds
    reg [26:0] counter = 26'd0;

    always @(posedge clk_50MHz) begin
        // Increment counter every clock cycle
        if (counter[26] >= 27'd1) begin
            counter <= 27'd0;
        end else begin
            counter <= counter + 1'b1;
        end

    // LED output - active-low to flash on/off
    assign led = counter[25];  // bit 25 = LED ON, bit 24 = LED OFF

endmodule
