`timescale 1ns / 1ps
//=============================================================================
// tern_tc_layer_rtl_tb — the tern_tc harness's byte stream through the node RTL.
//
// conformance/tern_tc_layer_ax7203.py --emit-requests writes every request
// frame (optionally led by a setkey frame) as one hex byte per line. This
// bench plays them into fpga/portable/trinet_node_core.v bit by bit over its
// UART, back to back as a pipelined host would, decodes uart_tx, and writes
// every response byte out the same way. The harness then verifies that stream
// with --responses: tags, nonces, node id, and every row against the int8
// weights. No board, but the same frame parser, dot product, key latch and
// SipHash engine the bitstream is built from.
//
// The core comes up UNKEYED (RECEIPT_KEY = 0), as the board does, so a run
// without a setkey frame must come back all status 0x04 and fail the harness.
//
//   iverilog -g2012 -o tb formal/tern_tc_layer_rtl_tb.v \
//       fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v
//   vvp tb +req=req.hex +resp=resp.hex            (+expect=N total answer bytes;
//                                                  default frames*19, today's one-answer-per-frame)
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module tern_tc_layer_rtl_tb;

`ifndef TB_BAUD_DIV
  `define TB_BAUD_DIV 8
`endif
`ifndef TB_MAX_BYTES
  `define TB_MAX_BYTES 4194304
`endif
    localparam integer BAUD_DIV  = `TB_BAUD_DIV;
    localparam integer MAX_BYTES = `TB_MAX_BYTES;
    localparam [31:0]  NODE_ID   = 32'h5452494E;   // FALLBACK_NODE_ID: the board's DNA reads zero

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg  rst = 1'b1;
    reg  uart_rx = 1'b1;
    wire uart_tx, frame_seen, result_nonzero;

    trinet_node_core #(.BAUD_DIV_P(BAUD_DIV), .RECEIPT_KEY(128'h0)) dut (
        .clk(clk), .rst(rst), .node_id(NODE_ID),
        .uart_rx(uart_rx), .uart_tx(uart_tx),
        .frame_seen(frame_seen), .result_nonzero(result_nonzero));

    reg [7:0] req [0:MAX_BYTES-1];
    reg [8*256-1:0] req_file, resp_file;
    integer n_req, n_resp, fd, i;
    reg sender_done = 1'b0;

    task send_byte(input [7:0] b);
        integer k;
        begin
            uart_rx = 1'b0; repeat (BAUD_DIV) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                uart_rx = b[k]; repeat (BAUD_DIV) @(posedge clk);
            end
            uart_rx = 1'b1; repeat (BAUD_DIV) @(posedge clk);
        end
    endtask

    // Receiver: centre-sampling UART decoder on uart_tx.
    reg [7:0] rx_b;
    integer rk;
    initial begin
        n_resp = 0;
        @(negedge rst);
        forever begin
            @(negedge uart_tx);
            repeat (BAUD_DIV / 2) @(posedge clk);
            if (uart_tx == 1'b0) begin
                for (rk = 0; rk < 8; rk = rk + 1) begin
                    repeat (BAUD_DIV) @(posedge clk);
                    rx_b[rk] = uart_tx;
                end
                repeat (BAUD_DIV) @(posedge clk);          // stop bit
                $fwrite(fd, "%02x\n", rx_b);
                n_resp = n_resp + 1;
            end
        end
    end

    integer frames, guard, expect_total;
    initial begin
        if (!$value$plusargs("req=%s", req_file))   req_file  = "req.hex";
        if (!$value$plusargs("resp=%s", resp_file)) resp_file = "resp.hex";
        for (i = 0; i < MAX_BYTES; i = i + 1) req[i] = 8'hxx;
        $readmemh(req_file, req);
        n_req = 0;
        while (n_req < MAX_BYTES && req[n_req] !== 8'hxx) n_req = n_req + 1;
        if (n_req == 0 || n_req % 24 != 0) begin
            $display("FAIL: %0d request bytes is not a whole number of 24-byte frames", n_req);
            $finish;
        end
        frames = n_req / 24;
        // Total response bytes the stream owes. Default: one 19-byte answer per
        // frame (today's protocol) — byte-identical to the hard-coded version,
        // so existing invocations are unchanged. +expect=N overrides for
        // mixed-length streams: the batch ops answer 19 B per SETX and 24 B
        // per DOT6, and the caller knows the split.
        if (!$value$plusargs("expect=%d", expect_total)) expect_total = frames * 19;
        fd = $fopen(resp_file, "w");
        $display("tern_tc_layer_rtl_tb: %0d frames, BAUD_DIV=%0d, expect %0d response bytes",
                 frames, BAUD_DIV, expect_total);

        repeat (20) @(posedge clk);
        rst = 1'b0;
        repeat (20 * BAUD_DIV) @(posedge clk);

        for (i = 0; i < n_req; i = i + 1) begin
            send_byte(req[i]);
            if (i % (24 * 16384) == 24 * 16384 - 1)
                $display("  sent %0d / %0d frames", (i + 1) / 24, frames);
        end
        sender_done = 1'b1;

        // The last response needs its line time after its frame (<= 24 bytes,
        // well inside the 40-byte-time guard).
        guard = 0;
        while (n_resp < expect_total && guard < 40 * 10 * BAUD_DIV) begin
            @(posedge clk); guard = guard + 1;
        end
        $fclose(fd);
        $display("tern_tc_layer_rtl_tb: %0d response bytes for %0d frames, %0d expected (%0s)",
                 n_resp, frames, expect_total, (n_resp == expect_total) ? "complete" : "INCOMPLETE");
        $finish;
    end

endmodule
