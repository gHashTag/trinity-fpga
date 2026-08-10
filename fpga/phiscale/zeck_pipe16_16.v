// Zeckendorf normaliser, 16-stage pipeline (2 compare-subtracts per stage).
// Stages past the last Fibonacci index pass their registers through, so the
// depth can exceed the number of compare-subtracts without leaving the
// output undriven -- which is how the first generator produced a design
// whose top digits had no driver.
`default_nettype none
module zeck_pipe16_16 (input wire clk, input wire [15:0] x, output wire [22:0] z);
    reg  [15:0] r [0:16];
    reg  [22:0] d [0:16];
    always @(posedge clk) begin r[0] <= x; d[0] <= 0; end
    wire [15:0] s0_r [0:2];
    wire [22:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[22] = (s0_r[0] >= 16'd46368);
    assign s0_r[1] = s0_d[22] ? (s0_r[0] - 16'd46368) : s0_r[0];
    assign s0_d[21] = (s0_r[1] >= 16'd28657);
    assign s0_r[2] = s0_d[21] ? (s0_r[1] - 16'd28657) : s0_r[1];
    always @(posedge clk) begin
      r[1] <= s0_r[2];
      d[1] <= d[0] | (s0_d & 23'd6291456);
    end
    wire [15:0] s1_r [0:2];
    wire [22:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[20] = (s1_r[0] >= 16'd17711);
    assign s1_r[1] = s1_d[20] ? (s1_r[0] - 16'd17711) : s1_r[0];
    assign s1_d[19] = (s1_r[1] >= 16'd10946);
    assign s1_r[2] = s1_d[19] ? (s1_r[1] - 16'd10946) : s1_r[1];
    always @(posedge clk) begin
      r[2] <= s1_r[2];
      d[2] <= d[1] | (s1_d & 23'd1572864);
    end
    wire [15:0] s2_r [0:2];
    wire [22:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[18] = (s2_r[0] >= 16'd6765);
    assign s2_r[1] = s2_d[18] ? (s2_r[0] - 16'd6765) : s2_r[0];
    assign s2_d[17] = (s2_r[1] >= 16'd4181);
    assign s2_r[2] = s2_d[17] ? (s2_r[1] - 16'd4181) : s2_r[1];
    always @(posedge clk) begin
      r[3] <= s2_r[2];
      d[3] <= d[2] | (s2_d & 23'd393216);
    end
    wire [15:0] s3_r [0:2];
    wire [22:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[16] = (s3_r[0] >= 16'd2584);
    assign s3_r[1] = s3_d[16] ? (s3_r[0] - 16'd2584) : s3_r[0];
    assign s3_d[15] = (s3_r[1] >= 16'd1597);
    assign s3_r[2] = s3_d[15] ? (s3_r[1] - 16'd1597) : s3_r[1];
    always @(posedge clk) begin
      r[4] <= s3_r[2];
      d[4] <= d[3] | (s3_d & 23'd98304);
    end
    wire [15:0] s4_r [0:2];
    wire [22:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[14] = (s4_r[0] >= 16'd987);
    assign s4_r[1] = s4_d[14] ? (s4_r[0] - 16'd987) : s4_r[0];
    assign s4_d[13] = (s4_r[1] >= 16'd610);
    assign s4_r[2] = s4_d[13] ? (s4_r[1] - 16'd610) : s4_r[1];
    always @(posedge clk) begin
      r[5] <= s4_r[2];
      d[5] <= d[4] | (s4_d & 23'd24576);
    end
    wire [15:0] s5_r [0:2];
    wire [22:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[12] = (s5_r[0] >= 16'd377);
    assign s5_r[1] = s5_d[12] ? (s5_r[0] - 16'd377) : s5_r[0];
    assign s5_d[11] = (s5_r[1] >= 16'd233);
    assign s5_r[2] = s5_d[11] ? (s5_r[1] - 16'd233) : s5_r[1];
    always @(posedge clk) begin
      r[6] <= s5_r[2];
      d[6] <= d[5] | (s5_d & 23'd6144);
    end
    wire [15:0] s6_r [0:2];
    wire [22:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[10] = (s6_r[0] >= 16'd144);
    assign s6_r[1] = s6_d[10] ? (s6_r[0] - 16'd144) : s6_r[0];
    assign s6_d[9] = (s6_r[1] >= 16'd89);
    assign s6_r[2] = s6_d[9] ? (s6_r[1] - 16'd89) : s6_r[1];
    always @(posedge clk) begin
      r[7] <= s6_r[2];
      d[7] <= d[6] | (s6_d & 23'd1536);
    end
    wire [15:0] s7_r [0:2];
    wire [22:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[8] = (s7_r[0] >= 16'd55);
    assign s7_r[1] = s7_d[8] ? (s7_r[0] - 16'd55) : s7_r[0];
    assign s7_d[7] = (s7_r[1] >= 16'd34);
    assign s7_r[2] = s7_d[7] ? (s7_r[1] - 16'd34) : s7_r[1];
    always @(posedge clk) begin
      r[8] <= s7_r[2];
      d[8] <= d[7] | (s7_d & 23'd384);
    end
    wire [15:0] s8_r [0:2];
    wire [22:0] s8_d;
    assign s8_r[0] = r[8];
    assign s8_d[6] = (s8_r[0] >= 16'd21);
    assign s8_r[1] = s8_d[6] ? (s8_r[0] - 16'd21) : s8_r[0];
    assign s8_d[5] = (s8_r[1] >= 16'd13);
    assign s8_r[2] = s8_d[5] ? (s8_r[1] - 16'd13) : s8_r[1];
    always @(posedge clk) begin
      r[9] <= s8_r[2];
      d[9] <= d[8] | (s8_d & 23'd96);
    end
    wire [15:0] s9_r [0:2];
    wire [22:0] s9_d;
    assign s9_r[0] = r[9];
    assign s9_d[4] = (s9_r[0] >= 16'd8);
    assign s9_r[1] = s9_d[4] ? (s9_r[0] - 16'd8) : s9_r[0];
    assign s9_d[3] = (s9_r[1] >= 16'd5);
    assign s9_r[2] = s9_d[3] ? (s9_r[1] - 16'd5) : s9_r[1];
    always @(posedge clk) begin
      r[10] <= s9_r[2];
      d[10] <= d[9] | (s9_d & 23'd24);
    end
    wire [15:0] s10_r [0:2];
    wire [22:0] s10_d;
    assign s10_r[0] = r[10];
    assign s10_d[2] = (s10_r[0] >= 16'd3);
    assign s10_r[1] = s10_d[2] ? (s10_r[0] - 16'd3) : s10_r[0];
    assign s10_d[1] = (s10_r[1] >= 16'd2);
    assign s10_r[2] = s10_d[1] ? (s10_r[1] - 16'd2) : s10_r[1];
    always @(posedge clk) begin
      r[11] <= s10_r[2];
      d[11] <= d[10] | (s10_d & 23'd6);
    end
    wire [15:0] s11_r [0:1];
    wire [22:0] s11_d;
    assign s11_r[0] = r[11];
    assign s11_d[0] = (s11_r[0] >= 16'd1);
    assign s11_r[1] = s11_d[0] ? (s11_r[0] - 16'd1) : s11_r[0];
    always @(posedge clk) begin
      r[12] <= s11_r[1];
      d[12] <= d[11] | (s11_d & 23'd1);
    end
    always @(posedge clk) begin r[13] <= r[12]; d[13] <= d[12]; end
    always @(posedge clk) begin r[14] <= r[13]; d[14] <= d[13]; end
    always @(posedge clk) begin r[15] <= r[14]; d[15] <= d[14]; end
    always @(posedge clk) begin r[16] <= r[15]; d[16] <= d[15]; end
    assign z = d[16];
endmodule
