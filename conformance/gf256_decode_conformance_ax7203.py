#!/usr/bin/env python3
"""GF256 decode conformance — GoldenFloat N=256 -> FP32. 32-byte data frame.
Uses gf_decode_param.v iverilog golden reference for bit-exact comparison."""
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import struct, time, random, sys, argparse, subprocess, os

N = 256; E_BITS = 97; M_BITS = 158
BIAS = (1 << (E_BITS - 1)) - 1
EMAX = (1 << E_BITS) - 1

def golden_fp32(raw):
    """Use iverilog gf_decode_param as golden reference."""
    tb = f"""`timescale 1ns / 1ps
module tb;
    reg [{N-1}:0] gf_in;
    wire [31:0] fp32_out;
    gf_decode_param #(.N({N}), .E({E_BITS}), .M({M_BITS}), .BIAS({BIAS}), .OUT_REG(0)) u_dec (
        .gf_in(gf_in), .fp32_out(fp32_out),
        .is_nan_o(), .is_inf_o(), .is_zero_o(), .is_subnormal_o());
    initial begin
        gf_in = {N}'h{raw:0{N//4}x};
        #10 $display("%h", fp32_out);
        $finish;
    end
endmodule
"""
    tdir = "/tmp/gf256_golden"
    os.makedirs(tdir, exist_ok=True)
    with open(f"{tdir}/tb.v", "w") as f:
        f.write(tb)
    subprocess.run(
        ["iverilog", "-o", f"{tdir}/tb.vvp", f"{tdir}/tb.v",
         "fpga/openxc7-synth/gf_decode_param.v"],
        capture_output=True, check=True, cwd=os.getcwd()
    )
    r = subprocess.run(["vvp", f"{tdir}/tb.vvp"], capture_output=True, text=True, check=True)
    # Skip WARNING lines, find the hex output line
    for line in r.stdout.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('WARNING') and not line.startswith('$finish'):
            return int(line, 16)
    raise ValueError(f"No hex output found in: {r.stdout!r}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=100, help="random test vectors")
    args = ap.parse_args()

    codes = set()
    # Special values
    codes.add(0)                    # +0
    codes.add(1 << 255)             # -0
    codes.add(EMAX << M_BITS)       # +Inf
    codes.add((1 << 255) | (EMAX << M_BITS))  # -Inf
    codes.add((EMAX << M_BITS) | 1) # NaN

    # Values in FP32 range
    for e in [BIAS-200, BIAS-150, BIAS-149, BIAS-148, BIAS-127, BIAS-126,
              BIAS-1, BIAS, BIAS+1, BIAS+127, BIAS+128, BIAS+200]:
        for m in [0, 1, (1 << M_BITS) - 1, (1 << 235), (1 << 236) - 1]:
            for s in [0, 1]:
                raw = (s << 255) | (e << M_BITS) | m
                codes.add(raw)

    # Random (biased toward FP32-representable range)
    rng = random.Random(256)
    for _ in range(args.n):
        s = rng.randint(0, 1)
        e = BIAS + rng.randint(-200, 200)
        m = rng.randrange(1 << M_BITS)
        codes.add((s << 255) | (e << M_BITS) | m)

    codes = sorted(codes)
    port = serial.Serial(args.port, args.baud, timeout=5)
    ok = 0; fails = []

    for raw in codes:
        gold = golden_fp32(raw)
        b = [(raw >> (i * 8)) & 0xFF for i in range(32)]
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
                if len(fails) < 10:
                    fails.append(f"gold={gold:#010x} hw={d:#010x} exp={BIAS-raw>>158+BIAS}")
        else:
            if len(fails) < 10:
                fails.append(f"noresp")

    total = len(codes)
    print(f"HW RESULT: {ok}/{total} bit-exact (fails={total-ok})")
    for fmsg in fails:
        print(f"  {fmsg}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
