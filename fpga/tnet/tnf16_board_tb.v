`timescale 1ns/1ps
`default_nettype none
//=============================================================================
// tnf16_board_tb -- tnf16_board_ax7203 from the UART pins, with the STARTUPE2 mock.
//
//   iverilog -g2005 -o /tmp/tnf16_board_tb fpga/tnet/tnf16_board_params.v \
//       fpga/vivado/tnf16_board_ax7203.v fpga/openxc7-synth/STARTUPE2_mock.v \
//       fpga/tnet/tnf16_core.v fpga/tnet/tnf16_board_tb.v
//   vvp /tmp/tnf16_board_tb +vectors=/tmp/tnf16_vectors.hex [+skew_ppm=-40000] [+n=400]
//
// The mock has no `timescale of its own: list it after a file that has one, or its
// #7 counts in seconds and the board never leaves reset in simulated time.
// CFGMCLK 65.6..68.7 MHz puts the adapter's 1142857-baud bit at -43333..+1875 ppm
// against the board's; this bench passes at -43000 and +45000 and fails at -50000.
//
// The host side sends frames back to back with no idle, as the adapter does when
// the window is full; skew_ppm makes its bit shorter (negative) or longer than the
// board's. Checked: every response is RESP_OK, echoes SEQ and carries the reference
// word; bits 19..23 of each operand are junk and must be ignored; an unknown opcode
// gets RESP_BADOP SEQ 0 0 0; SYNC0 SYNC0 SYNC1 and a stray SYNC0 resync; the
// overrun LED stays off; the request LED toggles once per frame.
//=============================================================================
module tnf16_board_tb;
    localparam integer W = `TNF16_WORD_BITS;
    localparam integer CLK_NS = 14;                        // STARTUPE2_mock: #7 half period
    localparam real    DEV_BIT = `TNF16_BAUD_DIV * CLK_NS;  // board's bit, ns

    reg rst_n = 1'b0;
    reg rx = 1'b1;
    wire tx;
    wire [3:0] led;
    tnf16_board_ax7203 dut (.rst_n(rst_n), .uart_rx(rx), .uart_tx(tx), .led(led));

    real host_bit;
    integer skew_ppm, nreq;

    task send_byte(input [7:0] b);
        integer i;
        begin
            rx = 1'b0; #(host_bit);
            for (i = 0; i < 8; i = i + 1) begin rx = b[i]; #(host_bit); end
            rx = 1'b1; #(host_bit);
        end
    endtask

    // Receiver at the board's own rate: find the start bit's edge, sample mid-bit.
    reg [7:0] got [0:65535];
    integer ngot = 0;
    reg [7:0] rb;
    integer k;
    initial begin
        #1;
        forever begin
            @(negedge tx);
            #(DEV_BIT * 1.5);
            for (k = 0; k < 8; k = k + 1) begin rb[k] = tx; #(DEV_BIT); end
            if (tx !== 1'b1) $display("RX framing: stop bit %b at %0t", tx, $time);
            got[ngot] = rb; ngot = ngot + 1;
        end
    end

    // Expected response bytes, in order.
    reg [7:0] want [0:65535];
    integer nwant = 0;
    task expect5(input [7:0] tag, input [7:0] seq, input [W-1:0] y);
        begin
            want[nwant] = tag; want[nwant+1] = seq; want[nwant+2] = y[7:0];
            want[nwant+3] = y[15:8]; want[nwant+4] = {{(24-W){1'b0}}, y[W-1:16]};
            nwant = nwant + 5;
        end
    endtask

    task send_req(input [7:0] op, input [7:0] seq, input [23:0] a, input [23:0] b);
        begin
            send_byte(`TNF16_SYNC0); send_byte(`TNF16_SYNC1);
            send_byte(op); send_byte(seq);
            send_byte(a[7:0]); send_byte(a[15:8]); send_byte(a[23:16]);
            send_byte(b[7:0]); send_byte(b[15:8]); send_byte(b[23:16]);
        end
    endtask

    reg [1023:0] path;
    integer fd, r, i, nsent = 0, bad = 0, toggles = 0;
    reg [7:0]   f_op;
    reg [W-1:0] f_a, f_b, f_want;
    reg [4:0]   junk_a, junk_b;
    always @(led[1]) if (rst_n) toggles = toggles + 1;

    initial begin
        if (!$value$plusargs("vectors=%s", path)) begin $display("need +vectors=FILE"); $finish; end
        if (!$value$plusargs("skew_ppm=%d", skew_ppm)) skew_ppm = 0;
        if (!$value$plusargs("n=%d", nreq)) nreq = 400;
        host_bit = DEV_BIT * (1.0 + skew_ppm / 1.0e6);
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %0s", path); $finish; end

        #200 rst_n = 1'b1;
        #(DEV_BIT * 4);

        // A stray SYNC0 and a half header before the first frame.
        send_byte(8'h13); send_byte(`TNF16_SYNC0); send_byte(8'h00);
        send_byte(`TNF16_SYNC0);
        for (i = 0; i < nreq; i = i + 1) begin
            r = $fscanf(fd, "%h %h %h %h\n", f_op, f_a, f_b, f_want);
            if (r != 4) begin $display("vector file ended at %0d", i); $finish; end
            junk_a = i[4:0] ^ 5'h15; junk_b = ~i[4:0];
            if (i == nreq / 2) begin
                // SYNC0 SYNC0 SYNC1 resync, then an unknown opcode.
                send_byte(`TNF16_SYNC0);
                send_req(8'h07, i[7:0], {junk_a, f_a}, {junk_b, f_b});
                expect5(`TNF16_RESP_BADOP, i[7:0], {W{1'b0}});
                nsent = nsent + 1;
            end
            send_req(f_op, (i + 1) & 8'hFF, {junk_a, f_a}, {junk_b, f_b});
            expect5(`TNF16_RESP_OK, (i + 1) & 8'hFF, f_want);
            nsent = nsent + 1;
        end
        $fclose(fd);
        #(DEV_BIT * 200);

        if (ngot != nwant) $display("BYTES got %0d, want %0d", ngot, nwant);
        for (i = 0; i < nwant && i < ngot; i = i + 1)
            if (got[i] !== want[i]) begin
                bad = bad + 1;
                if (bad <= 10) $display("BYTE %0d (response %0d, byte %0d): got %02h want %02h",
                                        i, i / 5, i % 5, got[i], want[i]);
            end
        $display("TNF16 UART SIM skew %0d ppm: %0d frames, %0d/%0d response bytes right, overrun %b, request toggles %0d",
                 skew_ppm, nsent, nwant - bad - (nwant > ngot ? nwant - ngot : 0), nwant, led[2], toggles);
        if (ngot == nwant && bad == 0 && led[2] == 1'b0 && toggles == nsent && led[3] == 1'b1)
            $display("TNF16 UART SIM PASS");
        else
            $display("TNF16 UART SIM FAIL");
        $finish;
    end
endmodule
`default_nettype wire
