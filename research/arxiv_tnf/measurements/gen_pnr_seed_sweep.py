#!/usr/bin/env python3
"""Route one arm under several placer seeds and record what moves.

Produces `pnr_seed_sweep_2026-08-19.json` and the raw logs in `pnr_logs/`.

WHY THIS FILE EXISTS. Fourteen records sit in this directory; four have a
generator here, two have only a reader, and eight are mentioned by nothing in the
tree at all. A record no script can rebuild is a number nobody -- reader or author
-- can go behind. The sweep record was going to be the ninth such orphan, so this
is the generator, written to the standard the audit had just measured everything
else against.

WHAT IT MEASURES. One netlist, N placer seeds. The LUT count came back identical
in all five runs and Fmax moved 10.5%, so area is seed-invariant here and timing
is not. That matters because `tab:fullthroughput` prints sixteen frequencies to
0.01 MHz.

THE PART IS NOT THE CI'S. `xc7a200tfbg676-1` is the QMTech Wukong V1 of
`fpga/HARDWARE_SSOT.md`; `.github/workflows/tnf-cost-sweep.yml` routes
`xc7a200tfbg484-2`. Different package and different speed grade -- figures from
this script are not comparable to the sweep's and must not be substituted for them.

THE Fmax FIGURES REPRODUCE; THE LOG HASHES DO NOT. Re-running this script gave
all five Fmax values identical to the digit -- 408.16, 379.65, 411.52, 422.65,
384.91 -- and five DIFFERENT `log_sha256`, because nextpnr writes wall-clock
timings into its log. So the hash pins the file that was shipped, not a value a
re-run should reproduce. Verify the numbers by re-running; verify the logs by
hashing the shipped copies.

THE XDC IS GENERATED. Every pad gets `IOSTANDARD LVCMOS33` and no package pin, so
the placer chooses IO sites. A board XDC fixes them, and fixed IO changes routing
pressure. This is a deliberate simplification of a flow that has a board; it is
recorded in the output rather than hidden.
"""
import hashlib
import json
import pathlib
import re
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOGS = HERE / "pnr_logs"
OUT = HERE / "pnr_seed_sweep_2026-08-19.json"

TOP = "tnf_cost_e2m11_add_top"
PART = "xc7a200tfbg676-1"
SEEDS = (1, 2, 3, 4, 5)
TARGET_MHZ = 50.0

NEXTPNR = pathlib.Path.home() / "t27/build/fpga/openxc7/nextpnr-openxc7/build/nextpnr-xilinx"
CHIPDB = pathlib.Path.home() / f"t27/build/fpga/openxc7/{PART}.bin"


def synth(build):
    """Yosys, in the flow the sweep workflow pins -- minus its docker image.

    `-flatten` is deliberately absent: removing it is what made routing
    deterministic for the GF cells, and the sweep keeps the flow identical to the
    one that produced the audited rows.
    """
    src = ROOT / "fpga/openxc7-synth"
    j = build / f"{TOP}.json"
    cmd = (f"read_verilog {src}/tnf_cost/{TOP}.v {src}/gf_adder_param.v {src}/gf_mul_param.v; "
           f"synth_xilinx -abc9 -nocarry -arch xc7 -top {TOP}; "
           f"setundef -zero -params; stat; write_json {j}")
    r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True)
    if r.returncode or "\nERROR" in r.stdout:
        raise SystemExit(f"yosys failed:\n{r.stdout[-2000:]}")
    return j


def xdc_for(netlist_json, path):
    """IOSTANDARD for every pad, expanded BIT BY BIT.

    `get_ports {in_a}` does not match `in_a[0]`, and nextpnr then refuses the
    whole run with one error naming a single port -- which reads as a missing
    constraint rather than an unexpanded bus.
    """
    d = json.loads(pathlib.Path(netlist_json).read_text())
    mods = d["modules"]
    top = ([m for m, v in mods.items() if v.get("attributes", {}).get("top")] or list(mods))[0]
    lines = []
    for name, p in mods[top]["ports"].items():
        w = len(p["bits"])
        names = [name] if w == 1 else [f"{name}[{i}]" for i in range(w)]
        lines += [f"set_property IOSTANDARD LVCMOS33 [get_ports {{{n}}}]" for n in names]
    pathlib.Path(path).write_text("\n".join(lines) + "\n")
    return len(lines)


def route(netlist_json, xdc, seed, log):
    subprocess.run([str(NEXTPNR), "--chipdb", str(CHIPDB), "--xdc", str(xdc),
                    "--json", str(netlist_json), "--write", "/dev/null",
                    "--freq", str(TARGET_MHZ), "--seed", str(seed),
                    "--placer", "heap", "--router", "router1", "--timing-allow-fail"],
                   stdout=open(log, "w"), stderr=subprocess.STDOUT)
    text = pathlib.Path(log).read_text()
    f = re.findall(r"Max frequency for clock [^:]*: ([0-9.]+) MHz", text)
    if not f:
        raise SystemExit(f"seed {seed}: no Fmax in {log} -- routing did not complete")
    lut = re.findall(r"SLICE_LUTX:\s*(\d+)", text)
    ff = re.findall(r"SLICE_FFX:\s*(\d+)", text)
    return dict(seed=seed,
                fmax_mhz=float(f[-1]),
                fmax_preroute_mhz=float(f[0]) if len(f) > 1 else None,
                luts=int(lut[-1]) if lut else None,
                ffs=int(ff[-1]) if ff else None,
                # Pins the SHIPPED log, not a reproducible value: nextpnr writes
                # wall-clock timings, so a re-run hashes differently while every
                # Fmax comes back identical.
                log_sha256=hashlib.sha256(text.encode()).hexdigest())


def main():
    for p in (NEXTPNR, CHIPDB):
        if not p.exists():
            raise SystemExit(f"missing {p} -- see fpga/HARDWARE_SSOT.md")
    LOGS.mkdir(exist_ok=True)
    build = ROOT / "build/tnfcost"
    build.mkdir(parents=True, exist_ok=True)
    netlist = synth(build)
    xdc = build / "sweep_generic.xdc"
    npads = xdc_for(netlist, xdc)

    rows = [route(netlist, xdc, s, LOGS / f"e2m11_add_seed{s}.log") for s in SEEDS]
    fm = [r["fmax_mhz"] for r in rows]
    med = statistics.median(fm)
    rec = dict(
        top=TOP, status="routed", part=PART,
        note=("QMTech Wukong V1 per fpga/HARDWARE_SSOT.md. The CI sweep routes "
              "xc7a200tfbg484-2 (AX7203): DIFFERENT package AND speed grade, so these "
              "figures are not comparable to the CI's and are not offered as such."),
        flow=dict(yosys="local yosys (CI uses docker regymm/openxc7)",
                  nextpnr="openXC7 nextpnr-xilinx, --placer heap --router router1",
                  xdc=f"generated, IOSTANDARD LVCMOS33 on all {npads} pads, NO package "
                      "pins -- the placer chose IO sites, which the CI's board xdc fixes",
                  target_freq_mhz=TARGET_MHZ),
        seeds=rows,
        fmax_median_mhz=round(med, 2),
        fmax_min_mhz=round(min(fm), 2), fmax_max_mhz=round(max(fm), 2),
        fmax_spread_mhz=round(max(fm) - min(fm), 2),
        fmax_spread_pct=round(100 * (max(fm) - min(fm)) / med, 1),
        luts_identical_across_seeds=len({r["luts"] for r in rows}) == 1,
        reproducibility=("Fmax reproduces exactly on a re-run; log_sha256 does not, "
                         "because nextpnr logs wall-clock timings. The hashes pin the "
                         "shipped logs rather than predicting a re-run."),
        finding=(f"{len(SEEDS)} placer seeds on ONE netlist give Fmax "
                 f"{min(fm):.2f}-{max(fm):.2f} MHz, a spread of "
                 f"{100*(max(fm)-min(fm))/med:.1f}% of the median, while the LUT count "
                 "is identical in all of them. Area is seed-invariant here; timing is "
                 "not. A frequency quoted to 0.01 MHz from an unstated number of seeds "
                 "is over-precise against its own reproducibility."),
    )
    OUT.write_text(json.dumps(rec, indent=2) + "\n")
    print(f"{OUT.name}: median {rec['fmax_median_mhz']} MHz, "
          f"spread {rec['fmax_spread_pct']}%, LUTs identical={rec['luts_identical_across_seeds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
