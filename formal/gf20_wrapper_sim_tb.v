// gf20 wrapper FSM sim: drives uart_rx with the WIDER 9-byte request frame
// (AA 55 a_lo a_mid a_hi b_lo b_mid b_hi trig) at baud timing, then reads the
// loaded tx_buf (A5 + 3 result bytes). Verifies gf20_clean_ax7203's NEW 9-state
// wider-frame FSM + gf_adder_param #(7,12) call + result packing end-to-end —
// the highest-risk untested FSM (new design, fire #6). Expected results computed
// via gf_ref.py (independent oracle): 0+0=0, 1+0=1, 1+1=2, max+max=saturate.
`timescale 1ns / 1ps
`default_nettype none
module gf20_wrapper_sim_tb;
    reg  rst_n = 1'b0;
    reg  uart_rx = 1'b1;
    wire uart_tx;
    wire [3:0] led;
    gf20_clean_ax7203 dut (.rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));

    localparam realtime BIT = 6076.0;
    task send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx = 1'b0; #BIT;
            for (i = 0; i < 8; i = i + 1) begin uart_rx = b[i]; #BIT; end
            uart_rx = 1'b1; #BIT;
        end
    endtask

    integer errs = 0;
    // (a, b, expected_result) — from gf_ref.gf_add(gf20). max+max saturates (HAS_INF=0).
    reg [19:0] va [0:3]; reg [19:0] vb [0:3]; reg [19:0] vex [0:3];
    integer k;

    initial #50000000 $finish;
    initial begin
        va[0]=20'h00000; vb[0]=20'h00000; vex[0]=20'h00000;  // 0+0=0
        va[1]=20'h3F000; vb[1]=20'h00000; vex[1]=20'h3F000;  // 1+0=1
        va[2]=20'h3F000; vb[2]=20'h3F000; vex[2]=20'h40000;  // 1+1=2
        va[3]=20'h7FFFF; vb[3]=20'h7FFFF; vex[3]=20'h7FFFF;  // max+max=saturate

        #500; rst_n = 1'b1; #2000;
        for (k = 0; k < 4; k = k + 1) begin
            send_byte(8'hAA); send_byte(8'h55);
            send_byte(va[k][7:0]); send_byte(va[k][15:8]); send_byte(va[k][19:16]); // a lo/mid/hi
            send_byte(vb[k][7:0]); send_byte(vb[k][15:8]); send_byte(vb[k][19:16]); // b lo/mid/hi
            send_byte(8'h00);                        // trig
            #(BIT*3);                                // RX FSM + frame FSM + adder + tx_buf settle
            if (dut.tx_buf0 !== 8'hA5 ||
                dut.tx_buf1 !== vex[k][7:0] || dut.tx_buf2 !== vex[k][15:8] ||
                dut.tx_buf3 !== {4'b0, vex[k][19:16]}) begin
                errs = errs + 1;
                $display("MISMATCH k=%0d tx={%h %h %h %h} exp=0x%05h", k,
                    dut.tx_buf0, dut.tx_buf1, dut.tx_buf2, dut.tx_buf3, vex[k]);
            end else $display("ok k=%0d 0x%05h+0x%05h=0x%05h", k, va[k], vb[k], vex[k]);
        end
        $display("GF20 WRAPPER FSM SIM: %0d errors (4 cases, 9-byte wider frame)", errs);
        $finish;
    end
endmodule
`default_nettype wire
