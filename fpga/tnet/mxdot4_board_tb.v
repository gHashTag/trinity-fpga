`timescale 1ns/1ps
`default_nettype none
//=============================================================================
// mxdot4_board_tb -- mxdot4_board_ax7203 from the UART pins, with the STARTUPE2 mock.
//
//   python3 conformance/mxdot4_board_vectors.py --write /tmp/mxdot4_vectors.hex
//   iverilog -g2012 -o /tmp/mxdot4_board_tb fpga/tnet/mxdot4_board_params.v \
//       fpga/vivado/mxdot4_board_ax7203.v fpga/openxc7-synth/STARTUPE2_mock.v \
//       fpga/tnet/mxdot4_core.v fpga/tnet/mxdot4_board_tb.v
//   vvp /tmp/mxdot4_board_tb +vectors=/tmp/mxdot4_vectors.hex [+skew_ppm=-43000] [+n=40]
//
// The mock has no `timescale of its own: list it after a file that has one, or its
// #7 counts in seconds and the board never leaves reset in simulated time.
// The first 32 lines of the vector file are the pinned blocks of both ops (NaN
// scales, the hole code, full-scale sums, exponent ends), so n=40 covers them.
//
// Frames go back to back with no idle, as the adapter sends them when the window
// is full; skew_ppm makes the host's bit shorter (negative) or longer. Checked:
// every response is RESP_OK, echoes SEQ and carries the golden word; an unknown
// opcode gets RESP_BADOP SEQ 0 0 0; SYNC0 SYNC0 SYNC1 and a stray SYNC0 resync;
// the overrun LED stays off; the request LED toggles once per frame.
//=============================================================================
module mxdot4_board_tb;
    localparam integer W = `MXDOT4_WORD_BITS;
    localparam integer LB = 8 + 8 + 8 + 128 + 128 + 24;
    localparam integer CLK_NS = 14;                         // STARTUPE2_mock: #7 half period
    localparam real    DEV_BIT = `MXDOT4_BAUD_DIV * CLK_NS;  // board's bit, ns

    reg rst_n = 1'b0;
    reg rx = 1'b1;
    wire tx;
    wire [3:0] led;
    mxdot4_board_ax7203 dut (.rst_n(rst_n), .uart_rx(rx), .uart_tx(tx), .led(led));

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
            want[nwant+3] = y[15:8]; want[nwant+4] = y[23:16];
            nwant = nwant + 5;
        end
    endtask

    // {op, sa, sb, A, B}: A and B go out as 16 bytes each, byte j = A[8j+7:8j].
    task send_req(input [7:0] seq, input [LB-W-1:0] req);
        integer j;
        begin
            send_byte(`MXDOT4_SYNC0); send_byte(`MXDOT4_SYNC1);
            send_byte(req[LB-W-1 -: 8]); send_byte(seq);
            send_byte(req[LB-W-9 -: 8]); send_byte(req[LB-W-17 -: 8]);
            for (j = 0; j < 16; j = j + 1) send_byte(req[128 + 8*j +: 8]);
            for (j = 0; j < 16; j = j + 1) send_byte(req[8*j +: 8]);
        end
    endtask

    reg [1023:0] path;
    integer fd, r, i, nsent = 0, bad = 0, toggles = 0;
    reg [LB-1:0] line;
    always @(led[1]) if (rst_n) toggles = toggles + 1;

    initial begin
        if (!$value$plusargs("vectors=%s", path)) begin $display("need +vectors=FILE"); $finish; end
        if (!$value$plusargs("skew_ppm=%d", skew_ppm)) skew_ppm = 0;
        if (!$value$plusargs("n=%d", nreq)) nreq = 40;
        host_bit = DEV_BIT * (1.0 + skew_ppm / 1.0e6);
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %0s", path); $finish; end

        #200 rst_n = 1'b1;
        #(DEV_BIT * 4);

        // A stray SYNC0 and a half header before the first frame.
        send_byte(8'h13); send_byte(`MXDOT4_SYNC0); send_byte(8'h00);
        send_byte(`MXDOT4_SYNC0);
        for (i = 0; i < nreq; i = i + 1) begin
            r = $fscanf(fd, "%h\n", line);
            if (r != 1) begin $display("vector file ended at %0d", i); $finish; end
            if (i == nreq / 2) begin
                // SYNC0 SYNC0 SYNC1 resync, then an unknown opcode.
                send_byte(`MXDOT4_SYNC0);
                send_req(i[7:0], {8'h07, line[LB-9:W]});
                expect5(`MXDOT4_RESP_BADOP, i[7:0], {W{1'b0}});
                nsent = nsent + 1;
            end
            send_req((i + 1) & 8'hFF, line[LB-1:W]);
            expect5(`MXDOT4_RESP_OK, (i + 1) & 8'hFF, line[W-1:0]);
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
        $display("MXDOT4 UART SIM skew %0d ppm: %0d frames, %0d/%0d response bytes right, overrun %b, request toggles %0d",
                 skew_ppm, nsent, nwant - bad - (nwant > ngot ? nwant - ngot : 0), nwant, led[2], toggles);
        if (ngot == nwant && bad == 0 && led[2] == 1'b0 && toggles == nsent && led[3] == 1'b1)
            $display("MXDOT4 UART SIM PASS");
        else
            $display("MXDOT4 UART SIM FAIL");
        $finish;
    end
endmodule
`default_nettype wire
