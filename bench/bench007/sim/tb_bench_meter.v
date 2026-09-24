`timescale 1ps/1ps
// Testbench for bench_meter: decodes the UART stream and checks every line.
//   * format and checksum
//   * seq increments by one
//   * C within +-1 of GATE * T_ref / T_dut      (window 0 is partial, skipped)
//   * P == floor(C/STEPDIV) or ceil(C/STEPDIV)
// Compile-time knobs: -DDUT_HALF_PS=<ps>  -DSTEPDIV=<n>  -DNWIN=<n>
`ifndef DUT_HALF_PS
`define DUT_HALF_PS 7250
`endif
`ifndef STEPDIV
`define STEPDIV 16
`endif
`ifndef NWIN
`define NWIN 8
`endif
module tb;
    localparam integer GATE = 4000, BAUD = 4, REF_HALF = 2500;
    reg ref_clk = 0, dut_clk = 0;
    always #(REF_HALF)        ref_clk = ~ref_clk;
    always #(`DUT_HALF_PS)    dut_clk = ~dut_clk;

    reg [31:0] div = 0;
    always @(posedge dut_clk) div <= (div == `STEPDIV - 1) ? 0 : div + 1;
    wire step = (div == `STEPDIV - 1);

    wire tx;
    bench_meter #(.GATE(GATE), .BAUD_DIV(BAUD)) dut (
        .ref_clk(ref_clk), .dut_clk(dut_clk), .dut_step(step), .uart_tx(tx));

    // ---- UART receiver, sampling on ref_clk
    integer k, nlines = 0, fails = 0, last_seq = -1;
    reg [7:0] line [0:63];
    integer   len = 0;
    reg [7:0] b;
    real expect_c;

    function [3:0] hv(input [7:0] c);
        hv = (c >= "A") ? (c - 8'd55) : (c - 8'd48);
    endfunction
    function [31:0] hex8(input integer at);
        integer j; begin hex8 = 0; for (j = 0; j < 8; j = j + 1) hex8 = (hex8 << 4) | hv(line[at + j]); end
    endfunction
    function [7:0] s4(input [31:0] w); s4 = w[31:24] ^ w[23:16] ^ w[15:8] ^ w[7:0]; endfunction

    task check_line;
        reg [31:0] s, c, p; reg [7:0] kk, kc; integer lo, hi;
        begin
            if (len != 34 || line[0] != "B" || line[1] != "7" || line[2] != "," ||
                line[11] != "," || line[20] != "," || line[29] != "," ||
                line[32] != 8'h0D || line[33] != 8'h0A) begin
                $display("FAIL format len=%0d", len); fails = fails + 1;
            end else begin
                s = hex8(3); c = hex8(12); p = hex8(21);
                kk = {hv(line[30]), hv(line[31])};
                kc = s4(s) ^ s4(c) ^ s4(p);
                if (kk !== kc) begin $display("FAIL checksum %h vs %h", kk, kc); fails = fails + 1; end
                if (last_seq >= 0 && s != last_seq + 1) begin
                    $display("FAIL seq %0d after %0d", s, last_seq); fails = fails + 1;
                end
                last_seq = s;
                lo = c / `STEPDIV; hi = (c + `STEPDIV - 1) / `STEPDIV;
                if (s >= 1) begin
                    if ((c > expect_c + 1.0) || (c < expect_c - 1.0)) begin
                        $display("FAIL seq=%0d C=%0d expected %0.3f +-1", s, c, expect_c); fails = fails + 1;
                    end
                    if (p != lo && p != hi) begin
                        $display("FAIL seq=%0d P=%0d not in {%0d,%0d}", s, p, lo, hi); fails = fails + 1;
                    end
                end
                $display("line seq=%0d C=%0d P=%0d chk=%h  (expected C %0.3f)", s, c, p, kk, expect_c);
            end
            nlines = nlines + 1; len = 0;
        end
    endtask

    initial begin
        expect_c = (GATE * 2.0 * REF_HALF) / (2.0 * `DUT_HALF_PS);
        forever begin
            @(negedge tx);
            repeat (BAUD + BAUD / 2) @(posedge ref_clk);         // middle of bit 0
            for (k = 0; k < 8; k = k + 1) begin
                b[k] = tx;
                repeat (BAUD) @(posedge ref_clk);
            end
            if (tx !== 1'b1) begin $display("FAIL framing (stop bit)"); fails = fails + 1; end
            line[len] = b; len = len + 1;
            if (b == 8'h0A) check_line;
            if (len > 60) begin $display("FAIL runaway line"); fails = fails + 1; len = 0; end
        end
    end

    initial begin
        #(2.0 * REF_HALF * GATE * (`NWIN + 1) + 2.0 * REF_HALF * 34 * 10 * BAUD * 2);
        $display("lines=%0d fails=%0d", nlines, fails);
        if (nlines < `NWIN) begin $display("FAIL too few lines"); $fatal(1); end
        if (fails != 0) $fatal(1);
        $display("PASS");
        $finish;
    end
endmodule
