#!/usr/bin/env bash
# Independent iverilog witness for gf_decode_param.v -- all 10 Phase-A formats.
# Requires: iverilog (+vvp), python3. Run: bash fpga/witness/gf_decode/run_witness.sh
# Exit 0 iff all 10 PASS (fails=0). Written to be self-contained & reproducible.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
RTL="$HERE/../../openxc7-synth/gf_decode_param.v"
BUILD="$HERE/build"
rm -rf "$BUILD"; mkdir -p "$BUILD"
declare -a FMTS=("gf4 4 1 2 0" "gf6 6 2 3 1" "gf8 8 3 4 3" "gf10 10 3 6 3" "gf12 12 4 7 7" "gf14 14 5 8 15" "gf16 16 6 9 31" "gf20 20 7 12 63" "gf24 24 9 14 255" "gf32 32 12 19 2047")
printf "%-6s %-16s %-12s %s\n" "fmt" "vectors" "coverage" "verdict"
allpass=1
for row in "${FMTS[@]}"; do
  set -- $row; name=$1; N=$2; E=$3; M=$4; B=$5
  space=$((1<<N))
  if [ $space -le 70000 ]; then mode=exhaustive; else mode=repr; fi
  python3 "$HERE/golden_gen.py" "$BUILD" $name $N $E $M $B $mode >/dev/null
  python3 "$HERE/tb_gen.py"     "$BUILD" $name $N $E $M $B     >/dev/null
  iverilog -g2012 -o "$BUILD/sim_$name" "$BUILD/tb_$name.v" "$RTL" 2>"$BUILD/err_$name.txt"
  if [ $? -ne 0 ]; then echo "$name: IVERILOG COMPILE FAILED -- see $BUILD/err_$name.txt"; allpass=0; continue; fi
  res=$(vvp "$BUILD/sim_$name" 2>&1 | grep "HW RESULT")
  n=$(echo "$res" | grep -oE "[0-9]+/[0-9]+")
  if echo "$res" | grep -q "fails=0"; then verdict=PASS; else verdict=FAIL; allpass=0; fi
  printf "%-6s %-16s %-12s %s\n" "$name" "$n" "$mode" "$verdict"
done
echo "=============================="
if [ $allpass -eq 1 ]; then echo "ALL 10 Phase-A PASS (independent iverilog witness)"; exit 0
else echo "SOME FAIL"; exit 1; fi
