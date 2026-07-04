// tb_gf_decode.v
// -----------------------------------------------------------------------------
// Verilog testbench TEMPLATE for gf_decode_param.v. Reads a vector file
// produced by gen_vectors.py (golden-oracle output: gf_decode_ref.py) and
// compares the DUT's fp32_out against the expected IEEE binary32 value,
// bit-exact. Prints a final summary line in the canonical format used across
// the Trinity FPGA conformance suite:
//
//     HW RESULT: N/N bit-exact (fails=0)
//
// This line format is what UART-log parsers on AX7203 (corona-decode-host
// and friends) grep for to promote a cell to Tier E — see
// skills/user/trinity-wave-loop/references/burst-flash-checklist.md.
//
// USAGE (outside this sandbox, on a machine with iverilog/Vivado):
//   1. python3 gen_vectors.py gf16          # writes vectors/vectors_gf16.txt
//   2. iverilog -o sim_gf16 \
//        -DGF_N=16 -DGF_E=6 -DGF_M=9 -DGF_BIAS=31 \
//        -DVECTOR_FILE=\"vectors/vectors_gf16.txt\" \
//        tb_gf_decode.v gf_decode_param.v
//   3. vvp sim_gf16
//   Expected stdout tail: "HW RESULT: 4122/4122 bit-exact (fails=0)"
//
// To run the FULL Phase-A lineup, instantiate this pattern once per format
// (10 invocations, one per GF_N/E/M/BIAS/VECTOR_FILE combination) — either as
// 10 separate `iverilog` runs (simplest) or wrapped in a CI matrix job
// (see README.md "CI-workflow(ы)" section, one job per format, `strategy:
// matrix:` over the 10-row table).
//
// IMPORTANT — sandbox limitation: this repository/sandbox has NEITHER
// iverilog NOR yosys installed, so this testbench has NOT been executed
// here. Its correctness is a design-time claim based on 1:1 mirroring of
// the ALREADY bit-exact-verified rtl_bit_model.py comparison harness (see
// README.md "Что осталось за пользователем"). Running this file (or an
// equivalent Vivado xsim testbench) is a required user action before any
// Tier-E promotion.
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps

`ifndef GF_N
`define GF_N 16
`endif
`ifndef GF_E
`define GF_E 6
`endif
`ifndef GF_M
`define GF_M 9
`endif
`ifndef GF_BIAS
`define GF_BIAS 31
`endif
`ifndef VECTOR_FILE
`define VECTOR_FILE "vectors/vectors_gf16.txt"
`endif
`ifndef MAX_VECTORS
`define MAX_VECTORS 70000   // headroom above gf12's exhaustive 4096 and gf16-class 4122 sets
`endif

module tb_gf_decode;

    localparam integer N    = `GF_N;
    localparam integer E    = `GF_E;
    localparam integer M    = `GF_M;
    localparam integer BIAS = `GF_BIAS;

    reg  [N-1:0]  gf_in;
    wire [31:0]   fp32_out;
    wire          is_nan_o, is_inf_o, is_zero_o, is_subnormal_o;
    reg           clk;
    reg           rst_n;

    // DUT instantiated purely combinational (OUT_REG=0) for a simple
    // vector-by-vector comparison; flip OUT_REG=1 and add clocked stepping
    // if/when the registered-output variant needs its own timing testbench.
    gf_decode_param #(
        .N(N), .E(E), .M(M), .BIAS(BIAS), .OUT_REG(0)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .gf_in(gf_in),
        .fp32_out(fp32_out),
        .is_nan_o(is_nan_o), .is_inf_o(is_inf_o),
        .is_zero_o(is_zero_o), .is_subnormal_o(is_subnormal_o)
    );

    // ---- vector storage ----
    reg [N-1:0]  vec_gf   [0:`MAX_VECTORS-1];
    reg [31:0]   vec_exp  [0:`MAX_VECTORS-1];
    integer      n_vectors;
    integer      fails;
    integer      i;
    integer      fh;
    integer      code;

    // NaN-payload-agnostic compare: IEEE does not mandate a specific NaN bit
    // pattern, and the golden oracle / DUT both canonicalize to a quiet NaN
    // with a nonzero mantissa -- compare "is this exponent all-ones and
    // mantissa nonzero" for the NaN class instead of raw bit equality.
    function is_nan_bits;
        input [31:0] w;
        begin
            is_nan_bits = (w[30:23] == 8'hFF) && (w[22:0] != 23'b0);
        end
    endfunction

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst_n = 0;
        #12 rst_n = 1;

        // ---- load vector file: "<hex gf_in> <hex fp32_expected>" per line,
        // lines starting with '#' are comments (header metadata from
        // gen_vectors.py) and skipped.
        n_vectors = 0;
        fh = $fopen(`VECTOR_FILE, "r");
        if (fh == 0) begin
            $display("ERROR: could not open vector file %s", `VECTOR_FILE);
            $finish;
        end
        while (!$feof(fh) && n_vectors < `MAX_VECTORS) begin
            reg [8*256-1:0] line;
            reg [N-1:0] gf_val;
            reg [31:0]  exp_val;
            integer     rc;
            rc = $fscanf(fh, "%h %h\n", gf_val, exp_val);
            if (rc == 2) begin
                vec_gf[n_vectors]  = gf_val;
                vec_exp[n_vectors] = exp_val;
                n_vectors = n_vectors + 1;
            end else begin
                // skip comment/blank lines by reading and discarding to EOL
                code = $fgetc(fh);
                while (code != -1 && code != 10) code = $fgetc(fh);
            end
        end
        $fclose(fh);
        $display("Loaded %0d vectors from %s (N=%0d E=%0d M=%0d BIAS=%0d)",
                  n_vectors, `VECTOR_FILE, N, E, M, BIAS);

        // ---- run comparison ----
        fails = 0;
        for (i = 0; i < n_vectors; i = i + 1) begin
            gf_in = vec_gf[i];
            #1; // allow combinational settle
            if (is_nan_bits(vec_exp[i])) begin
                if (!is_nan_bits(fp32_out)) begin
                    fails = fails + 1;
                    if (fails <= 20)
                        $display("MISMATCH[%0d] gf_in=%0h expected=NaN(0x%08h) got=0x%08h",
                                  i, gf_in, vec_exp[i], fp32_out);
                end
            end else begin
                if (fp32_out !== vec_exp[i]) begin
                    fails = fails + 1;
                    if (fails <= 20)
                        $display("MISMATCH[%0d] gf_in=%0h expected=0x%08h got=0x%08h",
                                  i, gf_in, vec_exp[i], fp32_out);
                end
            end
        end

        // ---- canonical result line (grepped by UART-log / CI parsers) ----
        $display("HW RESULT: %0d/%0d bit-exact (fails=%0d)", n_vectors - fails, n_vectors, fails);

        if (fails == 0)
            $display("VERDICT: PASS");
        else
            $display("VERDICT: FAIL");

        $finish;
    end

endmodule
