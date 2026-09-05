#!/usr/bin/env python3
"""Fmax of every format decoder, over several placer seeds, in resumable chunks.

Chunked on purpose: a background shell here is killed at 600 s, so the driver
does as much as fits in a budget, writes its state, and the next invocation picks
up where it stopped. State is the output file itself -- a run already present is
never repeated -- so re-invoking is safe and idempotent.

Each `fpga/tnet/d_*.v` is a self-contained harness: an LFSR feeds the decoder, the
result is registered, and eight LEDs take a XOR fold of it. Identical shape for
every format, so the comparison is between decoders and not between harnesses.
`d_baseline` is the control -- the same harness with no decoder in it -- and the
literature survey's objection was precisely that a control this size may dominate
what the table reports.
"""
import json
import pathlib
import re
import subprocess
import sys
import time

S = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                 "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
WT = S / "upstream-wt"
TNET = WT / "fpga/tnet"
BUILD = S / "fmax_build"
OUT = S / "fmax_results.json"
NEXTPNR = pathlib.Path.home() / "t27/build/fpga/openxc7/nextpnr-openxc7/build/nextpnr-xilinx"
CHIPDB = pathlib.Path.home() / "t27/build/fpga/openxc7/xc7a200tfbg676-1.bin"
SEEDS = (1, 2, 3, 4, 5)
TARGET = 50.0
BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 420.0

DEPS = json.loads((S / "dmap.json").read_text())


def load():
    return json.loads(OUT.read_text()) if OUT.exists() else {}


def save(d):
    OUT.write_text(json.dumps(d, indent=1) + "\n")


def synth(top, deps):
    j = BUILD / f"{top}.json"
    if j.exists():
        return j
    srcs = " ".join(str(TNET / s) for s in [f"{top[2:]}" and f"d_{top[2:]}.v"] + deps)
    cmd = (f"read_verilog {srcs}; synth_xilinx -abc9 -nocarry -arch xc7 -top {top}; "
           f"setundef -zero -params; stat; write_json {j}")
    r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, cwd=TNET)
    if r.returncode or "\nERROR" in r.stdout:
        return None
    lc = re.findall(r"Estimated number of LCs:\s*(\d+)", r.stdout)
    (BUILD / f"{top}.lc").write_text(lc[-1] if lc else "0")
    return j


def xdc_for(j, path):
    d = json.loads(pathlib.Path(j).read_text())
    mods = d["modules"]
    top = ([m for m, v in mods.items() if v.get("attributes", {}).get("top")] or list(mods))[0]
    lines = []
    for name, p in mods[top]["ports"].items():
        w = len(p["bits"])
        names = [name] if w == 1 else [f"{name}[{i}]" for i in range(w)]
        lines += [f"set_property IOSTANDARD LVCMOS33 [get_ports {{{n}}}]" for n in names]
    pathlib.Path(path).write_text("\n".join(lines) + "\n")


def route(j, xdc, seed, log):
    subprocess.run([str(NEXTPNR), "--chipdb", str(CHIPDB), "--xdc", str(xdc),
                    "--json", str(j), "--write", "/dev/null", "--freq", str(TARGET),
                    "--seed", str(seed), "--placer", "heap", "--router", "router1",
                    "--timing-allow-fail"], stdout=open(log, "w"), stderr=subprocess.STDOUT)
    t = pathlib.Path(log).read_text()
    f = re.findall(r"Max frequency for clock [^:]*: ([0-9.]+) MHz", t)
    lut = re.findall(r"SLICE_LUTX:\s*(\d+)", t)
    return (float(f[-1]) if f else None, int(lut[-1]) if lut else None)


def main():
    BUILD.mkdir(exist_ok=True)
    res = load()
    t0 = time.time()
    done = new = 0
    for e in DEPS:
        top = e["top"]
        res.setdefault(top, {"seeds": {}, "lc": None, "luts": None})
        j = synth(top, e["deps"])
        if j is None:
            res[top]["error"] = "yosys failed"
            continue
        lcf = BUILD / f"{top}.lc"
        if lcf.exists():
            res[top]["lc"] = int(lcf.read_text())
        xdc = BUILD / f"{top}.xdc"
        if not xdc.exists():
            xdc_for(j, xdc)
        for s in SEEDS:
            if str(s) in res[top]["seeds"]:
                done += 1
                continue
            if time.time() - t0 > BUDGET:
                save(res)
                print(f"budget reached: {new} new, {done} already had, "
                      f"{sum(len(v['seeds']) for v in res.values())}/{len(DEPS)*len(SEEDS)} total")
                return 2
            fm, lut = route(j, xdc, s, BUILD / f"{top}.s{s}.log")
            res[top]["seeds"][str(s)] = fm
            if lut:
                res[top]["luts"] = lut
            new += 1
            save(res)
    save(res)
    tot = sum(len(v["seeds"]) for v in res.values())
    print(f"complete: {tot}/{len(DEPS)*len(SEEDS)} runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
