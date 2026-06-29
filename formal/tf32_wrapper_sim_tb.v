// tf32 wrapper FSM sim: drives the DECODE 7-byte frame (AA 55 fmt lo mid hi trig,
// 19-bit code in 3 bytes) at baud timing, reads tx_buf (A5 + 4 fp32 bytes).
// Verifies corona_decode_tf32_ax7203's distinct 7-byte/3-code-byte frame FSM +
// tf32_decode (wiring) + 5-byte TX packing end-to-end — the 4th FSM variant
// (new fire-#5 design, previously compile-checked only). Expected from the
// tf32 decode wiring {sign,exp,mant,13'b0}: 0, 1.0, Inf, NaN.
`timescale 1ns / 1ps
`default_nettype none
module tf32_wrapper_sim_tb;
    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;
    corona_decode_tf32_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

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
    reg [18:0] vcode [0:3]; reg [31:0] vex [0:3];

    initial #50000000 $finish;
    initial begin
        vcode[0]=19'h00000; vex[0]=32'h00000000;  // +0
        vcode[1]=19'h1FC00; vex[1]=32'h3F800000;  // 1.0 (exp=127)
        vcode[2]=19'h3FC00; vex[2]=32'h7F800000;  // +Inf (exp=255)
        vcode[3]=19'h3FC01; vex[3]=32'h7F802000;  // NaN (exp=255,mant=1)

        #500; rst_n = 1'b1; #2000;
        for (k = 0; k < 4; k = k + 1) begin
            send_byte(8'hAA); send_byte(8'h55); send_byte(8'd11);        // fmt=11 (tf32)
            send_byte(vcode[k][7:0]); send_byte(vcode[k][15:8]); send_byte(vcode[k][18:16]); // lo/mid/hi
            send_byte(8'h00);                                            // trig
            #(BIT*3);
            if (dut.tx_buf0 !== 8'hA5 || dut.tx_buf1 !== vex[k][7:0] ||
                dut.tx_buf2 !== vex[k][15:8] || dut.tx_buf3 !== vex[k][23:16] ||
                dut.tx_buf4 !== vex[k][31:24]) begin
                errs = errs + 1;
                $display("MISMATCH k=%0d code=0x%05h tx={%h %h %h %h %h} exp=0x%08h", k, vcode[k],
                    dut.tx_buf0, dut.tx_buf1, dut.tx_buf2, dut.tx_buf3, dut.tx_buf4, vex[k]);
            end else $display("ok k=%0d code=0x%05h -> 0x%08h", k, vcode[k], vex[k]);
        end
        $display("TF32 WRAPPER FSM SIM: %0d errors (4 cases, decode 7-byte/3-code frame)", errs);
        $finish;
    end
endmodule
`default_nettype wire
