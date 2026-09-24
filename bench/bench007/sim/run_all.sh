#!/usr/bin/env bash
# Every check behind the kit, in one go. Exit status 0 only if all pass.
#   5 clock ratios for bench_meter, 3 planted faults that MUST fail,
#   the probe top with primitive stubs, and the analysis on synthetic data
#   (known answers, a broken instrument, a zero delta, one repetition).
set -u
cd "$(dirname "$0")"
T=$(mktemp -d); fail=0
ok()  { echo "  ok    $1"; }
bad() { echo "  FAIL  $1"; fail=1; }

echo "bench_meter, clock ratios (DUT half-period ps / step divider):"
for cfg in "7250 16" "1650 16" "50000 4" "7250 1" "2500 3"; do
  set -- $cfg
  iverilog -g2012 -DDUT_HALF_PS=$1 -DSTEPDIV=$2 -o $T/tb.vvp tb_bench_meter.v ../rtl/bench_meter.v &&
  vvp -n $T/tb.vvp | grep -q '^PASS' && ok "dut_half=$1 ps, step/$2" || bad "dut_half=$1 ps, step/$2"
done

echo "planted faults (each must be caught):"
plant() {   # name, sed expression
  sed "$2" ../rtl/bench_meter.v > $T/$1.v
  cmp -s ../rtl/bench_meter.v $T/$1.v && { bad "$1: plant did not apply"; return; }
  iverilog -g2012 -o $T/$1.vvp tb_bench_meter.v $T/$1.v && vvp -n $T/$1.vvp | grep -q '^PASS' \
    && bad "$1 NOT caught" || ok "$1 caught"
}
plant checksum_drops_steps 's/wire \[7:0\] chk = x4(seq_l) ^ x4(cyc_l) ^ x4(stp_l);/wire [7:0] chk = x4(seq_l) ^ x4(cyc_l);/'
plant step_counter_not_cleared 's/            stp_cnt  <= 32.d0;/            stp_cnt  <= stp_cnt;/'
plant cycle_count_off_by_two 's/cyc_snap <= cyc_cnt + 32.d1;/cyc_snap <= cyc_cnt + 32'"'"'d3;/'

echo "probe top with primitive stubs:"
iverilog -g2012 -o $T/top.vvp tb_top.v stubs_xilinx.v ../rtl/bench007_probe_ax7203.v ../rtl/bench_meter.v &&
vvp -n $T/top.vvp | grep -q 'PASS top' && ok "top: 3 lines, C in range" || bad "top"

echo "analysis on synthetic captures:"
A=../host/b7_analyze.py
python3 make_synthetic.py $T/a >/dev/null
python3 $A --uart $T/a/uart_probe_synth.log --expect-step-div 1024 --host-steps $T/a/uart_active_synth.log \
  --step-regex '^y=' --rate-source host --power "idle=$T/a/p_idle_r*.csv" --power "active=$T/a/p_active_r*.csv" \
  --meter-res-w 0.001 --out $T/a/r > $T/a.out 2>&1
grep -q '68.812345 MHz' $T/a.out && grep -q 'Verdict: \*\*resolved' $T/a.out && grep -q '1.799 mJ' $T/a.out \
  && ok "known answers: 68.812345 MHz, ΔP 45 mW resolved, 1.799 mJ/step" || bad "known answers"
python3 make_synthetic.py $T/b --delta-mw 0 >/dev/null
python3 $A --power "idle=$T/b/p_idle_r*.csv" --power "active=$T/b/p_active_r*.csv" --meter-res-w 0.001 \
  --out $T/b/r > $T/b.out 2>&1
grep -q 'NOT resolved' $T/b.out && ok "zero delta -> NOT resolved, upper bound" || bad "zero delta"
python3 make_synthetic.py $T/c --break-instrument >/dev/null
python3 $A --uart $T/c/uart_probe_synth.log --expect-step-div 1024 --out $T/c/r > $T/c.out 2>&1 \
  && bad "broken instrument not refused" || ok "broken instrument -> refused (non-zero exit)"
python3 $A --power "idle=$T/a/p_idle_r1.csv" --power "active=$T/a/p_active_r1.csv" --meter-res-w 0.001 \
  --out $T/d > $T/d.out 2>&1
grep -q 'No verdict' $T/d.out && ok "one repetition -> no verdict" || bad "one repetition"
python3 $A --uart $T/a/uart_probe_synth.log --gate-s 0.5 --out $T/e > $T/e.out 2>&1 \
  && bad "wrong --gate-s not caught" || ok "wrong --gate-s -> time-base mismatch refused"

rm -rf $T
[ $fail -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
