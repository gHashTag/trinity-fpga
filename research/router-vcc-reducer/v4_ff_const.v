// v4 — no IDDR at all: an ordinary fabric flop with CE tied high.
// If this fails too, the defect is the constant network, not ILOGIC.
module top (input wire clk, input wire d, output reg q);
    always @(posedge clk) q <= d;
endmodule
