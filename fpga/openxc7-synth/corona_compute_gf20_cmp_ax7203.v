`default_nettype wire
`timescale 1ns / 1ps
// corona_compute_gf20_cmp_ax7203 — GoldenFloat20 comparison on AX7203.
// GF20: [S:1][E:7][M:12] = 20 bits, BIAS=63, HAS_INF=1.
//
// Frame protocol (10 bytes TX):
//   AA 55 fmt op a0 a1 a2 b0 b1 b2 trig
//   op: 0x00=EQ, 0x01=LT, 0x02=LE
// Response (5 bytes RX):
//   A5 r0 r1 r2 00

module corona_compute_gf20_cmp_ax7203 (
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
    always @(posedge mclk or posedge rst) if(rst) cnt_c<=0; else cnt_c<=cnt_c+1;
    assign led[0]=cnt_c[25]; assign led[3]=~rst;

    // ---- UART RX ----
    reg [2:0] rsync;
    always @(posedge mclk or posedge rst) if(rst) rsync<=3'b111; else rsync<={rsync[1:0],uart_rx};
    wire rxd=rsync[2];
    reg [1:0] rxs; reg [9:0] rxcnt; reg [3:0] rbi; reg [7:0] rxsr; reg [7:0] rx_byte; reg rx_new;
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

    // ---- Frame FSM ----
    reg [3:0] frm; reg [7:0] fmt_r, op_r; reg [19:0] a_r, b_r; reg frame_valid;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin frm<=0;fmt_r<=0;op_r<=0;a_r<=0;b_r<=0;frame_valid<=0; end
        else begin frame_valid<=0;
            if(rx_new) begin case(frm)
                4'd0: frm<=(rx_byte==8'hAA)?4'd1:4'd0;
                4'd1: frm<=(rx_byte==8'h55)?4'd2:4'd1;
                4'd2: begin fmt_r<=rx_byte;frm<=4'd3; end
                4'd3: begin op_r<=rx_byte;frm<=4'd4; end
                4'd4: begin a_r[7:0]<=rx_byte;frm<=4'd5; end
                4'd5: begin a_r[15:8]<=rx_byte;frm<=4'd6; end
                4'd6: begin a_r[19:16]<=rx_byte[3:0];frm<=4'd7; end
                4'd7: begin b_r[7:0]<=rx_byte;frm<=4'd8; end
                4'd8: begin b_r[15:8]<=rx_byte;frm<=4'd9; end
                4'd9: begin b_r[19:16]<=rx_byte[3:0];frm<=4'd10; end
                4'd10: begin frame_valid<=1;frm<=0; end
                default: frm<=0;
            endcase end
        end
    end
    assign led[1]=frame_valid;

    // ---- Comparison ----
    reg [19:0] a_reg, b_reg;
    reg [7:0] op_reg;
    reg comp_trigger;

    wire        sa = a_reg[19];
    wire [6:0]  ea = a_reg[18:12];
    wire [11:0]  ma = a_reg[11:0];
    wire        sb = b_reg[19];
    wire [6:0]  eb = b_reg[18:12];
    wire [11:0]  mb = b_reg[11:0];

    wire a_zero = (ea == 0) && (ma == 0);
    wire b_zero = (eb == 0) && (mb == 0);
    wire a_nan = (ea == {7{1'b1}}) && (ma != 0);
    wire b_nan = (eb == {7{1'b1}}) && (mb != 0);

    wire [18:0] abs_a = {ea, ma};
    wire [18:0] abs_b = {eb, mb};
    wire mag_lt = (abs_a < abs_b);
    wire mag_eq = (abs_a == abs_b);

    wire cmp_eq = (a_zero && b_zero) ||
                  (~(a_nan | b_nan) && (sa == sb) && ((a_zero && b_zero) || mag_eq));

    wire both_neg = sa && sb && ~(a_zero && b_zero);

    wire cmp_lt = (a_nan | b_nan) ? 1'b0 :
                  (a_zero && b_zero) ? 1'b0 :
                  (sa && ~sb) ? 1'b1 :
                  (~sa && sb) ? 1'b0 :
                  both_neg ? (abs_a > abs_b) :
                  mag_lt;

    wire cmp_le = cmp_lt | cmp_eq;

    always @(posedge mclk or posedge rst) begin
        if(rst) begin a_reg<=0; b_reg<=0; op_reg<=0; comp_trigger<=0; end
        else begin
            comp_trigger <= frame_valid;
            if(frame_valid) begin a_reg<=a_r; b_reg<=b_r; op_reg<=op_r; end
        end
    end

    wire cmp_result = (op_reg == 8'h00) ? cmp_eq :
                      (op_reg == 8'h01) ? cmp_lt :
                      (op_reg == 8'h02) ? cmp_le : 1'b0;

    reg [19:0] result_reg;   // widened: the TX path reads up to bit 19
    reg result_ready;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin result_reg<=0; result_ready<=0; end
        else begin
            result_ready <= comp_trigger;
            if(comp_trigger) result_reg <= cmp_result ? 8'h01 : 8'h00;
        end
    end
    assign led[2] = result_reg[0];

    // ---- UART TX ----
    reg responding; reg [2:0] tx_idx; reg [7:0] tx_buf0,tx_buf1,tx_buf2,tx_buf3,tx_buf4;
    reg [8:0] tcnt; reg [3:0] tbi; reg [9:0] tsr;
    always @(posedge mclk or posedge rst) begin
        if(rst) begin responding<=0;tx_idx<=0;tcnt<=BAUD_DIV-1;tbi<=0;tsr<=10'h3FF;uart_tx<=1;
            tx_buf0<=8'hFF;tx_buf1<=8'hFF;tx_buf2<=8'hFF;tx_buf3<=8'hFF;tx_buf4<=8'hFF; end
        else begin uart_tx<=tsr[0];
            if(result_ready) begin
                tx_buf0<=8'hA5;
                tx_buf1<=result_reg[7:0];
                tx_buf2<=result_reg[15:8];
                tx_buf3<={4'b0, result_reg[19:16]};
                tx_buf4<=8'h00;
                responding<=1; tx_idx<=0;
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
