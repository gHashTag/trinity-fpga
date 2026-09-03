#!/usr/bin/env bash
# bench.sh — Vivado side of the openXC7-vs-Vivado build-time benchmark.
#
# Runs N repeated non-project Vivado builds per design and appends one CSV row
# per run:  design,run,synth_s,place_s,route_s,bitgen_s,total_s,wns,tns,timing_met
#
# Usage:
#   ./bench.sh [-n N] [design ...]
#     -n N       runs per design (default 5)
#     design...  names from designs.tsv (default: all)
#
# Smoke:            ./bench.sh -n 1 blinky-digilent-arty
# Full campaign:    mkdir -p logs && nohup ./bench.sh -n 5 > logs/campaign-$(date +%Y%m%d-%H%M%S).log 2>&1 &
#
# Per-run artifacts live in runs/<design>/<stamp>/run<i>/ (bit, vivado.log,
# timing_summary.rpt, utilization.rpt, phase_times.csv). Results CSV + machine
# description land in results/.

set -eo pipefail

BENCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIVADO_SETTINGS="${VIVADO_SETTINGS:-/home/builder/data/vivado/2026.1/Vivado/settings64.sh}"

N=5
while getopts "n:h" opt; do
    case "$opt" in
        n) N="$OPTARG" ;;
        h) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) exit 2 ;;
    esac
done
shift $((OPTIND - 1))

# Xilinx settings scripts are not `set -u` clean — source first, tighten after.
# shellcheck disable=SC1090
source "$VIVADO_SETTINGS"
set -u

# Vivado 2026.1 telemetry (Flexera RUI SDK, ~/.Xilinx/Vivado/.RUISDK) phones
# home during write_bitstream; on this egress-blocked host the TCP connects
# hang in SYN retries and add 5-7 MINUTES of wall time that Vivado books into
# write_bitstream (measured: bitgen 434 s and 300 s vs 12.8 s clean; evidence
# in diag/ss-sample.log — endpoints 67.227.186.229:443, 169.254.169.254:80).
# Pointing the proxy env at a closed local port makes those connects fail
# instantly WITHOUT touching the build flow: no build step needs network and
# the license is a local node-locked file.
export http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9
export HTTP_PROXY=$http_proxy HTTPS_PROXY=$https_proxy

# The proxy blackhole above is NOT sufficient: the RUI SDK connects DIRECTLY
# (raw connect(), never consults the proxy env) to 67.227.186.229:443 /
# 72.52.161.233:443 and probes the cloud-metadata address 169.254.169.254:80
# during write_bitstream. Campaign 20260815-080720 measured bitgen_s of
# 138.68/282.69/140.69/14.13/407.99 for identical deterministic work (true
# value ~13 s); diag/ss-sample.log and diag/ss-diagB.log show the SYN-SENT
# sockets owned by the vivado pid while the proxy env was exported. So EVERY
# vivado call goes through vivado-nonet.sh: a rootless user+network namespace
# (unshare -r -n) where only loopback exists and connect() fails instantly
# with ENETUNREACH — hermetic by construction. The node-locked license hostid
# (a MAC) is satisfied by a dummy lic0 interface inside the namespace; see
# vivado-nonet.sh. The proxy env above stays as belt-and-suspenders.
vivado_nonet() {
    "$BENCH_ROOT/vivado-nonet.sh" "$@"
}

TSV="$BENCH_ROOT/designs.tsv"
all_designs=$(grep -v '^\s*#' "$TSV" | grep -v '^\s*$' | cut -d'|' -f1)
if [ "$#" -gt 0 ]; then designs="$*"; else designs=$all_designs; fi

stamp=$(date +%Y%m%d-%H%M%S)
RESULTS="$BENCH_ROOT/results"
mkdir -p "$RESULTS"
CSV="$RESULTS/bench-$stamp.csv"
echo "design,run,synth_s,place_s,route_s,bitgen_s,total_s,wns,tns,timing_met" > "$CSV"

# Machine description (the method requires it alongside every result set).
MACH="$RESULTS/machine-$stamp.txt"
{
    echo "hostname:   $(hostname)"
    echo "date:       $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "nproc:      $(nproc)"
    free -g | awk '/^Mem:/{print "mem_gb:     "$2}'
    echo "os:         $(lsb_release -ds 2>/dev/null || cat /etc/os-release | head -1)"
    echo "cpu:        $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //')"
    echo "vivado:     $(vivado_nonet -version 2>/dev/null | head -1)"
    echo "runs_per_design: $N"
    echo "designs:    $(echo $designs | tr '\n' ' ')"
} > "$MACH"
cat "$MACH"

lookup() { # $1=design -> prints the tsv row
    grep -v '^\s*#' "$TSV" | awk -F'|' -v d="$1" '$1 == d {print; found=1} END {exit !found}'
}

for design in $designs; do
    if ! row=$(lookup "$design"); then
        echo "ERROR: design '$design' not in $TSV" >&2
        exit 2
    fi
    IFS='|' read -r name dir top part xdc srcs globs <<< "$row"
    srcdir="$BENCH_ROOT/designs/$dir"

    # Absolutize sources and constraints against the design dir.
    abs_srcs=""
    for s in $srcs; do abs_srcs="$abs_srcs $srcdir/$s"; done
    abs_xdc="$srcdir/$xdc"

    for i in $(seq 1 "$N"); do
        rundir="$BENCH_ROOT/runs/$design/$stamp/run$i"
        mkdir -p "$rundir"
        # Data files ($readmemh .init/.mem) resolve against Vivado's cwd.
        if [ -n "$globs" ]; then
            for g in $globs; do cp "$srcdir"/$g "$rundir"/ 2>/dev/null || true; done
        fi
        echo "=== $design run $i/$N ($(date +%H:%M:%S)) ==="
        if (cd "$rundir" && \
            BM_TOP="$top" BM_PART="$part" BM_XDC="$abs_xdc" \
            BM_SOURCES="$abs_srcs" BM_OUT="$design" \
            vivado_nonet -mode batch -nojournal -log vivado.log \
                   -source "$BENCH_ROOT/run-design.tcl" > console.log 2>&1) \
           && [ -s "$rundir/phase_times.csv" ] && [ -s "$rundir/$design.bit" ]; then
            echo "$design,$i,$(cat "$rundir/phase_times.csv")" >> "$CSV"
            tail -1 "$CSV"
        else
            echo "$design,$i,NA,NA,NA,NA,NA,na,na,error" >> "$CSV"
            echo "RUN FAILED — see $rundir/vivado.log (last lines):"
            tail -5 "$rundir/vivado.log" 2>/dev/null || tail -5 "$rundir/console.log"
        fi
    done
done

echo
echo "=== summary (median + spread of total_s per design) ==="
python3 - "$CSV" <<'EOF'
import csv, statistics, sys
rows = list(csv.DictReader(open(sys.argv[1])))
by = {}
for r in rows:
    by.setdefault(r["design"], []).append(r)
print(f"{'design':<28} {'n':>2} {'median_s':>9} {'min_s':>8} {'max_s':>8} {'spread%':>8}  timing")
for d, rs in by.items():
    ok = [float(r["total_s"]) for r in rs if r["timing_met"] != "error"]
    met = ",".join(sorted({r["timing_met"] for r in rs}))
    if not ok:
        print(f"{d:<28} {0:>2} {'-':>9} {'-':>8} {'-':>8} {'-':>8}  ALL FAILED")
        continue
    med = statistics.median(ok)
    spread = 100.0 * (max(ok) - min(ok)) / med if med else 0.0
    print(f"{d:<28} {len(ok):>2} {med:>9.2f} {min(ok):>8.2f} {max(ok):>8.2f} {spread:>7.1f}%  met={met}")
EOF

echo
echo "CSV:     $CSV"
echo "machine: $MACH"
