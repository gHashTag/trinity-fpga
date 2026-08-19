# run-design.tcl — Vivado side of the openXC7-vs-Vivado build-time benchmark.
#
# Non-project batch flow (UG892 style): read_verilog/read_xdc -> synth_design
# -> opt_design -> place_design -> route_design -> write_bitstream, with a
# wall-clock timestamp around each phase.
#
# Inputs (environment variables, set by bench.sh):
#   BM_TOP      top module name
#   BM_PART     full Xilinx part string (e.g. xc7a35tcsg324-1)
#   BM_XDC      space-separated XDC file paths (absolute)
#   BM_SOURCES  space-separated Verilog file paths (absolute)
#   BM_OUT      output basename (bitstream = $BM_OUT.bit)
#
# Outputs (in the current working directory = the per-run directory):
#   $BM_OUT.bit          the bitstream
#   timing_summary.rpt   full report_timing_summary (post-route)
#   utilization.rpt      post-route utilization
#   phase_times.csv      one line: synth_s,place_s,route_s,bitgen_s,total_s,wns,tns,timing_met
#
# Timed boundary (agreed method): synthesis + place-and-route + bitstream
# generation ONLY. Report generation and timing extraction happen OUTSIDE
# the timed phases (between route_design and write_bitstream timestamps).
# place_s = opt_design + place_design (mirrors the LiteX-generated Vivado
# flow, which runs opt_design before placement; no phys_opt_design).

proc now_ms {} { return [clock milliseconds] }

set top     $::env(BM_TOP)
set part    $::env(BM_PART)
set xdcs    $::env(BM_XDC)
set sources $::env(BM_SOURCES)
set out     [expr {[info exists ::env(BM_OUT)] ? $::env(BM_OUT) : $top}]

puts "BM: part=$part top=$top out=$out"
puts "BM: general.maxThreads=[get_param general.maxThreads] (Vivado default, not tuned)"

# ---------------- synth ----------------
set t0 [now_ms]
foreach f $sources { read_verilog $f }
foreach f $xdcs    { read_xdc $f }
synth_design -top $top -part $part
set t1 [now_ms]

# ---------------- opt + place (place_s) ----------------
opt_design
place_design
set t2 [now_ms]

# ---------------- route ----------------
route_design
set t3 [now_ms]

# ---------------- timing extraction (NOT in the timed boundary) ----------------
report_timing_summary -file timing_summary.rpt
report_utilization -file utilization.rpt

set wns "na"; set tns "na"; set whs "na"; set met "na"
if {![catch {open timing_summary.rpt r} fh]} {
    set txt [read $fh]
    close $fh
    # "Design Timing Summary" table: header line with WNS(ns) TNS(ns) ...,
    # a separator line, then the values line:
    #   WNS(ns) TNS(ns) TNS-failing TNS-total WHS(ns) THS(ns) ...
    if {[regexp {WNS\(ns\)[^\n]*\n[^\n]*\n\s*(\S+)\s+(\S+)\s+\S+\s+\S+\s+(\S+)} $txt -> w t h]} {
        set wns $w; set tns $t; set whs $h
    }
}
if {[string is double -strict $wns]} {
    # timing_met = setup closed (WNS >= 0) AND hold closed (WHS >= 0).
    set hold_ok [expr {![string is double -strict $whs] || $whs >= 0}]
    set met [expr {($wns >= 0 && $hold_ok) ? 1 : 0}]
} else {
    # No user timing constraints (or table absent): honest answer is "na".
    set wns "na"; set tns "na"; set met "na"
}

# ---------------- bitstream ----------------
set t4 [now_ms]
write_bitstream -force $out.bit
set t5 [now_ms]

set synth_s  [format %.2f [expr {($t1 - $t0) / 1000.0}]]
set place_s  [format %.2f [expr {($t2 - $t1) / 1000.0}]]
set route_s  [format %.2f [expr {($t3 - $t2) / 1000.0}]]
set bitgen_s [format %.2f [expr {($t5 - $t4) / 1000.0}]]
set total_s  [format %.2f [expr {(($t1-$t0) + ($t2-$t1) + ($t3-$t2) + ($t5-$t4)) / 1000.0}]]

set line "$synth_s,$place_s,$route_s,$bitgen_s,$total_s,$wns,$tns,$met"
set ofh [open phase_times.csv w]
puts $ofh $line
close $ofh
puts "BM_RESULT: $line"
puts "BM: done ($out.bit)"
