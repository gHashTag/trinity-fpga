`default_nettype wire
`timescale 1ns / 1ps
// corona_decode_takum32_ax7203 — takum32 (FP32) decode on AX7203.
// NEW 32-bit decode frame: AA 55 fmt code[3] code[2] code[1] code[0] trig -> A5 FP32 LE.
// This extends the 16-bit decode frame (2 code bytes) to 32-bit (4 code bytes),
// opening the 32-bit-format decode column (takum32, int32, posit32, etc.).
//
// PIPELINED (2026-07-07): uses takum32_decode_pipelined (5-stage) instead of
// the combinational takum32_decode. The 87-bit + 72-bit multiplies + BRAM
// lookup + barrel-shift in the combinational version created an unroutable
// critical path (failed sa+heap x8, ~4h). Pipeline registers break the chain.
// frame_valid is delayed 5 cycles (frame_valid_d5) so tx_buf loads from the
// registered result on the correct cycle.
module corona_decode_takum32_ax7203 (
    input  wire rst_n, input wire uart_rx, output reg uart_tx, output wire [3:0] led
);
    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b0),.PACK(1'b0),
        .USRCCLKO(1'b0),.USRCCLKTS(1'b0),.USRDONEO(1'b0),.USRDONETS(1'b0));
    wire rst = ~rst_n | ~eos;
    localparam [8:0] BAUD_DIV = 9'd434;
    reg [26:0] cnt_c;
    always @(posedge mclk or posedge rst) if (rst) cnt_c<=0; else cnt_c<=cnt_c+1;
    assign led[0]=cnt_c[25]; assign led[3]=~rst;
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) if(rst) rsync<=3'b111; else rsync<={rsync[1:0],uart_rx};
    wire rxd=rsync[2];
    reg [1:0] rxs; reg [9:0] rxcnt; reg [2:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin rxs<=0;rxcnt<=0;rbi<=0;rxsr<=0;rx_byte<=0;rx_new<=0; end
        else begin rx_new<=0;
            case(rxs)
                2'd0: if(~rxd) begin rxcnt<=(BAUD_DIV+(BAUD_DIV>>1))-1;rxs<=1;rbi<=0; end
                2'd1: begin if(rxcnt==0) begin rxsr<={rxd,rxsr[7:1]}; if(rbi==7) begin rxs<=2;rxcnt<=BAUD_DIV-1; end else begin rbi<=rbi+1;rxcnt<=BAUD_DIV-1; end end else rxcnt<=rxcnt-1; end
                2'd2: begin if(rxcnt==0) begin rx_byte<=rxsr;rx_new<=1;rxs<=0; end else rxcnt<=rxcnt-1; end
                default: rxs<=0;
            endcase
        end
    end
    // 32-bit decode frame: AA 55 fmt code[3:0] trig (8 bytes)
    reg [2:0] frm; reg [7:0] fmt_r; reg [31:0] code_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;code_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                3'd0: frm<=(rx_byte==8'hAA)?3'd1:3'd0;
                3'd1: frm<=(rx_byte==8'h55)?3'd2:3'd0;
                3'd2: begin fmt_r<=rx_byte;frm<=3; end
                3'd3: begin code_r[7:0]<=rx_byte;frm<=4; end
                3'd4: begin code_r[15:8]<=rx_byte;frm<=5; end
                3'd5: begin code_r[23:16]<=rx_byte;frm<=6; end
                3'd6: begin code_r[31:24]<=rx_byte;frm<=7; end
                3'd7: begin frame_valid<=1;frm<=0; end
            endcase end
        end
    end
    assign led[1]=frame_valid;
    wire [31:0] result;
    wire        is_zero;
    takum32_decode_pipelined u_dec (.clk(mclk), .rst_n(~rst), .t32(code_r[31:0]), .fp32_out(result));
    assign led[2] = |result;
    // 6-cycle frame_valid delay to align tx_buf load with pipelined result
    // (5 pipeline stages + 1 extra for BRAM synchronous read latency)
    reg frame_valid_d1, frame_valid_d2, frame_valid_d3, frame_valid_d4, frame_valid_d5, frame_valid_d6;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frame_valid_d1<=0; frame_valid_d2<=0; frame_valid_d3<=0; frame_valid_d4<=0; frame_valid_d5<=0; frame_valid_d6<=0; end
        else begin frame_valid_d1<=frame_valid; frame_valid_d2<=frame_valid_d1; frame_valid_d3<=frame_valid_d2; frame_valid_d4<=frame_valid_d3; frame_valid_d5<=frame_valid_d4; frame_valid_d6<=frame_valid_d5; end
    end
    reg responding; reg [2:0] tx_idx; reg [7:0] tx_buf0,tx_buf1,tx_buf2,tx_buf3,tx_buf4;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF;tx_buf1<=8'hFF;tx_buf2<=8'hFF;tx_buf3<=8'hFF;tx_buf4<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(frame_valid_d6) begin
                tx_buf0<=8'hA5; tx_buf1<=result[7:0]; tx_buf2<=result[15:8];
                tx_buf3<=result[23:16]; tx_buf4<=result[31:24]; responding<=1; tx_idx<=0;
            end
            if(tcnt==0) begin tcnt<=BAUD_DIV-1;
                if(tbi==9) begin tbi<=0;
                    if(responding) begin
                        case(tx_idx)
                            3'd0: tsr<={1'b1,tx_buf0,1'b0}; 3'd1: tsr<={1'b1,tx_buf1,1'b0};
                            3'd2: tsr<={1'b1,tx_buf2,1'b0}; 3'd3: tsr<={1'b1,tx_buf3,1'b0};
                            3'd4: tsr<={1'b1,tx_buf4,1'b0};
                        endcase
                        if(tx_idx==4) responding<=0; else tx_idx<=tx_idx+1;
                    end else tsr<=10'h3FF;
                end else begin tbi<=tbi+1;tsr<={1'b1,tsr[9:1]}; end
            end else tcnt<=tcnt-1;
        end
    end
endmodule
`default_nettype wire
