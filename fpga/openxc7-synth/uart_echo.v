// =============================================================================
// UART Echo Minimal — Direct wire test
// Purpose: Bypass all UART logic - direct RX to TX connection
// Pins: K20 (RX), L20 (TX) per DSLogic measurements
// =============================================================================

module uart_echo (
    input  wire clk,           // 50 MHz (M22)
    input  wire uart_rx,       // From FT232RL TXD (white, J2 pin 5, K20)
    output wire uart_tx,       // To FT232RL RXD (green, J2 pin 6, L20)
    output wire led            // Status LED (T23)
);

    // Direct wire - bypass ALL UART logic
    assign uart_tx = uart_rx;
    assign led = 1'b0;         // LED on (active-low)

endmodule
