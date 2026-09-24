`default_nettype none
// bench_meter -- BENCH-007 instrument: MEASURED clock and MEASURED step rate.
//
// What it answers
//   * How many cycles did the DUT clock actually tick in one second, where the
//     second is counted on the board's 200 MHz crystal (SiT9102, +-50 ppm)
//     rather than taken from an MMCM setting or a timing report?
//   * How many completed steps (one `dut_step` pulse each) happened in that
//     same second?
//
// ref_clk must be derived from the crystal (the AX7203 probe uses 200 MHz / 2).
// Output, once per window, on uart_tx at 115200 8N1 (baud derived from the
// crystal, so it does not depend on the clock being measured):
//
//     B7,SSSSSSSS,CCCCCCCC,PPPPPPPP,KK\r\n
//
//   S = window sequence number (hex, 32 bit). Window 0 is partial -- discard.
//   C = DUT clock cycles in the window (hex, 32 bit)
//   P = dut_step pulses in the window (hex, 32 bit)
//   K = checksum: XOR of the 12 bytes of S,C,P (hex)
//
// Accuracy of C: +-1 cycle from sampling the gate edge in the DUT domain, plus
// the crystal tolerance. At 70 MHz that is 1.4e-8 + 5e-5; the crystal dominates.
//
// Contract for a caller:
//   * dut_step is ONE dut_clk cycle high per completed step. A "done" held high
//     as a level must be edge-detected first, or every cycle it is high counts.
//   * GATE must be much longer than one report line (34 chars x 10 bits x
//     BAUD_DIV ref cycles = ~3 ms at 115200). S counts lines sent, so if a window
//     closed while a line was still going out it would be merged, not flagged.
//     The probe's 1 s window is ~340x the line time.
//
// CDC: toggle handshake in both directions. Snapshot registers change once per
// window and are read only after the toggle has crossed a 2-FF synchroniser, so
// they are stable for the whole read. The paths between the two domains are
// false paths by construction; if a timing tool analyses them, that report is
// about a path that is never sampled while changing.
module bench_meter #(
    parameter integer GATE     = 100_000_000,  // ref cycles per window (1 s at 100 MHz)
    parameter integer BAUD_DIV = 868           // 100e6 / 115200 = 868.06  (0.007 % error)
)(
    input  wire ref_clk,
    input  wire dut_clk,
    input  wire dut_step,
    output reg  uart_tx = 1'b1
);
    // ------------------------------------------------------------ ref: gate
    reg [31:0] gate_cnt = 32'd0;
    reg        gate_tgl = 1'b0;
    always @(posedge ref_clk) begin
        if (gate_cnt == GATE - 1) begin
            gate_cnt <= 32'd0;
            gate_tgl <= ~gate_tgl;
        end else begin
            gate_cnt <= gate_cnt + 32'd1;
        end
    end

    // ------------------------------------------------------------ dut: count
    (* ASYNC_REG = "TRUE" *) reg g_s1 = 1'b0, g_s2 = 1'b0;
    reg        g_s3     = 1'b0;
    reg [31:0] cyc_cnt  = 32'd0, stp_cnt  = 32'd0;
    reg [31:0] cyc_snap = 32'd0, stp_snap = 32'd0;
    reg        snap_tgl = 1'b0;
    wire       edge_dut = g_s2 ^ g_s3;
    always @(posedge dut_clk) begin
        g_s1 <= gate_tgl;
        g_s2 <= g_s1;
        g_s3 <= g_s2;
        if (edge_dut) begin
            // the detection cycle is the LAST cycle of the closing window
            cyc_snap <= cyc_cnt + 32'd1;
            stp_snap <= stp_cnt + {31'd0, dut_step};
            cyc_cnt  <= 32'd0;
            stp_cnt  <= 32'd0;
            snap_tgl <= ~snap_tgl;
        end else begin
            cyc_cnt  <= cyc_cnt + 32'd1;
            stp_cnt  <= stp_cnt + {31'd0, dut_step};
        end
    end

    // ------------------------------------------------------------ ref: read
    // Three short stages, all in the ref domain, so no path carries more than
    // a hex encoder or an XOR tree in one 5 ns cycle:
    //   L (latch)  copy the stable snapshot across            -> seq_l/cyc_l/stp_l
    //   B (build)  encode the whole line into a byte register  -> line
    //   T (tx)     shift bytes out, 8N1, BAUD_DIV ref cycles per bit
    // Measured on xc7a200tfbg484-2 (nextpnr-xilinx 45a986b): this domain closes
    // at ~166 MHz, so run it at 100 MHz, not at the raw 200 MHz crystal.
    (* ASYNC_REG = "TRUE" *) reg s_s1 = 1'b0, s_s2 = 1'b0;
    reg        s_s3    = 1'b0;
    reg        pending = 1'b0;
    reg [31:0] seq = 32'd0, seq_l = 32'd0, cyc_l = 32'd0, stp_l = 32'd0;
    reg [1:0]  stage = 2'd0;                 // 0 idle, 1 latched, 2 transmitting
    localparam integer NCHARS = 34;
    reg [8*NCHARS-1:0] line = {NCHARS{8'h0A}};   // first character in the top byte
    reg [5:0]  ci   = 6'd0;
    reg [3:0]  bi   = 4'd0;
    reg [15:0] baud = 16'd0;
    reg [7:0]  cur  = 8'hFF;

    function [7:0] hexc(input [3:0] n);
        hexc = (n < 4'd10) ? (8'd48 + {4'd0, n}) : (8'd55 + {4'd0, n});
    endfunction
    function [63:0] hex32(input [31:0] w);
        hex32 = {hexc(w[31:28]), hexc(w[27:24]), hexc(w[23:20]), hexc(w[19:16]),
                 hexc(w[15:12]), hexc(w[11:8]),  hexc(w[7:4]),   hexc(w[3:0])};
    endfunction
    function [7:0] x4(input [31:0] w);
        x4 = w[31:24] ^ w[23:16] ^ w[15:8] ^ w[7:0];
    endfunction

    wire [7:0] chk = x4(seq_l) ^ x4(cyc_l) ^ x4(stp_l);

    always @(posedge ref_clk) begin
        s_s1 <= snap_tgl;
        s_s2 <= s_s1;
        s_s3 <= s_s2;
        if (s_s2 ^ s_s3) pending <= 1'b1;

        case (stage)
        2'd0: begin
            uart_tx <= 1'b1;
            if (pending) begin
                // the snapshot last changed >= 2 ref cycles ago and will not
                // change again for ~one window: safe to copy
                pending <= 1'b0;
                seq_l   <= seq;
                cyc_l   <= cyc_snap;
                stp_l   <= stp_snap;
                seq     <= seq + 32'd1;
                stage   <= 2'd1;
            end
        end
        2'd1: begin
            line  <= {"B7,", hex32(seq_l), ",", hex32(cyc_l), ",", hex32(stp_l), ",",
                      hexc(chk[7:4]), hexc(chk[3:0]), 8'h0D, 8'h0A};
            ci    <= 6'd0;
            bi    <= 4'd0;
            baud  <= 16'd0;
            stage <= 2'd2;
        end
        default: begin
            if (baud != 16'd0) begin
                baud <= baud - 16'd1;
            end else if (ci == NCHARS) begin
                // the last stop bit has lasted a full bit period
                uart_tx <= 1'b1;
                stage   <= 2'd0;
            end else begin
                baud <= BAUD_DIV[15:0] - 16'd1;
                case (bi)
                    4'd0: begin
                        uart_tx <= 1'b0;                              // start bit
                        cur     <= line[8*NCHARS-1 -: 8];
                        line    <= {line[8*NCHARS-9:0], 8'h0A};
                        bi      <= 4'd1;
                    end
                    4'd9: begin
                        uart_tx <= 1'b1;                              // stop bit
                        bi      <= 4'd0;
                        ci      <= ci + 6'd1;
                    end
                    default: begin
                        uart_tx <= cur[0];                            // data, LSB first
                        cur     <= {1'b1, cur[7:1]};
                        bi      <= bi + 4'd1;
                    end
                endcase
            end
        end
        endcase
    end
endmodule
`default_nettype wire
