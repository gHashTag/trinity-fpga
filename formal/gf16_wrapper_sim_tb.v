// gf16 wrapper FSM sim: drives the compute 7-byte frame (AA 55 a_lo a_hi b_lo
// b_hi cmd) at baud timing, reads tx_buf (A5 + res_lo + res_hi + 00). Verifies
// the MIGRATED gf16_clean_ax7203 (parametric gf_adder_param #(6,9,HAS_INF=1))
// frame FSM + adder + packing end-to-end — covers the compute 7-byte-frame FSM
// variant (shared by gf4/6/8/12/16) and confirms the fire-#3 migration. Expected
// from gf_ref.py: 0+0, 1+0, 1+1=2, max+max -> Inf (HAS_INF=1).
`timescale 1ns / 1ps
`default_nettype none
module gf16_wrapper_sim_tb;
    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;
    gf16_clean_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

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
    reg [15:0] va [0:3]; reg [15:0] vb [0:3]; reg [15:0] vex [0:3];

    initial #50000000 $finish;
    initial begin
        va[0]=16'h0000; vb[0]=16'h0000; vex[0]=16'h0000;  // 0+0
        va[1]=16'h3E00; vb[1]=16'h0000; vex[1]=16'h3E00;  // 1+0=1
        va[2]=16'h3E00; vb[2]=16'h3E00; vex[2]=16'h4000;  // 1+1=2
        va[3]=16'h7DFF; vb[3]=16'h7DFF; vex[3]=16'h7E00;  // max+max -> Inf (HAS_INF=1)

        #500; rst_n = 1'b1; #2000;
        for (k = 0; k < 4; k = k + 1) begin
            send_byte(8'hAA); send_byte(8'h55);
            send_byte(va[k][7:0]); send_byte(va[k][15:8]);   // a lo/hi
            send_byte(vb[k][7:0]); send_byte(vb[k][15:8]);   // b lo/hi
            send_byte(8'h00);                                 // cmd
            #(BIT*3);
            if (dut.tx_buf0 !== 8'hA5 || dut.tx_buf1 !== vex[k][7:0] ||
                dut.tx_buf2 !== vex[k][15:8] || dut.tx_buf3 !== 8'h00) begin
                errs = errs + 1;
                $display("MISMATCH k=%0d tx={%h %h %h %h} exp=0x%04h", k,
                    dut.tx_buf0, dut.tx_buf1, dut.tx_buf2, dut.tx_buf3, vex[k]);
            end else $display("ok k=%0d 0x%04h+0x%04h=0x%04h", k, va[k], vb[k], vex[k]);
        end
        $display("GF16 WRAPPER FSM SIM: %0d errors (4 cases, compute 7-byte frame, HAS_INF=1)", errs);
        $finish;
    end
endmodule
`default_nettype wire
