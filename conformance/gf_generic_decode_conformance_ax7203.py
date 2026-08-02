#!/usr/bin/env python3
"""Generic GF decode conformance — works for any GF{N} format using iverilog golden.
Usage: python3 gf_generic_decode_conformance.py --fmt gf4 --port /dev/cu.usbserial-1120
"""
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import time, random, sys, argparse, subprocess, os

GF_PARAMS = {
    "gf4":  {"N": 4,  "E": 1, "M": 2,  "BIAS": 0,  "nbytes": 2},
    "gf6":  {"N": 6,  "E": 2, "M": 3,  "BIAS": 1,  "nbytes": 2},
    "gf8":  {"N": 8,  "E": 3, "M": 4,  "BIAS": 3,  "nbytes": 2},
    "gf10": {"N": 10, "E": 3, "M": 6,  "BIAS": 3,  "nbytes": 2},
    "gf12": {"N": 12, "E": 4, "M": 7,  "BIAS": 7,  "nbytes": 2},
    "gf14": {"N": 14, "E": 5, "M": 8,  "BIAS": 15, "nbytes": 2},
    "gf16": {"N": 16, "E": 6, "M": 9,  "BIAS": 31, "nbytes": 2},
    "gf20": {"N": 20, "E": 7, "M": 12, "BIAS": 63, "nbytes": 3},
    "gf24": {"N": 24, "E": 8, "M": 15, "BIAS": 127,"nbytes": 3},
    "gf32": {"N": 32, "E": 12,"M": 19, "BIAS": 2047,"nbytes": 4},
}

def golden_fp32(raw, params):
    N, E, M, BIAS = params["N"], params["E"], params["M"], params["BIAS"]
    mask = (1 << N) - 1
    tb = f"""`timescale 1ns / 1ps
module tb;
    reg [{N-1}:0] gf_in;
    wire [31:0] fp32_out;
    gf_decode_param #(.N({N}), .E({E}), .M({M}), .BIAS({BIAS}), .OUT_REG(0)) u_dec (
        .gf_in(gf_in), .fp32_out(fp32_out),
        .is_nan_o(), .is_inf_o(), .is_zero_o(), .is_subnormal_o());
    initial begin
        gf_in = {N}'h{raw & mask:0{N//4}x};
        #10 $display("%h", fp32_out);
        $finish;
    end
endmodule
"""
    tdir = f"/tmp/gf_golden_{N}"
    os.makedirs(tdir, exist_ok=True)
    with open(f"{tdir}/tb.v", "w") as f:
        f.write(tb)
    subprocess.run(
        ["iverilog", "-o", f"{tdir}/tb.vvp", f"{tdir}/tb.v",
         "fpga/openxc7-synth/gf_decode_param.v"],
        capture_output=True, check=True, cwd=os.getcwd()
    )
    r = subprocess.run(["vvp", f"{tdir}/tb.vvp"], capture_output=True, text=True, check=True)
    for line in r.stdout.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('WARNING') and not line.startswith('$finish'):
            return int(line, 16)
    raise ValueError(f"No hex output: {r.stdout!r}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", required=True, choices=list(GF_PARAMS.keys()))
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=200, help="random vectors (0=exhaustive if N<=12)")
    args = ap.parse_args()

    p = GF_PARAMS[args.fmt]
    N, nbytes = p["N"], p["nbytes"]
    mask = (1 << N) - 1

    # Generate test vectors
    if N <= 12 and args.n == 0:
        codes = list(range(1 << N))
    else:
        codes = set()
        codes.add(0)
        codes.add(1 << (N-1))
        E, M, BIAS = p["E"], p["M"], p["BIAS"]
        EMAX = (1 << E) - 1
        for e in [0, 1, BIAS-1, BIAS, BIAS+1, EMAX-1, EMAX]:
            for m in [0, 1, (1 << M) - 1 if M > 0 else 0]:
                for s in [0, 1]:
                    codes.add(((s << (N-1)) | (e << M) | m) & mask)
        rng = random.Random(42)
        for _ in range(args.n):
            codes.add(rng.randrange(1 << N) & mask)
        codes = sorted(codes)

    port = serial.Serial(args.port, args.baud, timeout=5)
    ok = 0; fails = []

    for raw in codes:
        gold = golden_fp32(raw, p)
        b = [(raw >> (i * 8)) & 0xFF for i in range(nbytes)]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.012)
        r = port.read(5)
        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            gn = (gold >> 23 & 0xFF) == 0xFF and (gold & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == gold:
                ok += 1
            else:
                if len(fails) < 5:
                    fails.append(f"raw=0x{raw:0{(N+3)//4}x} gold={gold:#010x} hw={d:#010x}")
        else:
            if len(fails) < 5:
                fails.append(f"raw=0x{raw:0{(N+3)//4}x} noresp")

    total = len(codes)
    print(f"HW RESULT: {ok}/{total} bit-exact (fails={total-ok})")
    for fmsg in fails:
        print(f"  {fmsg}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
