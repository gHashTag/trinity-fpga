`default_nettype none
// bench007_probe_ax7203 -- first BENCH-007 session, no design files needed.
//
// Measures ONE thing on THIS die: the internal configuration clock CFGMCLK,
// which every JTAG-verdict design in gHashTag/t27 runs on (directly, or /32 as
// `slowclk`). The repo records 68.8-70.77 MHz across three dice (T495); this
// run gives the number for the die on the bench, against the 200 MHz crystal.
//
// It also proves the solo flow end to end: CI bitstream -> openFPGALoader ->
// UART capture -> analysis -> report, before the real DUT is on the board.
//
// Self-check built in: dut_step fires once every 1024 DUT cycles, so every
// line must satisfy  P == floor(C/1024) or P == ceil(C/1024)  (window edges
// cut the divider at an arbitrary phase). b7_analyze.py --expect-step-div 1024
// enforces it; a line that fails means the instrument, not the DUT, is wrong.
//
// LEDs: led[0] blinks from the crystal (~0.75 Hz, 100 MHz / 2^27), led[1] from CFGMCLK
// (~0.5 Hz at 69 MHz), led[2] lights while a report line is being sent.
module bench007_probe_ax7203 (
    input  wire       clk200_p,
    input  wire       clk200_n,
    output wire       uart_tx,
    output wire [3:0] led
);
    // The reference domain runs at 100 MHz = crystal / 2. The first build ran
    // it at 200 MHz and nextpnr put its 32-bit counters at 166 MHz: a real
    // timing failure, visible only once the net carried its true constraint.
    // Halving it keeps the crystal's accuracy and gives the counters margin.
    wire clk200_i, clk200;
    IBUFDS ibufds_clk (.I(clk200_p), .IB(clk200_n), .O(clk200_i));
    BUFG   bufg_200   (.I(clk200_i), .O(clk200));
    reg half = 1'b0;
    always @(posedge clk200) half <= ~half;
    wire ref_clk;
    BUFG   bufg_ref   (.I(half), .O(ref_clk));

    wire cfgmclk_raw, dut_clk;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(10.0)) startup (
        .CFGCLK(), .CFGMCLK(cfgmclk_raw), .EOS(), .PREQ(),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0),
        .PACK(1'b0), .USRCCLKO(1'b0), .USRCCLKTS(1'b0),
        .USRDONEO(1'b1), .USRDONETS(1'b1));
    BUFG bufg_dut (.I(cfgmclk_raw), .O(dut_clk));

    reg [9:0] div = 10'd0;
    always @(posedge dut_clk) div <= div + 10'd1;
    wire step = (div == 10'h3FF);

    bench_meter #(.GATE(100_000_000), .BAUD_DIV(868)) meter (    // 1 s; 115200 baud -0.007 %
        .ref_clk(ref_clk), .dut_clk(dut_clk), .dut_step(step), .uart_tx(uart_tx));

    reg [26:0] hb_ref = 27'd0;
    always @(posedge ref_clk) hb_ref <= hb_ref + 27'd1;
    reg [26:0] hb_dut = 27'd0;
    always @(posedge dut_clk) hb_dut <= hb_dut + 27'd1;

    assign led[0] = hb_ref[26];
    assign led[1] = hb_dut[26];
    assign led[2] = ~uart_tx;
    assign led[3] = 1'b0;
endmodule
`default_nettype wire
