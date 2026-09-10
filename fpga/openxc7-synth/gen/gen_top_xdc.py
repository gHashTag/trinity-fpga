#!/usr/bin/env python3
"""Constrain the pads a generated cost-sweep top actually has.

Run 34341199353 came back routing-pending on all five arms. The flow handed
nextpnr `corona_decode_ax7203.xdc`, which constrains led[0..3], rst_n, uart_rx
and uart_tx -- ports these tops do not have -- and left their own pads
unconstrained. That is a harness defect, not a fabric limit, and the two must
never be recorded as the same thing.

This writes an IO-standard-only constraint file, no package pins, which is the
shape of the local 2026-08-19 run that did route (tnf_cost_e2m11_add_top, 467
LUT at five seeds). Without package pins the placer chooses IO sites, so the
resulting Fmax is not a board number and is not offered as one.

usage: gen_top_xdc.py <yosys-json> <top> <out.xdc>
"""
import json, pathlib, sys


def main() -> int:
    src, top, out = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.loads(pathlib.Path(src).read_text())
    mods = d.get("modules", {})
    mod = mods.get(top)
    if mod is None:
        if len(mods) != 1:
            print(f"{top} not in {src} and it holds {len(mods)} modules", file=sys.stderr)
            return 2
        mod = next(iter(mods.values()))
    lines = []
    for name, port in mod.get("ports", {}).items():
        width = len(port.get("bits", []))
        for i in range(width):
            pad = f"{name}[{i}]" if width > 1 else name
            lines.append(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{pad}}}]")
    if not lines:
        print(f"{top} exposes no ports", file=sys.stderr)
        return 2
    pathlib.Path(out).write_text("\n".join(lines) + "\n")
    print(f"{top}: {len(lines)} pads constrained, IO standard only, no package pins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
