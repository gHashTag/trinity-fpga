#!/usr/bin/env python3
"""BENCH-007 analysis: raw captures in, citable numbers out.

Self-tests run FIRST and abort before any number prints if one fails
(.claude/skills/measurement-discipline in trinity-fpga: "a harness without
self-tests produces mush, confidently").

Examples
  # probe session: measured CFGMCLK, instrument self-check on
  python3 b7_analyze.py --uart raw/uart_probe_*.log --expect-step-div 1024 --out results/probe

  # DUT session: clock/steps from bench_meter (B7) OR from host-counted lines,
  # plus power in three repetitions per condition
  python3 b7_analyze.py \
      --host-steps raw/uart_active_r1_*.log --step-regex '^y=' \
      --power idle=raw/p_idle_r1.csv,raw/p_idle_r2.csv,raw/p_idle_r3.csv \
      --power active=raw/p_active_r1.csv,raw/p_active_r2.csv,raw/p_active_r3.csv \
      --meter "FNIRSI FNB58" --meter-res-w 0.001 --meter-acc-pct 0.5 \
      --step-name "training step" --out results/xor

Power CSV: any delimiter; header names are matched case-insensitively.
  time      : time, timestamp, t, ts, elapsed, time_s
  power     : p, power, power_w, w, watts
  or V and I: voltage, voltage_v, v, vbus  and  current, current_a, i, ibus, a
Without a time column pass --sample-hz.
"""
import argparse
import csv
import glob
import hashlib
import io
import json
import math
import os
import platform
import re
import statistics as st
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b7_format import make_b7, parse_b7  # noqa: E402

TIME_KEYS = ("time", "timestamp", "t", "ts", "elapsed", "time_s", "time(s)")
P_KEYS = ("p", "power", "power_w", "w", "watts", "power(w)")
V_KEYS = ("voltage", "voltage_v", "v", "vbus", "volt", "voltage(v)")
I_KEYS = ("current", "current_a", "i", "ibus", "a", "amp", "current(a)")


# ----------------------------------------------------------------- readers
def read_uart_log(path):
    """[(t_ns, text)] from a b7_capture .log (comment lines skipped)."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            t, text = line.rstrip("\n").split("\t", 1)
            out.append((int(t), text))
    return out


def b7_windows(lines, with_time=False):
    """Valid B7 records, window 0 dropped. Returns (records, n_bad, gaps[, times_ns]).

    A line rejected by the checksum also shows up as a sequence gap."""
    recs, times, bad = [], [], 0
    for t, text in lines:
        if not text.startswith("B7"):
            continue
        r = parse_b7(text)
        if r is None:
            bad += 1
        elif r[0] != 0:
            recs.append(r)
            times.append(t)
    gaps = sum(1 for a, b in zip(recs, recs[1:]) if b[0] != a[0] + 1)
    return (recs, bad, gaps, times) if with_time else (recs, bad, gaps)


def read_power_csv(path, sample_hz=None, trim_s=0.0):
    """Trimmed samples of power in watts, and the duration they cover."""
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    rows = [r for r in raw.splitlines() if r.strip() and not r.lstrip().startswith("#")]
    if not rows:
        raise ValueError(f"{path}: empty")
    delim = "," if rows[0].count(",") else (";" if rows[0].count(";") else ("\t" if "\t" in rows[0] else None))
    split = (lambda s: next(csv.reader(io.StringIO(s), delimiter=delim))) if delim else (lambda s: s.split())
    head = [h.strip().lower() for h in split(rows[0])]

    def col(keys):
        for k in keys:
            if k in head:
                return head.index(k)
        return None

    it, ip, iv, ii = col(TIME_KEYS), col(P_KEYS), col(V_KEYS), col(I_KEYS)
    if ip is None and (iv is None or ii is None):
        raise ValueError(f"{path}: no power column and no voltage+current pair in header {head}")
    ts, ps = [], []
    for n, r in enumerate(rows[1:]):
        f = split(r)
        try:
            p = float(f[ip]) if ip is not None else float(f[iv]) * float(f[ii])
            t = float(f[it]) if it is not None else (n / sample_hz if sample_hz else None)
        except (ValueError, IndexError):
            continue
        if t is None:
            raise ValueError(f"{path}: no time column; pass --sample-hz")
        ts.append(t)
        ps.append(p)
    if len(ps) < 3:
        raise ValueError(f"{path}: fewer than 3 samples")
    t0, t1 = ts[0] + trim_s, ts[-1] - trim_s
    kept = [p for t, p in zip(ts, ps) if t0 <= t <= t1]
    if len(kept) < 3:
        raise ValueError(f"{path}: trimming {trim_s}s from both ends leaves {len(kept)} samples")
    return kept, (t1 - t0)


# ----------------------------------------------------------------- statistics
def summary(xs):
    n = len(xs)
    m = st.fmean(xs)
    sd = st.stdev(xs) if n > 1 else 0.0
    return {"n": n, "mean": m, "sd": sd, "sem": sd / math.sqrt(n) if n > 1 else float("nan"),
            "min": min(xs), "max": max(xs)}


def condition(files, sample_hz, trim_s):
    reps = []
    for fpath in files:
        samples, dur = read_power_csv(fpath, sample_hz, trim_s)
        s = summary(samples)
        s.update(file=fpath, duration_s=dur, sha256=sha(fpath))
        reps.append(s)
    means = [r["mean"] for r in reps]
    agg = summary(means) if len(means) > 1 else {"n": 1, "mean": means[0], "sd": float("nan"),
                                                  "sem": float("nan"), "min": means[0], "max": means[0]}
    agg["spread"] = agg["max"] - agg["min"]
    return {"reps": reps, "across_reps": agg}


# Student t, two-sided 99 % (= one-sided 99.5 %), by degrees of freedom.
_T995 = {1: 63.657, 2: 9.925, 3: 5.841, 4: 4.604, 5: 4.032, 6: 3.707, 7: 3.499, 8: 3.355, 9: 3.250,
         10: 3.169, 11: 3.106, 12: 3.055, 13: 3.012, 14: 2.977, 15: 2.947, 16: 2.921, 17: 2.898,
         18: 2.878, 19: 2.861, 20: 2.845, 25: 2.787, 30: 2.750, 40: 2.704, 60: 2.660, 120: 2.617}
MIN_REPS = 3
RES_K = 3.0          # a difference must also exceed 3 x the meter resolution


def t995(df):
    """Conservative: the table value at the largest tabulated df <= df."""
    if df < 1:
        return float("inf")
    keys = [k for k in _T995 if k <= df]
    return _T995[max(keys)] if df < 1e9 else 2.576


def delta_verdict(p_act, p_idle, res_w):
    """ΔP = P_active - P_idle with a verdict that can say no.

    Uncertainty: standard error of the difference of the per-repetition means
    (Welch), with a 99 % t critical value at the Welch-Satterthwaite degrees of
    freedom -- with 3 repetitions a condition has 2 degrees of freedom, and
    treating its SEM as a normal sigma would claim far more than the data hold.
    The meter resolution is a second floor.

      insufficient  fewer than MIN_REPS repetitions in either condition: no verdict
      resolved      d > margin           -> value, with a 99 % interval
      not resolved  |d| <= margin        -> one-sided 99.5 % upper bound only
      anomaly       d < -margin          -> active below idle: labels swapped,
                                            wrong files or drift. Stop, do not publish.
    """
    na, ni = p_act["n"], p_idle["n"]
    d = p_act["mean"] - p_idle["mean"]
    out = {"delta_w": d, "n_active": na, "n_idle": ni, "u_w": None, "df": None, "t": None,
           "margin_w": None, "status": None, "ci99_w": None, "upper_bound_w": None}
    if na < MIN_REPS or ni < MIN_REPS:
        out["status"] = "insufficient"
        return out
    sa, si = p_act["sem"], p_idle["sem"]
    u = math.sqrt(sa ** 2 + si ** 2)
    if u > 0:
        den = (sa ** 4 / (na - 1) if sa > 0 else 0.0) + (si ** 4 / (ni - 1) if si > 0 else 0.0)
        df = u ** 4 / den
        t = t995(df)
    else:
        df, t = float("inf"), 0.0                  # identical repetitions: only the meter floor is left
    margin = max(t * u, RES_K * res_w)
    out.update(u_w=u, df=df if math.isfinite(df) else None, t=t, margin_w=margin)
    if d > margin:
        out.update(status="resolved", ci99_w=[d - t * u, d + t * u])
    elif d < -margin:
        out["status"] = "anomaly"
    else:
        out.update(status="not_resolved", upper_bound_w=max(d, 0.0) + margin)
    return out


def host_rate(ts_ns):
    """(N-1)/(t_last - t_first) in 1/s, or None if the span is zero."""
    if len(ts_ns) < 2 or ts_ns[-1] <= ts_ns[0]:
        return None
    return (len(ts_ns) - 1) / ((ts_ns[-1] - ts_ns[0]) / 1e9)


def fmt_j(e):
    for unit, k in (("J", 1.0), ("mJ", 1e-3), ("µJ", 1e-6), ("nJ", 1e-9), ("pJ", 1e-12)):
        if abs(e) >= k:
            return f"{e / k:,.3f} {unit}"
    return f"{e / 1e-15:,.3f} fJ"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ----------------------------------------------------------------- self-tests
def self_tests(tmpdir):
    # 1. the parser returns exact values for a line built the way the RTL builds it
    for seq, cyc, stp in [(1, 68_812_345, 67_199), (0xFFFFFFFF, 0, 0), (7, 200_000_000, 1)]:
        assert parse_b7(make_b7(seq, cyc, stp)) == (seq, cyc, stp), "parser: round trip"
    # 1b. against a line printed by the RTL simulation (sim/tb_top.v: 100 MHz ref, stub CFGMCLK 68.8 MHz)
    assert parse_b7("B7,00000001,00006B82,0000001B,F3") == (1, 0x6B82, 0x1B), "parser vs RTL sim"
    # 2. NEGATIVE CONTROL: a corrupted checksum and a flipped digit must be rejected
    good = make_b7(3, 68_800_000, 67_187)
    assert parse_b7(good[:-2] + "00") is None or good.endswith("00"), "checksum not checked"
    flipped = good[:14] + ("1" if good[14] != "1" else "2") + good[15:]
    assert parse_b7(flipped) is None, "a corrupted digit passed the checksum"
    # 3. malformed / partial lines are rejected, not half-parsed
    for bad in ("", "B7", good[:-3], good + "0", "b7" + good[2:], good.replace(",", ";")):
        assert parse_b7(bad) is None, f"malformed accepted: {bad!r}"
    # 4. power reader: exact mean on a known file, both schemas, and trimming
    p1 = os.path.join(tmpdir, "st_p.csv")
    with open(p1, "w") as f:
        f.write("time,power\n" + "".join(f"{t},{3.0 if 2 <= t <= 8 else 99.0}\n" for t in range(11)))
    s, dur = read_power_csv(p1, trim_s=2.0)
    assert s == [3.0] * 7 and abs(dur - 6.0) < 1e-12, "power reader: trim or mean"
    p2 = os.path.join(tmpdir, "st_vi.csv")
    with open(p2, "w") as f:
        f.write("timestamp sample_in_packet voltage_V current_A\n" +
                "".join(f"{t} 0 12.0 0.25\n" for t in range(5)))
    s, _ = read_power_csv(p2)
    assert all(abs(x - 3.0) < 1e-12 for x in s), "power reader: V*I schema"
    # 5. the verdict can say NO, and refuses when it cannot know
    same = {"n": 3, "mean": 3.0, "sem": 0.002}
    v = delta_verdict(same, same, res_w=0.001)
    assert v["status"] == "not_resolved" and v["upper_bound_w"] > 0, "verdict: identical inputs resolved"
    v = delta_verdict({"n": 3, "mean": 3.5, "sem": 0.002}, same, res_w=0.001)
    assert v["status"] == "resolved" and abs(v["delta_w"] - 0.5) < 1e-12, "verdict: a clear delta not resolved"
    v = delta_verdict({"n": 1, "mean": 3.5, "sem": float("nan")}, same, res_w=0.001)
    assert v["status"] == "insufficient", "verdict given on one repetition"
    v = delta_verdict({"n": 3, "mean": 2.9, "sem": 0.002}, same, res_w=0.001)
    assert v["status"] == "anomaly", "active far below idle was not flagged"
    # t at 2 df must be the 99 % value, not a normal 3-sigma
    assert abs(t995(2.0) - 9.925) < 1e-9 and abs(t995(4.7) - 4.604) < 1e-9, "t table"
    # 6. B7 window logic: window 0 dropped, gaps counted, bad lines counted
    lines = [(0, make_b7(0, 5, 0)), (1, make_b7(1, 10, 1)), (2, make_b7(3, 10, 1)), (3, "B7,garbage")]
    recs, bad, gaps = b7_windows(lines)
    assert [r[0] for r in recs] == [1, 3] and bad == 1 and gaps == 1, "window bookkeeping"
    # 7. host step rate never divides by zero
    assert host_rate([5, 5, 5]) is None and abs(host_rate([0, 10**9, 2 * 10**9]) - 1.0) < 1e-12, "host rate"
    print("self-tests: 7/7 passed (incl. negative controls) -- numbers follow")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uart", nargs="*", default=[], help="b7_capture .log files carrying B7 lines")
    ap.add_argument("--gate-s", type=float, default=1.0,
                    help="window length in seconds = GATE / ref_clk (probe: 100e6 / 100 MHz = 1.0). "
                         "Cross-checked against the host clock; a mismatch > 0.5%% stops the run")
    ap.add_argument("--ref-ppm", type=float, default=50.0, help="crystal tolerance (SiT9102: +-50 ppm)")
    ap.add_argument("--expect-step-div", type=int, help="probe self-check: P must be floor/ceil(C/N)")
    ap.add_argument("--host-steps", nargs="*", default=[], help=".log files; count lines matching --step-regex")
    ap.add_argument("--step-regex", default=r".+")
    ap.add_argument("--step-name", default="step")
    ap.add_argument("--rate-source", choices=("die", "host"), help="which step rate feeds the energy figure "
                    "(default: the on-die counter if present, else host-counted)")
    ap.add_argument("--power", action="append", default=[], help="COND=file1,file2,...  (idle / active)")
    ap.add_argument("--sample-hz", type=float)
    ap.add_argument("--trim-s", type=float, default=5.0, help="seconds dropped at both ends of each power file")
    ap.add_argument("--meter", default="UNSPECIFIED")
    ap.add_argument("--meter-res-w", type=float, default=0.01, help="meter power resolution, W")
    ap.add_argument("--meter-acc-pct", type=float, help="meter accuracy, %% of reading (reported, not used in the verdict)")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    self_tests(a.out)
    for f in os.listdir(a.out):
        if f.startswith("st_"):
            os.remove(os.path.join(a.out, f))

    R = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "script_sha256": sha(os.path.abspath(__file__)), "python": platform.python_version(),
         "inputs": {}}
    md = ["# BENCH-007 -- computed results", "",
          f"Generated {R['generated_utc']} by `b7_analyze.py` (sha256 `{R['script_sha256'][:16]}…`).", ""]

    # --- clock and steps from the on-die instrument
    uart_files = sorted({p for g in a.uart for p in glob.glob(g)})
    steps_per_s = rate_die = rate_host = None
    if uart_files:
        recs, bad, gaps, tb = [], 0, 0, []
        for fpath in uart_files:
            r, b, g, ts = b7_windows(read_uart_log(fpath), with_time=True)
            recs += r
            bad += b
            gaps += g
            R["inputs"][fpath] = sha(fpath)
            if len(r) >= 10 and r[-1][0] > r[0][0]:
                tb.append((ts[-1] - ts[0]) / 1e9 / (r[-1][0] - r[0][0]))
        if not recs:
            sys.exit("no valid B7 windows in the given files")
        # the window length claimed by --gate-s, checked against the host clock
        if tb:
            host_gate = st.fmean(tb)
            R["timebase_check"] = {"gate_s_claimed": a.gate_s, "gate_s_host": host_gate}
            if abs(host_gate / a.gate_s - 1) > 0.005:
                sys.exit(f"TIME BASE MISMATCH: --gate-s {a.gate_s} but the host clock sees one window every "
                         f"{host_gate:.4f} s. Every frequency would be off by that ratio. Fix --gate-s "
                         f"(GATE / ref_clk) or check that the DUT clock is not stalling.")
        cyc = [r[1] / a.gate_s for r in recs]
        stp = [r[2] / a.gate_s for r in recs]
        c = summary(cyc)
        sys_hz = c["mean"] * a.ref_ppm * 1e-6
        stat_hz = c["sem"] if c["n"] > 1 else float("nan")
        clk = {"windows": c["n"], "bad_lines": bad, "seq_gaps": gaps, "mean_hz": c["mean"], "sd_hz": c["sd"],
               "min_hz": c["min"], "max_hz": c["max"], "stat_unc_hz": stat_hz,
               "crystal_unc_hz": sys_hz, "quantisation_hz": 1.0 / a.gate_s}
        R["clock"] = clk
        rate_die = steps_per_s = st.fmean(stp)
        R["steps_on_die"] = {"mean_per_s": steps_per_s, "sd_per_s": st.stdev(stp) if len(stp) > 1 else 0.0}
        md += ["## Clock, measured on the die against the 200 MHz crystal", "",
               "| quantity | value |", "|---|---|",
               f"| windows used (window 0 dropped) | {c['n']} |",
               f"| rejected lines (checksum/format) | {bad} |", f"| sequence gaps | {gaps} |",
               f"| clock, mean | **{c['mean'] / 1e6:.6f} MHz** |",
               f"| window-to-window sd | {c['sd']:.1f} Hz |",
               f"| min / max | {c['min'] / 1e6:.6f} / {c['max'] / 1e6:.6f} MHz |",
               f"| crystal tolerance (±{a.ref_ppm:g} ppm), systematic | ±{sys_hz:.0f} Hz |",
               f"| window length: claimed / seen by host | {a.gate_s:g} s / "
               + (f"{R['timebase_check']['gate_s_host']:.4f} s |" if "timebase_check" in R else "n/a (< 10 windows) |"),
               f"| {a.step_name}s per second (on-die counter) | {steps_per_s:,.1f} |", ""]
        if a.expect_step_div:
            n = a.expect_step_div
            viol = [r for r in recs if r[2] not in (r[1] // n, -(-r[1] // n))]
            R["instrument_selfcheck"] = {"div": n, "windows": len(recs), "violations": len(viol)}
            md += [f"Instrument self-check: P ∈ {{⌊C/{n}⌋, ⌈C/{n}⌉}} in "
                   f"{len(recs) - len(viol)}/{len(recs)} windows -- "
                   + ("**PASS**" if not viol else "**FAIL: the instrument is wrong, do not use these numbers**"), ""]

    # --- steps counted on the host (DUT that reports each step over UART)
    host_files = sorted({p for g in a.host_steps for p in glob.glob(g)})
    if host_files:
        rx = re.compile(a.step_regex)
        rates = []
        for fpath in host_files:
            ts = [t for t, text in read_uart_log(fpath) if rx.search(text)]
            R["inputs"][fpath] = sha(fpath)
            r = host_rate(ts)
            if r is None:
                print(f"warning: {fpath}: fewer than 2 matching lines or zero time span -- skipped")
            else:
                rates.append(r)
        if rates:
            rate_host = st.fmean(rates)
            steps_per_s = rate_host
            R["steps_host"] = {"files": len(host_files), "per_file_per_s": rates, "mean_per_s": steps_per_s,
                               "note": "host-paced: includes UART and host time, i.e. throughput AS RUN"}
            md += ["## Steps counted on the host", "",
                   f"{a.step_name}s per second, as run (includes UART and host turnaround): "
                   f"**{steps_per_s:,.2f}** (mean of {len(rates)} capture(s): "
                   + ", ".join(f"{r:,.2f}" for r in rates) + ")", ""]

    src = a.rate_source or ("die" if rate_die is not None else "host")
    steps_per_s = rate_die if src == "die" else rate_host
    if steps_per_s is not None:
        R["rate_used"] = {"source": src, "per_s": steps_per_s}

    # --- power
    conds = {}
    for spec in a.power:
        name, _, files = spec.partition("=")
        fl = sorted({p for g in files.split(",") for p in glob.glob(g.strip())})
        if not fl:
            sys.exit(f"--power {name}: no files matched {files}")
        conds[name] = condition(fl, a.sample_hz, a.trim_s)
        for r in conds[name]["reps"]:
            R["inputs"][r["file"]] = r["sha256"]
    if conds:
        R["power"] = conds
        R["meter"] = {"model": a.meter, "resolution_w": a.meter_res_w, "accuracy_pct": a.meter_acc_pct}
        md += ["## Board input power", "",
               f"Meter: {a.meter}, resolution {a.meter_res_w:g} W"
               + (f", accuracy ±{a.meter_acc_pct:g} % of reading" if a.meter_acc_pct else "")
               + f". {a.trim_s:g} s trimmed from both ends of every file.", "",
               "| condition | rep | samples | mean W | sd W |", "|---|---|---|---|---|"]
        for name, cd in conds.items():
            for i, r in enumerate(cd["reps"], 1):
                md.append(f"| {name} | {i} | {r['n']} | {r['mean']:.4f} | {r['sd']:.4f} |")
            ag = cd["across_reps"]
            md.append(f"| **{name}** | all | {ag['n']} reps | **{ag['mean']:.4f}** | spread {ag['spread']:.4f} |")
        md.append("")
        if "idle" in conds and "active" in conds:
            v = delta_verdict(conds["active"]["across_reps"], conds["idle"]["across_reps"], a.meter_res_w)
            R["delta_p"] = v
            md += ["## ΔP = P_active − P_idle", ""]
            if v["status"] == "insufficient":
                md += [f"**No verdict**: {v['n_active']} active and {v['n_idle']} idle repetitions; at least "
                       f"{MIN_REPS} of each are needed to estimate run-to-run spread. Means are listed above; "
                       f"no ΔP or energy figure is produced.", ""]
            else:
                md += [f"ΔP = **{v['delta_w'] * 1e3:.2f} mW**. Standard error of the difference "
                       f"{v['u_w'] * 1e3:.2f} mW (Welch df "
                       + (f"{v['df']:.1f}" if v["df"] else "∞") + f", t₀.₉₉₅ = {v['t']:.3f}); "
                       f"decision margin {v['margin_w'] * 1e3:.2f} mW = max(t·u, {RES_K:g} × meter resolution).", ""]
                if v["status"] == "resolved":
                    lo, hi = v["ci99_w"]
                    md.append(f"Verdict: **resolved**. 99 % interval {lo * 1e3:.2f} … {hi * 1e3:.2f} mW.")
                elif v["status"] == "not_resolved":
                    md.append(f"Verdict: **NOT resolved** -- report the upper bound ΔP < "
                              f"{v['upper_bound_w'] * 1e3:.2f} mW (one-sided 99.5 %), not a value.")
                md.append("")
            if v["status"] == "anomaly":
                with open(os.path.join(a.out, "results.md"), "w") as f:
                    f.write("\n".join(md + ["**ANOMALY: active is below idle by more than the margin.**"]))
                sys.exit(f"ANOMALY: P_active is {-v['delta_w'] * 1e3:.2f} mW BELOW P_idle, beyond the "
                         f"{v['margin_w'] * 1e3:.2f} mW margin. Swapped labels, wrong files or drift -- "
                         f"re-measure (interleave ABABAB); nothing publishable here.")
            if steps_per_s and v["status"] in ("resolved", "not_resolved"):
                if v["status"] == "resolved":
                    e = v["delta_w"] / steps_per_s
                    R["energy_per_step_j"] = e
                    md.append(f"Marginal energy per {a.step_name}: **{fmt_j(e)}** "
                              f"(ΔP / {steps_per_s:,.2f} per s, rate from the {src} counter).")
                else:
                    e = v["upper_bound_w"] / steps_per_s
                    R["energy_per_step_upper_bound_j"] = e
                    md.append(f"Marginal energy per {a.step_name}: **< {fmt_j(e)}** (upper bound; "
                              f"rate from the {src} counter).")
                wall = conds["active"]["across_reps"]["mean"] / steps_per_s
                R["board_energy_per_step_j"] = wall
                md += ["", f"Whole-board energy per {a.step_name} (P_active / rate, includes DDR3, "
                           f"regulators, idle fabric): {fmt_j(wall)}.", ""]

    md += ["## Inputs (sha256)", ""] + [f"- `{k}` `{v}`" for k, v in sorted(R["inputs"].items())] + [""]
    def clean(o):
        if isinstance(o, float) and not math.isfinite(o):
            return None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    with open(os.path.join(a.out, "results.json"), "w") as f:
        json.dump(clean(R), f, indent=1, allow_nan=False)
    with open(os.path.join(a.out, "results.md"), "w") as f:
        f.write("\n".join(md))
    print("\n".join(md))
    print(f"\nwritten: {a.out}/results.json, {a.out}/results.md")
    if R.get("instrument_selfcheck", {}).get("violations"):
        sys.exit("INSTRUMENT SELF-CHECK FAILED -- these numbers are not usable")


if __name__ == "__main__":
    main()
