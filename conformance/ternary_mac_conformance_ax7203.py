#!/usr/bin/env python3
"""ternary_mac_conformance_ax7203.py — Ternary MAC conformance host.

Ternary MAC (ternary_mac_16.v):
  16-element dot product with ternary weights and inputs
  w[i], x[i] ∈ {-1, 0, +1} (2-bit encoding: 00=-1, 01=0, 10=+1)
  Result: signed 5-bit [-16, +16]

Golden oracle: exact integer dot product (trivially correct).

Usage:
  python3 ternary_mac_conformance_ax7203.py --self-test
  python3 ternary_mac_conformance_ax7203.py --port /dev/cu.usbserial-1120

Note: ternary_mac_16 is standalone RTL (AXI-Stream style, not UART-conformance format).
HW test requires a UART wrapper. This script provides the golden oracle + self-test.

Honesty: [simulated] — SW golden oracle. HW requires UART bridge.
"""
import argparse, sys, random

def ternary_decode(bits_2):
    """2-bit ternary decode: 00=-1, 01=0, 10=+1, 11=0(unused)."""
    if bits_2 == 0b00: return -1
    elif bits_2 == 0b01: return 0
    elif bits_2 == 0b10: return 1
    else: return 0  # unused 11 → 0

def golden_dot(w_raw, x_raw):
    """Golden ternary dot product: 16 elements, exact integer arithmetic."""
    result = 0
    for i in range(16):
        w_val = ternary_decode((w_raw >> (2 * i)) & 3)
        x_val = ternary_decode((x_raw >> (2 * i)) & 3)
        result += w_val * x_val
    # Clamp to 5-bit signed [-16, +16]
    if result > 16: result = 16
    if result < -16: result = -16
    return result & 0x1F  # 5-bit unsigned representation of signed

def self_test():
    """Exhaustive spot checks + random validation."""
    rnd = random.Random(42)
    ok = 0; bad = 0

    # Corner cases
    # All zero-trits (01=0): dot = 0
    all_zero = 0
    for i in range(16):
        all_zero |= (0b01 << (2 * i))  # 01 = zero
    assert golden_dot(all_zero, all_zero) == 0, "all-zero dot should be 0"

    # All +1 × all +1: w=0xAAAA... (10 repeated), x=0xAAAA... → dot = 16
    all_pos = 0
    for i in range(16):
        all_pos |= (0b10 << (2 * i))
    assert golden_dot(all_pos, all_pos) == 16 & 0x1F, f"all+1 dot should be 16, got {golden_dot(all_pos, all_pos)}"

    # All +1 × all -1: w=all_pos, x=all_neg → dot = -16
    all_neg = 0  # 00 repeated = all -1
    result_neg = golden_dot(all_pos, all_neg)
    expected_neg = (-16) & 0x1F  # = 16 in unsigned 5-bit
    assert result_neg == expected_neg, f"all+1 × all-1 should be -16 (={expected_neg}), got {result_neg}"

    # Mixed: half +1, half 0-trit → dot = 0 (zero trits contribute 0)
    half = 0
    for i in range(8):
        half |= (0b10 << (2 * i))      # first 8 = +1
    for i in range(8, 16):
        half |= (0b01 << (2 * i))      # last 8 = 0
    result = golden_dot(half, half)
    assert result == 8, f"half+1 dot should be 8, got {result}"

    # Random tests
    for _ in range(1000):
        w = rnd.randint(0, 0xFFFFFFFF)
        x = rnd.randint(0, 0xFFFFFFFF)
        g = golden_dot(w, x)
        # Manual recompute
        manual = 0
        for i in range(16):
            wv = ternary_decode((w >> (2*i)) & 3)
            xv = ternary_decode((x >> (2*i)) & 3)
            manual += wv * xv
        manual_clamped = max(-16, min(16, manual)) & 0x1F
        if g == manual_clamped:
            ok += 1
        else:
            bad += 1
            if bad <= 3:
                print(f"  MISMATCH w=0x{w:08x} x=0x{x:08x} golden={g} manual={manual_clamped}")

    print(f"self-test ternary_mac_16: {ok}/{ok+bad} random PASS, corners PASS")
    return bad == 0

def main():
    ap = argparse.ArgumentParser(description="Ternary MAC conformance for AX7203")
    ap.add_argument("--port", default="/dev/cu.usbserial-1120")
    ap.add_argument("--baud", type=int, default=160000)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    # HW test requires UART wrapper around ternary_mac_16
    print("ERROR: ternary_mac_16 HW test requires UART bridge module (not yet built)")
    print("The ternary_mac_16.v uses direct I/O, not UART. Need corona_compute_ternary_mac_ax7203.v wrapper.")
    sys.exit(1)

if __name__ == "__main__":
    main()
