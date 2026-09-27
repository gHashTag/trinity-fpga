#!/usr/bin/env python3
"""Build a TRI-NET node bitstream for the ALINX AX7203 (xc7a200tfbg484-2) with the
local openXC7 toolchain.  Mirrors .github/workflows/ax7203-trinet-fleet.yml.

    yosys (synth_xilinx) -> nextpnr-xilinx -> fasm2frames -> xc7frames2bit

It NEVER touches the board: no openocd, no openFPGALoader, no /dev/cu.*.
The flash command is printed as text only (needs the owner's explicit yes).

Example:
    python3 fpga/openxc7-synth/build_trinet_node.py --out /tmp/trinet-node-build/node0
    python3 fpga/openxc7-synth/build_trinet_node.py --node 1 --rev 1bb1d97e --out /tmp/trinet-node-build/node1
    python3 fpga/openxc7-synth/build_trinet_node.py --top blink --src blink.v --xdc blink.xdc \
        --no-node-params --out /tmp/trinet-node-build/smoke

Keep --out outside the repository. Findings and hashes of the 2026-09-27
restore: conformance/NODE_TOOLCHAIN_RESTORE.md.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "trinity-fpga")
OXC7 = os.path.join(HOME, "openxc7-src")
NEXTPNR_SRC = os.path.join(OXC7, "nextpnr-xilinx")
DB_SUBMODULE = os.path.join(NEXTPNR_SRC, "xilinx", "external", "prjxray-db")
# The prjxray-db revision nextpnr-xilinx pins (openXC7 fork).  The checked-out
# submodule on this host is f4pga upstream 0a0adde, which lacks the
# CFG_CENTER_* ppips -> fasm2frames fails on STARTUPE2 routing.  We export the
# pinned tree read-only with `git archive` instead of checking it out.
DB_PIN = "ab1fc60c38a0dc1bc1d3d495f3189b25ae971e04"
# Outside the repository: the export is 187 MB.
DB_CACHE = os.path.join(HOME, ".cache", "openxc7", "prjxray-db-ab1fc60")
PRJXRAY = os.path.join(OXC7, "prjxray")

DEFAULT_TOP = "trinet_node_v2_ax7203"
DEFAULT_SRC = ["fpga/openxc7-synth/trinet_siphash24.v",
               "fpga/portable/trinet_node_core.v",
               "fpga/vivado/trinet_node_v2_ax7203.v"]
DEFAULT_XDC = "specs/fpga/constraints/gf16_clean_ax7203.xdc"
NODE_IDS = {0: "32'h5452494E", 1: "32'h5452494F", 2: "32'h54524950"}
FLASH_CFG = "fpga/openxc7-synth/ax7203_al321.cfg"

FORBIDDEN = ("openocd", "openFPGALoader", "xc3sprog")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def payload_sha256(bit):
    """sha256 of the config data from the sync word 0xAA995566 on.  The .bit
    header embeds the .frames path and a date/time, so the whole-file sha256
    differs on every run; this one is stable (verified 2026-09-27)."""
    with open(bit, "rb") as f:
        b = f.read()
    i = b.find(bytes.fromhex("aa995566"))
    return hashlib.sha256(b[i:]).hexdigest() if i >= 0 else None


def parse_time_l(text):
    """Parse macOS `/usr/bin/time -l` output."""
    out = {}
    m = re.search(r"([\d.]+) real", text)
    if m:
        out["wall_s"] = float(m.group(1))
    m = re.search(r"(\d+)\s+maximum resident set size", text)
    if m:
        out["max_rss_mb"] = round(int(m.group(1)) / 2**20, 1)
    m = re.search(r"(\d+)\s+peak memory footprint", text)
    if m:
        out["peak_footprint_mb"] = round(int(m.group(1)) / 2**20, 1)
    return out


def run_step(name, cmd, outdir, outputs, env=None, stdin=None):
    """Run one step under /usr/bin/time -l; delete its outputs first so a failed
    step can never leave a stale artefact that looks like a success."""
    if any(os.path.basename(str(c)) in FORBIDDEN for c in cmd):
        sys.exit("refusing to run a board-touching tool: %s" % cmd[0])
    for o in outputs:
        if os.path.exists(o):
            os.remove(o)
    log = os.path.join(outdir, name + ".log")
    t0 = time.time()
    with open(log, "wb") as lf:
        p = subprocess.run(["/usr/bin/time", "-l"] + [str(c) for c in cmd],
                           stdout=lf, stderr=subprocess.PIPE, env=env,
                           cwd=outdir, stdin=stdin)
    err = p.stderr.decode(errors="replace")
    with open(log, "ab") as lf:
        lf.write(b"\n--- stderr ---\n" + p.stderr)
    rec = {"step": name, "cmd": [str(c) for c in cmd], "rc": p.returncode,
           "log": log, **parse_time_l(err)}
    rec.setdefault("wall_s", round(time.time() - t0, 2))
    bad = [o for o in outputs if not os.path.exists(o) or os.path.getsize(o) == 0]
    print("[%-12s] rc=%d  %6.1f s  rss %s MB" % (name, p.returncode, rec["wall_s"],
                                                 rec.get("max_rss_mb", "?")))
    if p.returncode != 0 or bad:
        tail = "\n".join(err.strip().splitlines()[-15:])
        sys.exit("step %s FAILED (rc=%d, missing/empty: %s)\n%s\nsee %s"
                 % (name, p.returncode, bad, tail, log))
    return rec


def tool_versions():
    def first(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (r.stdout or r.stderr).strip().splitlines()[0]
        except Exception as e:  # noqa: BLE001
            return "UNAVAILABLE: %s" % e
    v = {"yosys": first(["yosys", "-V"]),
         "nextpnr-xilinx": first(["nextpnr-xilinx", "--version"]),
         "python3": sys.version.split()[0]}
    for tool, repo in (("prjxray", PRJXRAY), ("nextpnr-xilinx-src", NEXTPNR_SRC)):
        v[tool] = first(["git", "-C", repo, "log", "-1", "--format=%h %cd"])
    # The steps run these names from PATH, and two nextpnr-xilinx builds here print the same
    # --version (one writes ZINV_T1, one does not): record which file ran, by path and sha256.
    for tool in ("yosys", "nextpnr-xilinx"):
        path = shutil.which(tool)
        v[tool + "-bin"] = ("%s sha256 %s" % (os.path.realpath(path), sha256(path))
                            if path else "UNAVAILABLE: not on PATH")
    return v


def ensure_db(db_root):
    if os.path.isdir(db_root):
        return
    if os.path.abspath(db_root) != os.path.join(DB_CACHE, "artix7"):
        sys.exit("db root %s does not exist" % db_root)
    print("exporting prjxray-db %s (artix7) -> %s" % (DB_PIN[:7], DB_CACHE))
    os.makedirs(DB_CACHE, exist_ok=True)
    ga = subprocess.Popen(["git", "-C", DB_SUBMODULE, "archive", DB_PIN, "artix7"],
                          stdout=subprocess.PIPE)
    # --exclude: the db ships artix7/settings.sh; this workspace keeps no .sh files
    subprocess.run(["tar", "-x", "--exclude", "*.sh", "-C", DB_CACHE], stdin=ga.stdout, check=True)
    if ga.wait() != 0:
        sys.exit("git archive of prjxray-db %s failed" % DB_PIN)


def snapshot_sources(args, srcdir):
    """Copy (or `git show` at --rev) every input into out/src so a concurrent
    push to the repo cannot change the design mid-build."""
    os.makedirs(srcdir, exist_ok=True)
    files = []
    for rel in args.src + [args.xdc]:
        dst = os.path.join(srcdir, os.path.basename(rel))
        if args.rev:
            blob = subprocess.run(["git", "-C", args.repo, "show", "%s:%s" % (args.rev, rel)],
                                  capture_output=True, check=True).stdout
            with open(dst, "wb") as f:
                f.write(blob)
        else:
            path = rel if os.path.isabs(rel) else os.path.join(args.repo, rel)
            shutil.copyfile(path, dst)
        files.append(dst)
    return files[:-1], files[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", default=DEFAULT_TOP)
    ap.add_argument("--xdc", default=DEFAULT_XDC, help="repo-relative or absolute")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--src", nargs="+", default=DEFAULT_SRC, help="repo-relative or absolute")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--rev", help="take --src/--xdc from this git rev (e.g. 1bb1d97e)")
    ap.add_argument("--node", type=int, choices=sorted(NODE_IDS), default=0)
    ap.add_argument("--baud-div", type=int, default=60)
    ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                    help="extra chparam, overrides node defaults")
    ap.add_argument("--no-node-params", action="store_true",
                    help="skip USE_DNA/FALLBACK_NODE_ID/BAUD_DIV_P (non-node designs)")
    ap.add_argument("--part", default="xc7a200tfbg484-2")
    ap.add_argument("--chipdb", default=os.path.join(OXC7, "chipdb", "xc7a200tfbg484-2.bin"))
    ap.add_argument("--db-root", default=os.path.join(DB_CACHE, "artix7"))
    ap.add_argument("--freq", default="50.0")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--placer", default="heap", choices=["heap", "sa"])
    ap.add_argument("--seed-search", action="store_true",
                    help="CI behaviour: heap then sa, seeds 1..8, first routed wins")
    ap.add_argument("--name", help="bitstream basename (default trinet_node<N>)")
    ap.add_argument("--nosrl", action="store_true",
                    help="synth_xilinx -nosrl: plain flip-flops, no SRL16E/SRLC32E")
    ap.add_argument("--allow-srl", action="store_true",
                    help="go on to nextpnr even if yosys inferred shift-register LUTs")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    name = args.name or ("trinet_node%d" % args.node if args.top == DEFAULT_TOP else args.top)
    ensure_db(args.db_root)
    srcs, xdc = snapshot_sources(args, os.path.join(out, "src"))
    steps = []

    # 1. yosys -- identical script to CI
    params = {}
    if not args.no_node_params:
        params = {"USE_DNA": "0", "FALLBACK_NODE_ID": NODE_IDS[args.node],
                  "BAUD_DIV_P": str(args.baud_div)}
    for kv in args.param:
        k, v = kv.split("=", 1)
        params[k] = v
    chparam = ""
    if params:
        chparam = "chparam %s %s; " % (" ".join("-set %s %s" % kv for kv in params.items()), args.top)
    json_out = os.path.join(out, "node.json")
    ys = ("read_verilog %s; %ssynth_xilinx -flatten -abc9 -nocarry -nodsp%s -arch xc7 -top %s; "
          "setundef -zero -params; write_json %s"
          % (" ".join(srcs), chparam, " -nosrl" if args.nosrl else "", args.top, json_out))
    steps.append(run_step("yosys", ["yosys", "-q", "-l", os.path.join(out, "yosys.full.log"),
                                    "-p", ys], out, [json_out]))
    with open(os.path.join(out, "yosys.full.log")) as f:
        ystat = f.read()
    if re.search(r"^ *\d+ +DSP48", ystat, re.M):
        sys.exit("DSP48 inferred -- CI guard would fail")
    # 2026-09-27: tnf16_board_ax7203 with 19 SRL16E sat in router1 for over 13 min
    # (two runs); the same netlist with -nosrl routed in 28 s. The node has none.
    if re.search(r"^ *\d+ +SRL(16E|C32E)", ystat, re.M) and not args.allow_srl:
        sys.exit("SRL16E/SRLC32E inferred: router1 did not finish on such a netlist on this Mac. "
                 "Rebuild with --nosrl (or --allow-srl to try anyway).")

    # 2. nextpnr-xilinx
    fasm = os.path.join(out, "node.fasm")
    routed = os.path.join(out, "node_routed.json")
    tries = ([(p, s) for p in ("heap", "sa") for s in range(1, 9)]
             if args.seed_search else [(args.placer, args.seed)])
    chosen = None
    for placer, seed in tries:
        cmd = ["nextpnr-xilinx", "--chipdb", args.chipdb, "--xdc", xdc, "--json", json_out,
               "--write", routed, "--fasm", fasm, "--freq", args.freq, "--seed", str(seed),
               "--placer", placer, "--router", "router1", "--timing-allow-fail"]
        try:
            rec = run_step("nextpnr", cmd, out, [fasm, routed])
        except SystemExit as e:
            if not args.seed_search:
                raise
            print("  %s/seed %d failed: %s" % (placer, seed, str(e).splitlines()[0]))
            continue
        with open(rec["log"], errors="replace") as f:
            log = f.read()
        if "Failed to find a route" in log:
            print("  %s/seed %d: unrouted nets" % (placer, seed))
            continue
        fm = re.findall(r"Max frequency for clock\s+'([^']+)': ([\d.]+) MHz", log)  # nextpnr pads short names: clock  'rxc'
        rec["fmax_mhz"] = {c: float(v) for c, v in fm}  # last report wins (post-route)
        rec["placer"], rec["seed"] = placer, seed
        steps.append(rec)
        chosen = (placer, seed)
        break
    if not chosen:
        sys.exit("no placer/seed routed")

    # 3. fasm2frames (prjxray python).  Warn about the silent-drop trap.
    part_dir = os.path.join(args.db_root, args.part)
    req = os.path.join(part_dir, "required_features.fasm")
    frames = os.path.join(out, "node.frames")
    env = dict(os.environ, PYTHONPATH=PRJXRAY + os.pathsep + os.environ.get("PYTHONPATH", ""),
               PYTHONWARNINGS="ignore")
    steps.append(run_step("fasm2frames", [sys.executable, os.path.join(PRJXRAY, "utils", "fasm2frames.py"),
                                          "--db-root", args.db_root, "--part", args.part, fasm, frames],
                          out, [frames], env=env))

    # 4. xc7frames2bit
    bit = os.path.join(out, name + ".bit")
    steps.append(run_step("frames2bit", ["xc7frames2bit", "--part_file", os.path.join(part_dir, "part.yaml"),
                                         "--part_name", args.part, "--frm_file", frames,
                                         "--output_file", bit], out, [bit]))

    manifest = {
        "top": args.top, "part": args.part, "node": args.node, "params": params,
        "rev": args.rev, "placer_seed": chosen, "freq": args.freq, "yosys_script": ys,
        "chipdb": args.chipdb, "db_root": args.db_root,
        "required_features_fasm": os.path.exists(req),
        "inputs": {os.path.basename(p): sha256(p) for p in srcs + [xdc]},
        "tools": tool_versions(), "steps": steps,
        "outputs": {os.path.basename(p): {"bytes": os.path.getsize(p), "sha256": sha256(p)}
                    for p in (json_out, fasm, frames, bit)},
    }
    manifest["outputs"][os.path.basename(bit)]["payload_sha256"] = payload_sha256(bit)
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    ob = manifest["outputs"][os.path.basename(bit)]
    print("bit     %s\nsha256  %s  (file; header has path+time, not reproducible)\n"
          "payload %s  (from sync word; compare THIS)\nbytes   %d"
          % (bit, ob["sha256"], ob["payload_sha256"], os.path.getsize(bit)))
    if not manifest["required_features_fasm"]:
        print("note: %s has no required_features.fasm (same as CI; nothing added)" % args.part)
    print("\nFlash (needs owner's explicit yes; NOT run by this script):\n"
          "  cd %s && sudo /opt/homebrew/bin/openocd -f %s -c \"init\" "
          "-c \"pld load 0 %s\" -c \"runtest 2000\" -c \"shutdown\"" % (args.repo, FLASH_CFG, bit))


if __name__ == "__main__":
    main()
