// lns8 wrapper FSM sim: drives the decode 6-byte frame, reads tx_buf. Verifies
// lns8's UNIQUE tuple packing {sign, 15'b0, magnitude} (the only decode wrapper
// with a non-fp32 result construction) end-to-end. Expected from the host golden
// _lns8 = (sign<<31)|magnitude. Closes the lns8-packing residual.
`timescale 1ns / 1ps
`default_nettype none
module lns8_wrapper_sim_tb;
    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;
    corona_decode_lns8_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    localparam realtime BIT = 6076.0;
    task send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx = 1'b0; #BIT;
            for (i = 0; i < 8; i = i + 1) begin uart_rx = b[i]; #BIT; end
            uart_rx = 1'b1; #BIT;
        end
    endtask

    integer errs = 0, k;
    reg [7:0] vcode [0:4]; reg [31:0] vex [0:3]; reg [31:0] expv;

    initial #50000000 $finish;
    initial begin
        // (code, expected result) from host golden _lns8
        vcode[0]=8'h00; vcode[1]=8'h10; vcode[2]=8'h7F; vcode[3]=8'h80; vcode[4]=8'hFF;
        #500; rst_n = 1'b1; #2000;
        for (k = 0; k < 5; k = k + 1) begin
            send_byte(8'hAA); send_byte(8'h55); send_byte(8'd10);   // fmt=10 (lns8)
            send_byte(vcode[k]); send_byte(8'h00); send_byte(8'h00); // lo, hi, trig
            #(BIT*3);
            // compute expected (sign<<31)|magnitude mirroring _lns8
            case (vcode[k])
              8'h00: expv=32'h00000000; 8'h10: expv=32'h00000200; 8'h7F: expv=32'h0000F500;
              8'h80: expv=32'h80000100; 8'hFF: expv=32'h8000F500; default: expv=32'hDEAD_BEEF;
            endcase
            if (dut.tx_buf0 !== 8'hA5 || dut.tx_buf1 !== expv[7:0] ||
                dut.tx_buf2 !== expv[15:8] || dut.tx_buf3 !== expv[23:16] ||
                dut.tx_buf4 !== expv[31:24]) begin
                errs = errs + 1;
                $display("MISMATCH code=0x%02h tx={%h %h %h %h %h} exp=0x%08h", vcode[k],
                    dut.tx_buf0, dut.tx_buf1, dut.tx_buf2, dut.tx_buf3, dut.tx_buf4, expv);
            end else $display("ok code=0x%02h -> 0x%08h", vcode[k], expv);
        end
        $display("LNS8 WRAPPER FSM SIM: %0d errors (5 cases, tuple packing)", errs);
        $finish;
    end
endmodule
`default_nettype wire
