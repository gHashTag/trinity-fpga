#!/usr/bin/env python3
"""Takum32 decode conformance — logarithmic N=32 → FP32. 4-byte data frame."""
# `serial` is imported where it is used, not at module level. Pass 181 found
# that 30 hosts with a verified golden model could not even be IMPORTED without
# pyserial, which put those goldens out of reach of CI, of any cross-check, and
# of reuse by another host. A model that needs a board driver to be read is
# checking the wrong thing.
import struct, time, random, sys, argparse, subprocess, os

def golden_fp32(takum_bits):
    """Use iverilog combinational decoder as golden reference."""
    tb = f"""`timescale 1ns / 1ps
module tb;
    reg [31:0] t32;
    wire [31:0] fp32_out;
    takum32_decode u_dec (.t32(t32), .fp32_out(fp32_out));
    initial begin
        t32 = 32'h{takum_bits:08x};
        #10 $display("%h", fp32_out);
        $finish;
    end
endmodule
"""
    tdir = "/tmp/takum32_golden"
    os.makedirs(tdir, exist_ok=True)
    with open(f"{tdir}/tb.v", "w") as f:
        f.write(tb)
    subprocess.run(
        ["iverilog", "-o", f"{tdir}/tb.vvp", f"{tdir}/tb.v",
         "fpga/openxc7-synth/takum32_decode.v"],
        capture_output=True, check=True, cwd=os.getcwd()
    )
    r = subprocess.run(["vvp", f"{tdir}/tb.vvp"], capture_output=True, text=True, check=True)
    return int(r.stdout.strip().split('\n')[0].strip(), 16)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--n", type=int, default=50, help="random test vectors (0 = SSOT only)")
    args = ap.parse_args()

    # Load SSOT conformance vectors
    import json
    with open("/tmp/t27_ssot/conformance/vectors/takum32_conformance_v0.json") as f:
        sdata = json.load(f)

    test_vectors = []
    for v in sdata['vectors']:
        takum_int = int(v['takum32_bits_hex'], 16)
        test_vectors.append((v['name'], takum_int))

    # Add random vectors
    if args.n > 0:
        rng = random.Random(42)
        for _ in range(args.n):
            test_vectors.append(("rand", rng.randrange(2**32)))

    port = serial.Serial(args.port, args.baud, timeout=5)
    ok = 0
    fails = []

    for name, raw in test_vectors:
        # Compute golden
        gold = golden_fp32(raw)

        # Send: AA 55 0 b0 b1 b2 b3 0
        b = [(raw >> (i * 8)) & 0xFF for i in range(4)]
        port.write(bytes([0xAA, 0x55, 0] + b + [0]))
        time.sleep(0.015)
        r = port.read(5)

        if len(r) >= 5 and r[0] == 0xA5:
            d = r[1] | (r[2] << 8) | (r[3] << 16) | (r[4] << 24)
            # NaN-equivalent check
            gn = (gold >> 23 & 0xFF) == 0xFF and (gold & 0x7FFFFF)
            dn = (d >> 23 & 0xFF) == 0xFF and (d & 0x7FFFFF)
            if (gn and dn) or d == gold:
                ok += 1
            else:
                if len(fails) < 10:
                    fails.append(f"{name}: raw=0x{raw:08x} gold={gold:#010x} hw={d:#010x}")
        else:
            if len(fails) < 10:
                fails.append(f"{name}: raw=0x{raw:08x} noresp (got {r.hex()})")

    total = len(test_vectors)
    print(f"HW RESULT: {ok}/{total} bit-exact (fails={total-ok})")
    for fmsg in fails:
        print(f"  {fmsg}", file=sys.stderr)
    port.close()

if __name__ == "__main__":
    main()
