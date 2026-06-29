#!/usr/bin/env python3
"""Structural FSM audit: verifies every decode/compute wrapper's frame FSM is
correctly formed (catches a per-clone state-number typo that variant FSM sims,
decode_verify, the slice-audit, and compile-check all miss).

Per wrapper, checks:
  - sync bytes 0xAA (state 0) + 0x55 (state 1) present
  - frame_valid (decode) OR gf_adder_param (compute) present
  - the frm next-state transitions include the full advance sequence 1..max
  - max state is one of the known FSM variant sizes (5=decode-6B, 6=tf32/compute-7B, 8=compute-9B)

  python3 conformance/wrapper_fsm_audit.py
"""
import re, glob, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAPPERS = (
    [w for w in glob.glob(os.path.join(ROOT, "fpga/openxc7-synth/corona_decode_*_ax7203.v"))
     if "corona_decode_top" not in w]
    + glob.glob(os.path.join(ROOT, "fpga/vivado/gf*_clean_ax7203.v"))
)


def main():
    bad = 0
    for w in sorted(WRAPPERS):
        src = open(w).read()
        name = os.path.basename(w)
        has_sync = ("8'hAA" in src) and ("8'h55" in src)
        has_out = ("frame_valid" in src) or ("gf_adder_param" in src)
        # frm next-state values (advance + wrap). Handles both forms:
        #   frm<=(rx_byte==8'hAA)?3'd1:3'd0   (sync, sized)
        #   frm<=3 / frm <= 3'd3              (data, unsized or sized, maybe spaced)
        nexts = set()
        for m in re.finditer(r"frm\s*<=\s*(?:\([^)]*\)\s*\?)?\s*(?:\d+'d)?(\d+)", src):
            nexts.add(int(m.group(1)))
        mx = max(nexts) if nexts else -1
        advance_ok = all(s in nexts for s in range(1, mx + 1))
        mx_ok = mx in (5, 6, 8)
        ok = has_sync and has_out and advance_ok and mx_ok
        if not ok:
            bad += 1
        print(f"{'OK   ' if ok else 'CHECK'} {name:42} max={mx} advance1..{mx}={'y' if advance_ok else 'N'} "
              f"sync={'y' if has_sync else 'N'} out={'y' if has_out else 'N'}")
    print(f"WRAPPER FSM AUDIT: {bad} need review / {len(WRAPPERS)} wrappers")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
