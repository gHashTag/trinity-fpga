#!/usr/bin/env python3
"""Does the placer/router CONFIGURATION move Fmax more than the seed does?

Five seeds of one configuration gave dispersions from 1.6% to 41.7%. The CI tries
three configurations in order -- heap/router1, heap/router2, sa/router2 -- and
takes the first that routes, so a published median is a median over seeds WITHIN
whichever configuration happened to succeed. If configuration moves the number
more than seed does, that choice is doing more work than the median.

Resumable in chunks: a background shell here is killed at 600 s.
"""
import json, pathlib, re, subprocess, sys, time
S = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                 "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
BUILD = S / "wmax_build"
OUT = S / "cfg_results.json"
NEXTPNR = pathlib.Path.home() / "t27/build/fpga/openxc7/nextpnr-openxc7/build/nextpnr-xilinx"
CHIPDB = pathlib.Path.home() / "t27/build/fpga/openxc7/xc7a200tfbg676-1.bin"
DESIGNS = ['w_baseline', 'w_bin16', 'w_bin32', 'w_bnf16', 'w_fp8e4m3', 'w_fp8e5m2', 'w_gf10', 'w_gf14', 'w_gfplus8', 'w_gfternary', 'w_ibmhfp', 'w_int8', 'w_lns16', 'w_minifl', 'w_posit16', 'w_posit32', 'w_posit64', 'w_tnf16', 'w_tnf32', 'w_tnf64', 'w_vaxf']
CONFIGS = [("heap", "router1"), ("heap", "router2"), ("sa", "router2")]
SEEDS = (1, 2, 3, 4, 5)
BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 420.0

def main():
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    t0 = time.time()
    for top in DESIGNS:
        j = BUILD / f"{top}.json"; xdc = BUILD / f"{top}.xdc"
        if not (j.exists() and xdc.exists()):
            res.setdefault(top, {})["error"] = "no netlist -- run the w_ sweep first"; continue
        res.setdefault(top, {})
        for p, r in CONFIGS:
            key = f"{p}/{r}"
            res[top].setdefault(key, {})
            for s in SEEDS:
                if str(s) in res[top][key]: continue
                if time.time() - t0 > BUDGET:
                    OUT.write_text(json.dumps(res, indent=1) + "\n")
                    n = sum(len(v) for d in res.values() for k, v in d.items() if isinstance(v, dict))
                    print(f"budget reached: {n}/{len(DESIGNS)*len(CONFIGS)*len(SEEDS)}"); return 2
                log = BUILD / f"{top}.{p}.{r}.s{s}.log"
                subprocess.run([str(NEXTPNR), "--chipdb", str(CHIPDB), "--xdc", str(xdc),
                                "--json", str(j), "--write", "/dev/null", "--freq", "50.0",
                                "--seed", str(s), "--placer", p, "--router", r,
                                "--timing-allow-fail"], stdout=open(log, "w"),
                               stderr=subprocess.STDOUT)
                t = log.read_text()
                f = re.findall(r"Max frequency for clock [^:]*: ([0-9.]+) MHz", t)
                res[top][key][str(s)] = float(f[-1]) if f else None
                OUT.write_text(json.dumps(res, indent=1) + "\n")
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    n = sum(len(v) for d in res.values() for k, v in d.items() if isinstance(v, dict))
    print(f"complete: {n}/{len(DESIGNS)*len(CONFIGS)*len(SEEDS)}"); return 0

sys.exit(main())
