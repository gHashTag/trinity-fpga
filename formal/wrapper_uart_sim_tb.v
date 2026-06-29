// Wrapper FSM/UART sim: drives uart_rx with a full request frame at baud timing
// (the bit-level send, which the wrapper's RX FSM receives), then READS the
// loaded tx_buf hierarchically (A5 + result) instead of sampling uart_tx —
// avoiding the immediate-TX recv race. Verifies the RX FSM + frame FSM + decode
// + tx_buf load end-to-end (the cloning-risk path). UART TX shifting itself is
// the HW-proven part. Built for corona_decode_fp4; pattern reusable.
`timescale 1ns / 1ps
`default_nettype none
module wrapper_uart_sim_tb;
    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;
    corona_decode_fp4_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    // bit-time = BAUD_DIV(434) mclk cycles = 434*14ns (STARTUPE2_mock mclk=#7).
    localparam realtime BIT = 6076.0;
    task send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx = 1'b0;            #BIT;            // start bit
            for (i = 0; i < 8; i = i + 1) begin uart_rx = b[i]; #BIT; end  // data LSB-first
            uart_rx = 1'b1;            #BIT;            // stop bit
        end
    endtask

    function [31:0] fp4_golden(input [3:0] c);
        case (c)
            4'h0: fp4_golden=32'h00000000; 4'h1: fp4_golden=32'h3F000000;
            4'h2: fp4_golden=32'h3F800000; 4'h3: fp4_golden=32'h3FC00000;
            4'h4: fp4_golden=32'h40000000; 4'h5: fp4_golden=32'h40400000;
            4'h6: fp4_golden=32'h40800000; 4'h7: fp4_golden=32'h40C00000;
            4'h8: fp4_golden=32'h80000000; 4'h9: fp4_golden=32'hBF000000;
            4'hA: fp4_golden=32'hBF800000; 4'hB: fp4_golden=32'hBFC00000;
            4'hC: fp4_golden=32'hC0000000; 4'hD: fp4_golden=32'hC0400000;
            4'hE: fp4_golden=32'hC0800000; 4'hF: fp4_golden=32'hC0C00000;
        endcase
    endfunction

    integer code, errs = 0;
    reg [31:0] expv;
    initial #50000000 $finish;   // global guard
    initial begin
        #500; rst_n = 1'b1; #2000;
        for (code = 0; code < 16; code = code + 1) begin
            send_byte(8'hAA); send_byte(8'h55); send_byte(8'd6);   // fmt=6 (fp4)
            send_byte(code[7:0]); send_byte(8'h00); send_byte(8'h00);
            #(BIT*3);   // let RX FSM + frame FSM + tx_buf load settle
            expv = fp4_golden(code[3:0]);
            if (dut.tx_buf0 !== 8'hA5 ||
                dut.tx_buf1 !== expv[7:0]  || dut.tx_buf2 !== expv[15:8] ||
                dut.tx_buf3 !== expv[23:16] || dut.tx_buf4 !== expv[31:24]) begin
                errs = errs + 1;
                $display("MISMATCH code=0x%0h tx={%h %h %h %h %h} exp=0x%08h", code,
                    dut.tx_buf0, dut.tx_buf1, dut.tx_buf2, dut.tx_buf3, dut.tx_buf4, expv);
            end else $display("ok code=0x%0h tx_buf=A5 %08h", code, expv);
        end
        $display("WRAPPER FSM SIM: %0d errors (fp4, 16 codes)", errs);
        $finish;
    end
endmodule
`default_nettype wire
