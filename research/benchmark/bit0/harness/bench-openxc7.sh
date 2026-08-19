#!/usr/bin/env bash
# bench-openxc7.sh -- openXC7 side of the openXC7-vs-Vivado build-time benchmark
# (same-machine row). Times, for each of the 4 frozen designs, the three
# invocations of demo-projects' own openXC7.mk flow:
#
#     make <project>.json    (yosys synthesis)
#     make <project>.fasm    (nextpnr-xilinx place & route)
#     make <project>.bit     (fasm2frames + xc7frames2bit)
#
# each timed separately, so the numbers describe the project's own flow.
# Seed = each design's default (no --seed injected; PNR_ARGS untouched).
#
# The script runs on the HOST and re-executes itself INSIDE the frozen
# regymm/openxc7 container (image below), where yosys 0.62 / prjxray tools /
# pypy3 live and where nextpnr-xilinx was rebuilt from /bench/src at the
# frozen revision. All revisions are READ from the built tree at run time and
# stamped into the results -- nothing is hardcoded.
#
# Usage:
#     ./bench-openxc7.sh [-n N] [design ...]
#         -n N       runs per design (default 5)
#         design...  subset of: blinky picosoc-qmtech litex-ddr-arty-s7
#                    litex-ddr-arty-s7-deephier   (default: all 4)
#
# Smoke:            ./bench-openxc7.sh -n 1 blinky
# Full campaign (box must be quiet):
#     cd ~/data/openxc7/bench-openxc7 && \
#       nohup ./bench-openxc7.sh -n 5 > logs/campaign-$(date +%Y%m%d-%H%M%S).log 2>&1 &
#
# Output: results/bench-openxc7-<stamp>.csv
#         (design,run,json_s,fasm_s,bit_s,total_s,nextpnr_rev,prjxraydb_rev,yosys_ver)
#         results/bench-openxc7-<stamp>-machine.txt  (machine + full revision stamp)
#         logs/campaign-<stamp>/<design>-run<i>-<stage>.log
set -euo pipefail

IMAGE='docker.io/regymm/openxc7@sha256:eced1cdd4727549f2d983328e0cf170fb6f6f67d87f19b2bf24365163368c70c'

# ---------------------------------------------------------------- host mode --
if [ -z "${BENCH_IN_CONTAINER:-}" ]; then
    BENCH_DIR="${BENCH_DIR:-$HOME/data/openxc7/bench-openxc7}"
    exec podman run --rm --network=none --pull=never \
        -e BENCH_IN_CONTAINER=1 \
        -e BENCH_HOST="$(hostname)" \
        -v "$BENCH_DIR":/bench \
        "$IMAGE" \
        bash /bench/bench-openxc7.sh "$@"
fi

# ----------------------------------------------------------- container mode --
N=5
while getopts "n:h" opt; do
    case $opt in
        n) N=$OPTARG ;;
        h) sed -n '2,36p' "$0"; exit 0 ;;
        *) echo "bad option"; exit 2 ;;
    esac
done
shift $((OPTIND - 1))

# design table: name  dir  project  extra-make-args
ALL_DESIGNS="blinky picosoc-qmtech litex-ddr-arty-s7 litex-ddr-arty-s7-deephier"
design_row() {
    case "$1" in
        blinky)                     echo "designs/main/blinky-digilent-arty blinky -" ;;
        picosoc-qmtech)             echo "designs/main/picosoc picosoc BOARD=qmtech" ;;
        litex-ddr-arty-s7)          echo "designs/main/litex-ddr-arty-s7 digilent_arty_s7 -" ;;
        litex-ddr-arty-s7-deephier) echo "designs/deephier/litex-ddr-arty-s7 digilent_arty_s7 -" ;;
        *) return 1 ;;
    esac
}
DESIGNS="${*:-$ALL_DESIGNS}"
for d in $DESIGNS; do design_row "$d" >/dev/null || { echo "unknown design: $d"; exit 2; }; done

cd /bench
export NEXTPNR_XILINX_DIR=/bench/src/nextpnr-xilinx
export NEXTPNR_XILINX_PYTHON_DIR=$NEXTPNR_XILINX_DIR/xilinx/python
export PRJXRAY_DB_DIR=$NEXTPNR_XILINX_DIR/xilinx/external/prjxray-db
export ARTIX7_CHIPDB=/bench/chipdb
export KINTEX7_CHIPDB=/bench/chipdb
export SPARTAN7_CHIPDB=/bench/chipdb
# our frozen-revision binaries (nextpnr-xilinx and bbasm both sit at the
# repo root) ahead of the image's own
export PATH="$NEXTPNR_XILINX_DIR:$PATH"
git config --global --add safe.directory '*' 2>/dev/null || true

# --- revisions READ from the built tree (never hardcoded) --------------------
NEXTPNR_REV=$(git -C "$NEXTPNR_XILINX_DIR" rev-parse HEAD)
DB_GITLINK=$(git -C "$NEXTPNR_XILINX_DIR" ls-tree HEAD xilinx/external/prjxray-db | awk '{print $3}')
DB_CHECKOUT=$(git -C "$PRJXRAY_DB_DIR" rev-parse HEAD)
YOSYS_FULL=$(yosys --version | head -1)
YOSYS_VER=$(printf '%s\n' "$YOSYS_FULL" | sed -n 's/^Yosys \([^ ]*\) (git sha1 \([0-9a-f]*\).*/\1-\2/p')
[ -n "$YOSYS_VER" ] || YOSYS_VER=$(printf '%s\n' "$YOSYS_FULL" | awk '{print $2}')

# --- preflight guards --------------------------------------------------------
fail() { echo "FATAL: $*" >&2; exit 1; }
[ -n "$NEXTPNR_REV" ] || fail "cannot read nextpnr-xilinx revision from tree"
[ "$DB_GITLINK" = "$DB_CHECKOUT" ] \
    || fail "prjxray-db checkout ($DB_CHECKOUT) != gitlink ($DB_GITLINK)"
NEXTPNR_BIN=$(command -v nextpnr-xilinx) || fail "nextpnr-xilinx not on PATH"
case "$NEXTPNR_BIN" in
    /bench/src/*) ;;
    *) fail "nextpnr-xilinx resolves to $NEXTPNR_BIN, not the frozen /bench/src build" ;;
esac
NEXTPNR_VERSTR=$("$NEXTPNR_BIN" --version 2>&1 | head -1)
for bin in chipdb/xc7a35tcsg324.bin chipdb/xc7k325tffg676.bin chipdb/xc7s50csga324.bin; do
    [ -s "$bin" ] || fail "$bin missing -- run scripts/gen-chipdb.sh first (untimed step)"
done
[ -s designs/main/vexriscv/VexRiscv.v ] || fail "designs/main/vexriscv/VexRiscv.v missing"
[ -s designs/deephier/vexriscv/VexRiscv.v ] || fail "designs/deephier/vexriscv/VexRiscv.v missing"

STAMP=$(date +%Y%m%d-%H%M%S)
CSV=results/bench-openxc7-$STAMP.csv
META=results/bench-openxc7-$STAMP-machine.txt
LOGDIR=logs/campaign-$STAMP
mkdir -p results "$LOGDIR"

LOAD=$(cut -d' ' -f1-3 /proc/loadavg)
{
    echo "bench-openxc7 campaign $STAMP"
    echo "host:             ${BENCH_HOST:-unknown} (container hostname $(hostname))"
    echo "image:            $IMAGE"
    echo "kernel:           $(uname -sr)"
    echo "cpu:              $(awk -F': ' '/model name/{print $2; exit}' /proc/cpuinfo)"
    echo "cores:            $(nproc)"
    echo "mem_total:        $(awk '/MemTotal/{printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
    echo "loadavg_at_start: $LOAD"
    echo "runs_per_design:  $N"
    echo "designs:          $DESIGNS"
    echo "--- revisions (read from the built tree at run time):"
    echo "nextpnr-xilinx:   $NEXTPNR_REV"
    echo "nextpnr version:  $NEXTPNR_VERSTR"
    echo "prjxray-db:       $DB_CHECKOUT (gitlink-verified)"
    echo "yosys:            $YOSYS_FULL"
    echo "demo-projects main:     $(cat designs/main/REVISION 2>/dev/null)"
    echo "demo-projects deephier: $(cat designs/deephier/REVISION 2>/dev/null)"
} | tee "$META"

case "$LOAD" in
    0.*|1.*) ;;
    *) echo "WARNING: load average is $LOAD -- the box is NOT quiet; timings will be polluted" | tee -a "$META" ;;
esac

echo "design,run,json_s,fasm_s,bit_s,total_s,nextpnr_rev,prjxraydb_rev,yosys_ver" > "$CSV"

t_stage() {  # t_stage <logfile> <cmd...> -> prints elapsed seconds (%.2f)
    local log=$1 t0 t1; shift
    t0=$(date +%s.%N)
    "$@" > "$log" 2>&1
    t1=$(date +%s.%N)
    awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b - a}'
}

for d in $DESIGNS; do
    read -r dir project extra <<< "$(design_row "$d")"
    [ "$extra" = "-" ] && extra=""
    for i in $(seq 1 "$N"); do
        echo "=== $d run $i/$N (load $(cut -d' ' -f1 /proc/loadavg)) $(date -u +%FT%TZ)"
        make -C "$dir" $extra clean > "$LOGDIR/$d-run$i-clean.log" 2>&1
        json_s=$(t_stage "$LOGDIR/$d-run$i-json.log" make -C "$dir" $extra "$project.json")
        fasm_s=$(t_stage "$LOGDIR/$d-run$i-fasm.log" make -C "$dir" $extra "$project.fasm")
        bit_s=$(t_stage "$LOGDIR/$d-run$i-bit.log"  make -C "$dir" $extra "$project.bit")
        [ -s "$dir/$project.bit" ] || fail "$d run $i produced no $project.bit"
        total_s=$(awk -v a="$json_s" -v b="$fasm_s" -v c="$bit_s" 'BEGIN{printf "%.2f", a+b+c}')
        echo "$d,$i,$json_s,$fasm_s,$bit_s,$total_s,$NEXTPNR_REV,$DB_CHECKOUT,$YOSYS_VER" >> "$CSV"
        echo "    json=${json_s}s fasm=${fasm_s}s bit=${bit_s}s total=${total_s}s"
    done
done

echo "campaign done: $CSV"
